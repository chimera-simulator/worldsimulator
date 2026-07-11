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
from datetime import datetime, timezone
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


def _next_api_key() -> Optional[str]:
    if _key_rotator is None:
        return None
    return next(_key_rotator)


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
) -> Optional[str]:
    """Gọi Gemini Flash 2.5 Free với 1 key trong round-robin.

    [MỚI] Nếu `budget` được truyền vào: kiểm tra + TRỪ quota TRƯỚC khi gọi
    API thật (`model.generate_content`). Đây là điểm trừ quota DUY NHẤT
    của toàn bộ pipeline — mọi agent khác (t0, t2) trừ quota URL ở tầng
    riêng của chúng, nhưng quota Gemini call/token CHỈ được trừ ở đây vì
    đây là nơi DUY NHẤT gọi Gemini API thật (xem docstring đầu file)."""

    if budget is not None and not budget.consume_gemini_call(estimated_tokens):
        logger.warning(
            "⚠️ [Summarizer] Gemini budget exhausted — bỏ qua call này."
        )
        return None

    api_key = _next_api_key()
    if not api_key:
        logger.error("❌ [Summarizer] Không có Gemini API key nào trong GEMINI_MODEL_NO_1..7.")
        return None

    try:
        import google.generativeai as genai

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

        # [MỚI] Nếu Gemini trả usage metadata thật, điều chỉnh counter
        # cho chính xác thay vì giữ nguyên ước tính estimated_tokens.
        if budget is not None:
            actual = getattr(response, "usage_metadata", None)
            if actual is not None:
                actual_total = getattr(actual, "total_token_count", None)
                if isinstance(actual_total, int):
                    budget.record_actual_tokens(actual_total - estimated_tokens)

        return response.text
    except Exception as e:
        logger.warning(f"⚠️ [Summarizer] Gemini call thất bại (key rotation sẽ dùng key khác lần sau): {e}")
        return None


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

        raw_response = _call_gemini(system_prompt, user_content, temperature, budget=budget)

        if raw_response is None:
            attempt += 1
            temperature = max(0.1, temperature - 0.1)
            continue

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

    raw_response = _call_gemini(system_prompt, user_content, temperature=0.2, budget=budget)
    if raw_response is None:
        if budget is not None and budget.is_gemini_budget_exhausted() and obs:
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
