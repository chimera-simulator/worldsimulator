"""
tests/test_gemini_retry.py
Kiểm thử cơ chế retry an toàn + key quarantine cho summarizer.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Helpers: mock BudgetManager
# ---------------------------------------------------------------------------
class _FakeBudget:
    def __init__(self, *, gemini_ok=True, time_ok=True):
        self._gemini_ok = gemini_ok
        self._time_ok = time_ok
        self.calls = 0

    def consume_gemini_call(self, estimated_tokens=1000):
        self.calls += 1
        return self._gemini_ok

    def is_gemini_budget_exhausted(self):
        return not self._gemini_ok

    def is_time_budget_exhausted(self):
        return not self._time_ok

    def record_actual_tokens(self, delta):
        pass

    def snapshot(self):
        return SimpleNamespace(tokens_used=0)


# ---------------------------------------------------------------------------
# Test 1 — content_blocked: dừng ngay, không retry
# ---------------------------------------------------------------------------
def test_call_gemini_content_blocked():
    """response.text raise ValueError → _call_gemini trả (None, 'content_blocked')."""
    import summarizer

    fake_response = MagicMock()
    type(fake_response).text = property(lambda self: (_ for _ in ()).throw(ValueError("blocked")))
    fake_response.usage_metadata = None

    with patch("google.generativeai.GenerativeModel") as MockModel:
        MockModel.return_value.generate_content.return_value = fake_response
        with patch("google.generativeai.configure"):
            with patch.object(summarizer, "_next_api_key", return_value="FAKE_KEY_XY"):
                result_text, error_type = summarizer._call_gemini("sys", "user", 0.2)

    assert result_text is None
    assert error_type == "content_blocked"


# ---------------------------------------------------------------------------
# Test 2 — content_blocked trong phase_a: break ngay sau 1 lần gọi
# ---------------------------------------------------------------------------
def test_phase_a_content_blocked_breaks_immediately():
    """content_blocked → phase_a break ngay, KHÔNG retry lần 2."""
    import summarizer

    call_count = 0

    def fake_call_gemini(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return None, "content_blocked"

    with patch.object(summarizer, "_call_gemini", side_effect=fake_call_gemini):
        with patch.object(summarizer, "load_prompt_template", return_value="PROMPT"):
            result, ok = summarizer.phase_a_visual_extractor(
                raw_text="test", image_metadata=[], target_form_field="field"
            )

    assert ok is False
    assert call_count == 1, f"Phải break sau 1 lần, nhưng gọi {call_count} lần"


# ---------------------------------------------------------------------------
# Test 3 — rate_limit: không tăng attempt, có sleep
# ---------------------------------------------------------------------------
def test_rate_limit_does_not_increment_attempt():
    """rate_limit → system_retry_count tăng, attempt KHÔNG tăng → số lần gọi = SYSTEM_RETRY_MAX+1."""
    import summarizer

    call_count = 0

    def fake_call_gemini(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return None, "rate_limit"

    sleep_calls = []

    with patch.object(summarizer, "_call_gemini", side_effect=fake_call_gemini):
        with patch.object(summarizer, "load_prompt_template", return_value="PROMPT"):
            with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                result, ok = summarizer.phase_a_visual_extractor(
                    raw_text="test", image_metadata=[], target_form_field="field",
                    max_retries=2,
                )

    # SYSTEM_RETRY_MAX = 5 → break sau lần thứ 6 (system_retry_count > 5)
    SYSTEM_RETRY_MAX = 5
    assert call_count == SYSTEM_RETRY_MAX + 1, (
        f"Kỳ vọng đúng {SYSTEM_RETRY_MAX + 1} lần gọi (attempt không được tăng "
        f"khi lỗi là rate_limit), nhưng gọi {call_count} lần"
    )
    assert ok is False
    assert call_count <= 7, f"Gọi quá nhiều lần: {call_count}"
    assert len(sleep_calls) > 0, "Phải có sleep khi rate_limit"


# ---------------------------------------------------------------------------
# Test 3b — rate_limit stops within SYSTEM_RETRY_MAX + 1 calls
# ---------------------------------------------------------------------------
def test_rate_limit_stops_within_bounds():
    """rate_limit liên tục → vòng lặp dừng ≤ SYSTEM_RETRY_MAX+1 lần gọi."""
    import summarizer

    call_count = 0

    def fake_call_gemini(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return None, "rate_limit"

    with patch.object(summarizer, "_call_gemini", side_effect=fake_call_gemini):
        with patch.object(summarizer, "load_prompt_template", return_value="PROMPT"):
            with patch("time.sleep"):
                result, ok = summarizer.phase_a_visual_extractor(
                    raw_text="test", image_metadata=[], target_form_field="field",
                    max_retries=2,
                )

    SYSTEM_RETRY_MAX = 5
    assert call_count <= SYSTEM_RETRY_MAX + 1, (
        f"Gọi {call_count} lần — vượt trần {SYSTEM_RETRY_MAX + 1}"
    )
    assert ok is False


# ---------------------------------------------------------------------------
# Test 4 — Không log API key đầy đủ
# ---------------------------------------------------------------------------
def test_no_full_api_key_in_logs(caplog):
    """API key đầy đủ KHÔNG được xuất hiện trong log."""
    import summarizer

    FAKE_KEY = "FAKE_KEY_ABCDE_SECRET"

    fake_response = MagicMock()
    type(fake_response).text = property(lambda self: (_ for _ in ()).throw(ValueError("blocked")))
    fake_response.usage_metadata = None

    with patch("google.generativeai.GenerativeModel") as MockModel:
        MockModel.return_value.generate_content.return_value = fake_response
        with patch("google.generativeai.configure"):
            with patch.object(summarizer, "_next_api_key", return_value=FAKE_KEY):
                import logging
                with caplog.at_level(logging.DEBUG, logger="summarizer"):
                    summarizer._call_gemini("sys", "user", 0.2)

    assert FAKE_KEY not in caplog.text, (
        f"API key đầy đủ '{FAKE_KEY}' xuất hiện trong log — vi phạm security!"
    )


# ---------------------------------------------------------------------------
# Test 5 — budget_exhausted: break ngay, không gọi API
# ---------------------------------------------------------------------------
def test_budget_exhausted_breaks_immediately():
    """consume_gemini_call trả False → (None, 'budget_exhausted'), 0 request thật."""
    import summarizer

    budget = _FakeBudget(gemini_ok=False)
    api_call_count = 0

    def fake_generate(*args, **kwargs):
        nonlocal api_call_count
        api_call_count += 1
        return MagicMock()

    with patch("google.generativeai.GenerativeModel") as MockModel:
        MockModel.return_value.generate_content.side_effect = fake_generate
        with patch("google.generativeai.configure"):
            with patch.object(summarizer, "_next_api_key", return_value="FAKE_KEY_AB"):
                text, error_type = summarizer._call_gemini("sys", "user", 0.2, budget=budget)

    assert text is None
    assert error_type == "budget_exhausted"
    assert api_call_count == 0, "Không được gọi API thật khi budget cạn"


# ---------------------------------------------------------------------------
# Test 6 — Key quarantined bị skip
# ---------------------------------------------------------------------------
def test_quarantined_key_is_skipped():
    """Key đang trong quarantine period → _next_api_key trả key thứ 2."""
    import summarizer

    future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    blackbook = {
        "key_quarantine": {
            "Y1": {"quarantined_until": future, "reason": "rpd_exhausted"}
        }
    }

    original_keys = summarizer.GEMINI_API_KEYS
    try:
        summarizer.GEMINI_API_KEYS = ["KEY_ABCXY1", "KEY_ABCXY2"]
        summarizer._key_rotator = summarizer._get_key_rotator()
        key = summarizer._next_api_key(blackbook=blackbook)
    finally:
        summarizer.GEMINI_API_KEYS = original_keys
        summarizer._key_rotator = summarizer._get_key_rotator()

    assert key is not None
    assert key[-2:] != "Y1", f"Key bị quarantine (Y1) không được trả về, nhưng nhận: {key}"


# ---------------------------------------------------------------------------
# Test 7 — Tất cả key quarantine → trả None
# ---------------------------------------------------------------------------
def test_all_keys_quarantined_returns_none():
    """Khi tất cả key đều quarantine → _next_api_key trả None."""
    import summarizer

    future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    blackbook = {
        "key_quarantine": {
            "Y1": {"quarantined_until": future, "reason": "rpd_exhausted"},
            "Y2": {"quarantined_until": future, "reason": "rpd_exhausted"},
        }
    }

    original_keys = summarizer.GEMINI_API_KEYS
    try:
        summarizer.GEMINI_API_KEYS = ["KEY_ABCXY1", "KEY_ABCXY2"]
        summarizer._key_rotator = summarizer._get_key_rotator()
        key = summarizer._next_api_key(blackbook=blackbook)
    finally:
        summarizer.GEMINI_API_KEYS = original_keys
        summarizer._key_rotator = summarizer._get_key_rotator()

    assert key is None


# ---------------------------------------------------------------------------
# Test 8 — _quarantine_key ghi đúng cấu trúc, không lưu key đầy đủ
# ---------------------------------------------------------------------------
def test_quarantine_key_writes_correct_structure():
    """_quarantine_key chỉ lưu 2 ký tự cuối, không lưu key đầy đủ."""
    import summarizer

    blackbook = {}
    full_key = "AIzaSy_VERY_SECRET_KEY_XY"
    summarizer._quarantine_key(full_key, blackbook, reason="rpd_exhausted")

    assert "key_quarantine" in blackbook
    qmap = blackbook["key_quarantine"]

    # key_id phải là 2 ký tự cuối
    assert "XY" in qmap, f"key_id 'XY' không có trong key_quarantine: {qmap}"

    # Key đầy đủ KHÔNG được xuất hiện trong JSON của blackbook
    dumped = json.dumps(blackbook)
    assert full_key not in dumped, "Key đầy đủ không được lưu trong blackbook!"

    entry = qmap["XY"]
    assert "quarantined_until" in entry
    assert entry["reason"] == "rpd_exhausted"


# ---------------------------------------------------------------------------
# Test 9 — Quarantine hết hạn → key được dùng lại
# ---------------------------------------------------------------------------
def test_expired_quarantine_allows_key():
    """quarantined_until trong quá khứ → key được dùng lại bình thường."""
    import summarizer

    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    blackbook = {
        "key_quarantine": {
            "Y1": {"quarantined_until": past, "reason": "rpd_exhausted"}
        }
    }

    original_keys = summarizer.GEMINI_API_KEYS
    try:
        summarizer.GEMINI_API_KEYS = ["KEY_ABCXY1"]
        summarizer._key_rotator = summarizer._get_key_rotator()
        key = summarizer._next_api_key(blackbook=blackbook)
    finally:
        summarizer.GEMINI_API_KEYS = original_keys
        summarizer._key_rotator = summarizer._get_key_rotator()

    assert key == "KEY_ABCXY1", f"Key hết hạn quarantine phải được trả về, nhưng nhận: {key}"
