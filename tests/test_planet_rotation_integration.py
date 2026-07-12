"""
tests/test_planet_rotation_integration.py — [SPEC_FIX_2_6][Coder 1 — lượt 2, fix REJECT]
===========================================================================================
Test tích hợp cho `main.run_pipeline_once()`, bổ sung theo yêu cầu ở
REJECT_CODER1_LUOT2_PLANET_ROTATION.md, mục "Yêu cầu fix" #2.

Khác với `tests/test_planet_rotation.py` (chỉ gọi trực tiếp 3 hàm helper
tách biệt), các test ở đây chạy THẬT qua `run_pipeline_once()` để lộ đúng
tương tác giữa `planet_target_fields` (fields thiếu của working planet
đang retry) và `pending_fields` toàn cục (`_load_pending_fields_from_db()`,
quét TOÀN BỘ `visual_blueprint_collection`, không lọc theo
`working_planet_id`) — đây chính là chỗ bug cũ (dòng
`effective_target_fields = planet_target_fields if planet_target_fields
else pending_fields`) lọt lưới 10/10 test unit-level trước đó.

Chiến lược mock:
- `main.load_blackbook` / `main.save_blackbook` — thay bằng in-memory dict,
  không đụng file thật trên đĩa.
- `main._load_pending_fields_from_db` / `main._visual_blueprint_collection_is_empty`
  — controllable trực tiếp theo từng case, không cần MongoDB thật.
- `main.run_search_pipeline` (T0) — AsyncMock ghi lại `target_fields` được
  truyền vào rồi raise 1 exception sentinel để dừng pipeline ngay sau
  bước (3)/(4) đang test, không cần mock tiếp toàn bộ T1->T5.

Nếu môi trường thiếu dependency runtime của main.py (httpx, pymongo,
google-generativeai, ...), toàn bộ test tự SKIP thay vì FAIL — theo đúng
pattern đã dùng ở tests/test_planet_rotation.py / tests/test_main_time_budget.py.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest import mock

import config

try:
    import main
    _MAIN_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - phụ thuộc môi trường CI (thiếu pymongo/httpx/...)
    main = None
    _MAIN_IMPORT_ERROR = e


class _StopAfterT0Search(Exception):
    """Sentinel raise từ T0 mock để dừng run_pipeline_once() sớm, ngay sau
    khi effective_target_fields đã được quyết định và truyền vào T0 —
    không cần mock tiếp T1->T5."""


@unittest.skipIf(main is None, f"main.py không import được trong môi trường này: {_MAIN_IMPORT_ERROR}")
class TestRunPipelineOnceGapFillMerge(unittest.TestCase):
    """3 case theo đúng yêu cầu REJECT mục 'Yêu cầu fix' #2."""

    def _empty_blackbook(self) -> dict:
        return {"keywords": {}, "scrape_state": {}, "version": 1}

    def _run_once_capture_t0_kwargs(
        self,
        blackbook: dict,
        pending_fields_return,
        collection_is_empty_return: bool,
    ):
        """Chạy run_pipeline_once() thật, mock các I/O ngoài (blackbook
        file, MongoDB, T0 search) và trả về (kwargs T0 đã nhận, report nếu
        pipeline dừng SỚM trước khi tới T0 — vd case 'KB đã đầy')."""
        captured_kwargs = {}

        async def fake_run_search_pipeline(*args, **kwargs):
            captured_kwargs.update(kwargs)
            raise _StopAfterT0Search()

        with mock.patch.object(main, "load_blackbook", return_value=blackbook), \
             mock.patch.object(main, "save_blackbook", return_value=None), \
             mock.patch.object(
                 main, "_load_pending_fields_from_db",
                 return_value=pending_fields_return,
             ) as mock_load_pending, \
             mock.patch.object(
                 main, "_visual_blueprint_collection_is_empty",
                 return_value=collection_is_empty_return,
             ), \
             mock.patch.object(main, "run_search_pipeline", side_effect=fake_run_search_pipeline):

            try:
                report = asyncio.run(main.run_pipeline_once(cfg=config))
            except _StopAfterT0Search:
                report = None

        return captured_kwargs, report, mock_load_pending

    # -------------------------------------------------------------------
    # Case 1 — Archetype MỚI + pending_fields toàn cục KHÔNG rỗng (thuộc
    # archetype/entity KHÁC) → effective_target_fields (= target_fields
    # truyền cho T0) PHẢI là None (full-scan), KHÔNG được lấy pending_fields đó.
    # -------------------------------------------------------------------
    def test_new_archetype_ignores_unrelated_global_pending_fields(self):
        blackbook = self._empty_blackbook()  # không có in_progress -> archetype mới

        other_archetype_pending_fields = [
            "form_1_planet_foundation.planet_identity.core_material",
        ]
        kwargs, report, _mock_load_pending = self._run_once_capture_t0_kwargs(
            blackbook,
            pending_fields_return=other_archetype_pending_fields,
            collection_is_empty_return=False,
        )

        self.assertIsNone(report)  # dừng do sentinel, không phải kb_full
        self.assertIn("target_fields", kwargs)
        self.assertIsNone(
            kwargs["target_fields"],
            "Archetype mới phải full-scan (target_fields=None), KHÔNG được "
            "nhận nhầm pending_fields của archetype/entity khác.",
        )

    # -------------------------------------------------------------------
    # Case 2 — Archetype đang retry_pending → effective_target_fields
    # PHẢI đúng bằng fields_pending của in_progress, không bị pending_fields
    # toàn cục ghi đè (và không cần gọi _load_pending_fields_from_db()).
    # -------------------------------------------------------------------
    def test_retry_pending_uses_own_fields_pending_not_global(self):
        blackbook = self._empty_blackbook()
        own_fields_pending = [
            "form_1_planet_foundation.planet_identity.terrain_patterns",
        ]
        rotation = main._get_current_planet_archetype(blackbook)
        rotation["in_progress"] = {
            "working_planet_id": "PLANET_TEST_INTEGRATION_01",
            "archetype_id": "jungle_world",
            "started_at": "2026-07-12T17:01:00Z",
            "status": "retry_pending",
            "retry_count": 1,
            "fields_filled": [],
            "fields_pending": own_fields_pending,
        }

        unrelated_global_pending_fields = [
            "form_2_civilization_layer.some_other_field",
        ]
        kwargs, report, mock_load_pending = self._run_once_capture_t0_kwargs(
            blackbook,
            pending_fields_return=unrelated_global_pending_fields,
            collection_is_empty_return=False,
        )

        self.assertIsNone(report)
        self.assertEqual(kwargs.get("target_fields"), own_fields_pending)
        # Khi retry_pending, cơ chế mới không còn cần đọc pending_fields
        # toàn cục để quyết định effective_target_fields.
        mock_load_pending.assert_not_called()

    # -------------------------------------------------------------------
    # Case 3 — Cold-start thật (DB rỗng, pending_fields is None) →
    # full-scan, KHÔNG bị chặn nhầm bởi check "KB đã đầy".
    # -------------------------------------------------------------------
    def test_cold_start_full_scan_not_blocked_by_kb_full_check(self):
        blackbook = self._empty_blackbook()

        kwargs, report, _mock_load_pending = self._run_once_capture_t0_kwargs(
            blackbook,
            pending_fields_return=None,
            collection_is_empty_return=True,
        )

        self.assertIsNone(report)
        self.assertIn("target_fields", kwargs)
        self.assertIsNone(kwargs["target_fields"])

    # -------------------------------------------------------------------
    # Bonus — KB THẬT SỰ đã đầy (không phải archetype mới bị hiểu nhầm):
    # DB không rỗng + không document nào còn pending_fields -> phải dừng
    # hẳn với skipped_reason="kb_full", KHÔNG gọi T0.
    # -------------------------------------------------------------------
    def test_kb_actually_full_stops_before_t0(self):
        blackbook = self._empty_blackbook()

        kwargs, report, _mock_load_pending = self._run_once_capture_t0_kwargs(
            blackbook,
            pending_fields_return=None,
            collection_is_empty_return=False,
        )

        self.assertEqual(kwargs, {})  # T0 không được gọi
        self.assertIsNotNone(report)
        self.assertEqual(report.get("skipped_reason"), "kb_full")


if __name__ == "__main__":
    unittest.main()
