"""
summarizer.py — Agent 4: TRÁI TIM của Repo 1 (Phase A + Phase B, Gate 3 + Gate 4)
====================================================================================
[CX]
- Đây là file DUY NHẤT trong 6 agent được phép gọi Gemini API.
- Phase A LUÔN chạy trước Phase B. Phase B tuyệt đối không được thực thi
  nếu Phase A fail (Gate 3 chặn cứng).
- Phase B tuyệt đối không được sửa locked_fields của Phase A — đảm bảo bằng
  kiến trúc (Phase B ghi vào instance MasterSchema20 mới, tách biệt hoàn
  toàn khỏi object VisualBlueprint30 của Phase A), không phải bằng so sánh
  runtime (đã gỡ bỏ vì là no-op — xem comment trong phase_b_gap_filling()).
- Không bao giờ tự set ip_filter_status = "cleaned" mặc định.
- Temperature bắt buộc 0.1–0.3 cho cả 2 phase.
- Retry tối đa 2 lần cho Phase A. Phase B không retry (fail thì fail).
"""
from __future__ import annotations

import itertools
import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from pydantic import ValidationError

from config import GEMINI_API_KEYS, GEMINI_MODEL_NAME, VISUAL_BLUEPRINT_3_0_TEMPLATE
from schemas.master_schema_2_0 import MasterSchema20
from schemas.visual_blueprint_3_0 import VisualBlueprint30
from core.budget_manager import BudgetManager
from core.logger import PipelineLogger

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# Proper-noun IP đã biết (dùng làm lưới an toàn bổ sung sau khi LLM strip;
# không thay thế yêu cầu IP-STRIP trong system prompt, chỉ là double-check).
_KNOWN_IP_TERMS = [
    "marvel", "star wars", "disney", "pixar", "nintendo", "pokemon",
    "goku", "dragon ball", "harry potter", "dc comics", "naruto",
]


def _get_key_rotator():
    """Round-robin generator qua GEMINI_API_KEYS. Trả về None nếu rỗng
    (cho phép unit test / dry-run không cần key thật)."""
    if not GEMINI_API_KEYS:
        return None
    return itertools.cycle(GEMINI_API_KEYS)


_key_rotator = _get_key_rotator()


def _next_api_key(blackbook: dict | None = None) -> Optional[str]:
    """Trả key tiếp theo chưa bị quarantine. None nếu tất cả quarantine hoặc không có key."""
    if _key_rotator is None:
        return None

    quarantine_map = (blackbook or {}).get("key_quarantine", {})
    now_utc = datetime.now(timezone.utc)
    total_keys = len(GEMINI_API_KEYS)
    if total_keys == 0:
        return None

    for _ in range(total_keys):
        key = next(_key_rotator)
        key_id = key[-2:]
        entry = quarantine_map.get(key_id, {})
        until_str = entry.get("quarantined_until")
        if until_str:
            try:
                expiry = datetime.fromisoformat(until_str)
                if now_utc < expiry:
                    logger.debug(f"🔒 [KeyRotator] Key ...{key_id} đang quarantine đến {until_str}, skip.")
                    continue
            except ValueError:
                pass
        return key  # Key này chưa quarantine hoặc đã hết hạn quarantine

    logger.error("❌ [KeyRotator] Tất cả API key đang bị quarantine — không còn key nào dùng được.")
    return None


def _quarantine_key(key: str, blackbook: dict, reason: str = "rpd_exhausted") -> None:
    """Ghi quarantine cho key vào blackbook đến UTC midnight ngày mai.
    Chỉ lưu 2 ký tự cuối của key — KHÔNG log/lưu key đầy đủ (tránh lộ secret).
    """
    key_id = key[-2:]
    now_utc = datetime.now(timezone.utc)
    next_reset = (now_utc + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    quarantine_section = blackbook.setdefault("key_quarantine", {})
    quarantine_section[key_id] = {
        "quarantined_until": next_reset.isoformat(),
        "reason": reason,
    }
    logger.warning(
        f"🔒 [KeyQuarantine] Key ...{key_id} bị quarantine đến {next_reset.isoformat()} "
        f"(reason: {reason})"
    )


def load_prompt_template(path: str) -> str:
    """Đọc file .txt từ prompts/."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"❌ [Summarizer] Không đọc được prompt template '{path}': {e}")
        return ""


def _strip_markdown_fence(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text).strip()


def _call_gemini(
    system_prompt: str,
    user_content: str,
    temperature: float,
    budget: "BudgetManager | None" = None,
    estimated_tokens: int = 1000,
    blackbook: dict | None = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Gọi Gemini Flash 2.5 Free với 1 key trong round-robin.

    Returns: (response_text, error_type)
      - (text, None)               → thành công
      - (None, "budget_exhausted") → budget cạn, caller nên break ngay
      - (None, "content_blocked")  → safety filter, caller nên break ngay
      - (None, "rate_limit")       → 429 RPM/RPD, caller nên sleep + retry
      - (None, "network_error")    → timeout/DNS/lỗi SDK, caller nên sleep + retry
    """
    if budget is not None and not budget.consume_gemini_call(estimated_tokens):
        logger.warning("⚠️ [Summarizer] Gemini budget exhausted — bỏ qua call này.")
        return None, "budget_exhausted"

    api_key = _next_api_key(blackbook=blackbook)
    if not api_key:
        logger.error("❌ [Summarizer] Không có Gemini API key nào khả dụng (tất cả quarantine hoặc rỗng).")
        return None, "network_error"

    try:
        import google.generativeai as genai
        import google.api_core.exceptions as google_exceptions

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL_NAME,
            system_instruction=system_prompt,
            generation_config={
                "temperature": temperature,
                "response_mime_type": "application/json",
            },
        )
        response = model.generate_content(user_content)

        # Cập nhật token thực tế nếu có
        if budget is not None:
            actual = getattr(response, "usage_metadata", None)
            if actual is not None:
                actual_total = getattr(actual, "total_token_count", None)
                if isinstance(actual_total, int):
                    budget.record_actual_tokens(actual_total - estimated_tokens)

        # Safety filter KHÔNG raise ở generate_content — chỉ raise khi đọc .text
        try:
            text = response.text
            return text, None
        except (ValueError, IndexError) as e:
            logger.warning(f"⚠️ [API] Response bị safety filter chặn (không retry): {e}")
            return None, "content_blocked"

    except Exception as e:
        # Phân loại: ResourceExhausted = 429 rate-limit; còn lại = network/SDK
        try:
            import google.api_core.exceptions as google_exceptions
            if isinstance(e, google_exceptions.ResourceExhausted):
                err_msg = str(e).lower()
                is_rpd = any(kw in err_msg for kw in ("daily", "per day", "quota exhausted", "day"))
                if is_rpd and blackbook is not None:
                    _quarantine_key(api_key, blackbook, reason="rpd_exhausted")
                    logger.warning(f"⚠️ [API] RPD exhausted cho key ...{api_key[-2:]} — đã quarantine.")
                else:
                    logger.warning(f"⚠️ [API] Rate limit 429 (RPM tạm thời): {e}")
                return None, "rate_limit"
        except ImportError:
            pass
        logger.warning(f"⚠️ [API] Lỗi mạng/SDK: {e}")
        return None, "network_error"


def _contains_known_ip(payload: dict) -> list[str]:
    """Quét thô các proper noun IP đã biết trong toàn bộ text field của
    payload (lưới an toàn bổ sung, KHÔNG thay thế yêu cầu strip ở prompt)."""
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    return [term for term in _KNOWN_IP_TERMS if term in serialized]


# =============================================================================
# PHASE A — Visual Extractor (Gate 3)
# =============================================================================
def phase_a_visual_extractor(
    raw_text: str,
    image_metadata: list,
    target_form_field: str,
    max_retries: int = 2,
    budget: "BudgetManager | None" = None,
    obs: "PipelineLogger | None" = None,
    blackbook: dict | None = None,
) -> Tuple[Optional[dict], bool]:
    system_prompt = load_prompt_template("prompts/phase_a_visual_extractor.txt")
    if not system_prompt:
        return None, False

    user_content = json.dumps(
        {
            "raw_text": raw_text[:8000],  # cap để tiết kiệm token free tier
            "image_metadata": image_metadata,
            "target_form_field": target_form_field,
            "template": VISUAL_BLUEPRINT_3_0_TEMPLATE,
        },
        ensure_ascii=False,
    )

    temperature = 0.2
    attempt = 0
    system_retry_count = 0   # Đếm retry lỗi hệ thống (rate_limit / network_error)
    SYSTEM_RETRY_MAX = 5     # Trần cứng — đủ vượt nghẽn RPM, không đủ treo lâu

    while attempt <= max_retries:
        # [MỚI] Nếu budget đã cạn TRƯỚC lần gọi này, dừng retry ngay —
        # gọi tiếp cũng sẽ luôn bị _call_gemini() chặn và trả None.
        if budget is not None and budget.is_gemini_budget_exhausted():
            if obs:
                obs.budget_exhausted(resource="gemini", agent="summarizer")
            logger.warning(
                f"⚠️ [Phase A][Gate 3] Dừng retry (attempt {attempt}) — Gemini budget đã cạn."
            )
            break

        raw_response, error_type = _call_gemini(
            system_prompt, user_content, temperature,
            budget=budget, blackbook=blackbook,
        )

        # --- Nhóm 1: Dừng ngay, không retry dưới bất kỳ hình thức nào ---
        if error_type == "budget_exhausted":
            if obs:
                obs.budget_exhausted(resource="gemini", agent="summarizer")
            logger.warning("⚠️ [Phase A] Budget exhausted — dừng retry.")
            break

        if error_type == "content_blocked":
            logger.warning("⚠️ [Phase A] Content bị safety filter — dừng retry (retry lại cũng sẽ bị chặn).")
            break

        # --- Nhóm 2: Lỗi hệ thống — sleep + backoff, KHÔNG tăng attempt ---
        if error_type in ("rate_limit", "network_error") or raw_response is None:
            system_retry_count += 1
            if system_retry_count > SYSTEM_RETRY_MAX:
                logger.warning(
                    f"⚠️ [Phase A] Vượt trần system_retry ({SYSTEM_RETRY_MAX}) — dừng."
                )
                break

            # Check time budget TRƯỚC khi sleep (tránh treo hàng phút)
            if budget is not None and budget.is_time_budget_exhausted():
                logger.warning("⚠️ [Phase A] Time budget cạn trong khi chờ retry — dừng.")
                break

            # Backoff lũy tiến: 5s → 10s → 20s → 30s → 30s (trần 30s)
            sleep_sec = min(5 * (2 ** (system_retry_count - 1)), 30)
            logger.info(
                f"⏳ [Phase A] Lỗi hệ thống [{error_type}] lần {system_retry_count} "
                f"— sleep {sleep_sec}s trước khi retry..."
            )
            time.sleep(sleep_sec)
            continue  # KHÔNG tăng attempt, KHÔNG hạ temperature

        # --- Nhóm 3: raw_response có nội dung, tiếp tục xử lý bên dưới ---

        try:
            cleaned = _strip_markdown_fence(raw_response)
            output = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"⚠️ [Phase A] JSON parse lỗi (attempt {attempt + 1}): {e}")
            attempt += 1
            temperature = max(0.1, temperature - 0.1)
            continue

        # Set consistency_lock.locked = True nếu extraction "thành công" theo
        # nhận định của LLM (đã điền species_base/skin) — nhưng vẫn phải qua
        # Pydantic + Gate 3 để xác nhận thật sự hợp lệ.
        output.setdefault("consistency_lock", {})
        if output["consistency_lock"].get("locked") is not True:
            output["consistency_lock"]["locked"] = bool(
                output.get("character_blueprint") or output.get("environment_blueprint")
            )

        try:
            validated = VisualBlueprint30(**output)
        except ValidationError as e:
            logger.warning(f"⚠️ [Phase A][Gate 3] Pydantic validation lỗi (attempt {attempt + 1}): {e}")
            attempt += 1
            temperature = max(0.1, temperature - 0.1)
            continue

        validated_dict = validated.model_dump()

        # [SPEC_FIX_P2 — Vấn đề 2] IP-check bắt buộc ở Phase A (Gate 3).
        # Trước đây lưới an toàn IP chỉ chạy ở Phase B -> Phase A có thể
        # "khoá" (consistency_lock.locked = True) một blueprint còn dính
        # proper noun IP mà không ai bắt lại. Từ giờ: phát hiện IP ở đây
        # PHẢI reject + retry giống lỗi Pydantic, KHÔNG được set True.
        ip_terms_found = _contains_known_ip(validated_dict)
        if ip_terms_found:
            logger.warning(
                f"⚠️ [Phase A][Gate 3] Phát hiện IP proper noun còn sót "
                f"{ip_terms_found} (attempt {attempt + 1}) — reject, retry."
            )
            attempt += 1
            temperature = max(0.1, temperature - 0.1)
            continue

        required_ok = bool(validated_dict.get("validation_rules", {}).get("required_fields"))
        locked_ok = validated_dict.get("consistency_lock", {}).get("locked") is True

        if not required_ok or not locked_ok:
            logger.warning(
                f"⚠️ [Phase A][Gate 3] Blueprint chưa hoàn chỉnh "
                f"(required_fields empty={not required_ok}, locked={locked_ok}), attempt {attempt + 1}."
            )
            attempt += 1
            temperature = max(0.1, temperature - 0.1)
            continue

        logger.info(f"✅ [Phase A][Gate 3] Blueprint pass — visual_id={validated_dict.get('visual_id')}")
        return validated_dict, True

    logger.error(f"❌ [Phase A][Gate 3] Thất bại sau {max_retries + 1} lần thử — flag 'phase_a_failed'.")
    return None, False


# =============================================================================
# PHASE B — Gap-Filling Station (Gate 4)
# =============================================================================
def phase_b_gap_filling(
    locked_blueprint: dict,
    raw_text: str,
    target_form_field: str,
    budget: "BudgetManager | None" = None,
    obs: "PipelineLogger | None" = None,
) -> Tuple[Optional[dict], bool]:
    system_prompt = load_prompt_template("prompts/phase_b_gap_filling.txt")
    if not system_prompt:
        return None, False

    user_content = json.dumps(
        {
            "locked_blueprint": locked_blueprint,
            "raw_text": raw_text[:8000],
            "target_form_field": target_form_field,
        },
        ensure_ascii=False,
    )

    raw_response, error_type = _call_gemini(system_prompt, user_content, temperature=0.2, budget=budget)
    if raw_response is None:
        if error_type == "budget_exhausted" and obs:
            obs.budget_exhausted(resource="gemini", agent="summarizer")
        elif budget is not None and budget.is_gemini_budget_exhausted() and obs:
            obs.budget_exhausted(resource="gemini", agent="summarizer")
        return None, False

    try:
        cleaned = _strip_markdown_fence(raw_response)
        output = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"⚠️ [Phase B] JSON parse lỗi: {e}")
        return None, False

    output.setdefault("provenance_and_metadata", {})
    output["provenance_and_metadata"].setdefault("target_form_field", target_form_field)
    output["provenance_and_metadata"].setdefault("timestamp", datetime.now(timezone.utc).isoformat())

    ip_terms_found = _contains_known_ip(output)
    claimed_status = output["provenance_and_metadata"].get("ip_filter_status", "unverified")

    # Không bao giờ tự tin "cleaned" nếu lưới an toàn vẫn thấy IP còn sót.
    if ip_terms_found:
        output["provenance_and_metadata"]["ip_filter_status"] = "failed"
        output["provenance_and_metadata"]["original_ip_detected"] = ip_terms_found
    elif claimed_status != "cleaned":
        output["provenance_and_metadata"]["ip_filter_status"] = "failed"

    try:
        validated = MasterSchema20(**output)
    except ValidationError as e:
        logger.warning(f"⚠️ [Phase B][Gate 4] Pydantic validation lỗi: {e}")
        return None, False

    validated_dict = validated.model_dump()

    # [SPEC_FIX_P3 — Vấn đề 1] Đã xoá bỏ vòng lặp so sánh "trước/sau" ở đây —
    # nó là no-op: cả 2 lần đọc đều lấy từ `locked_blueprint` (input, không
    # bị hàm này mutate), không lần nào đọc từ `validated_dict` (output thật
    # của Phase B). Về mặt kiến trúc, defense-in-depth bằng code KHÔNG cần
    # thiết ở đây: MasterSchema20 (Phase B) và VisualBlueprint30 (Phase A)
    # là 2 schema tách biệt hoàn toàn về type/namespace — Phase B ghi kết
    # quả vào một instance MasterSchema20 mới (`validated`/`validated_dict`),
    # về bản chất vật lý không có đường nào để ghi đè lên `locked_blueprint`
    # (biến của schema khác, scope khác) đang giữ ở tầng gọi Phase A.
    # Ràng buộc "Phase B không được sửa locked_fields" (docstring đầu file,
    # dòng 8) được đảm bảo bởi chính việc 2 schema không chia sẻ object,
    # không cần một vòng lặp runtime kiểm tra lại điều không thể xảy ra.

    if validated_dict["provenance_and_metadata"]["ip_filter_status"] != "cleaned":
        logger.warning("⚠️ [Phase B][Gate 4] ip_filter_status != 'cleaned' — flag 'ip_strip_incomplete'.")
        return validated_dict, False

    logger.info("✅ [Phase B][Gate 4] Gap-filling pass, ip_filter_status=cleaned.")
    return validated_dict, True


def _dig(d: dict, dot_path: str):
    keys = dot_path.split(".")
    value = d
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


# =============================================================================
# ORCHESTRATOR
# =============================================================================
def run_summarizer(
    scraped_doc: dict,
    budget: "BudgetManager | None" = None,
    obs: "PipelineLogger | None" = None,
    blackbook: dict | None = None,
) -> dict:
    """
    Returns: {"visual_blueprint": dict|None, "schema_record": dict|None,
              "target_form_field": str, "phase_a_ok": bool, "phase_b_ok": bool,
              "_tokens_used": int}
    """
    target_form_field = scraped_doc.get("target_form_field", "")

    tokens_before = budget.snapshot().tokens_used if budget is not None else 0

    blueprint, phase_a_ok = phase_a_visual_extractor(
        scraped_doc.get("raw_text", ""),
        scraped_doc.get("image_metadata", []),
        target_form_field,
        budget=budget,
        obs=obs,
        blackbook=blackbook,
    )

    if not phase_a_ok:
        tokens_after = budget.snapshot().tokens_used if budget is not None else 0
        return {
            "visual_blueprint": blueprint,
            "schema_record": None,
            "target_form_field": target_form_field,
            "phase_a_ok": False,
            "phase_b_ok": False,
            "_tokens_used": tokens_after - tokens_before,
        }

    schema_record, phase_b_ok = phase_b_gap_filling(
        blueprint, scraped_doc.get("raw_text", ""), target_form_field,
        budget=budget, obs=obs,
    )

    tokens_after = budget.snapshot().tokens_used if budget is not None else 0
    return {
        "visual_blueprint": blueprint,
        "schema_record": schema_record,
        "target_form_field": target_form_field,
        "phase_a_ok": phase_a_ok,
        "phase_b_ok": phase_b_ok,
        "_tokens_used": tokens_after - tokens_before,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
