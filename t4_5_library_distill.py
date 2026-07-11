"""
t4_5_library_distill.py — Agent Gate 6.5: Library Distillation
================================================================
Chạy giữa t4_deduplicate.py và t5_upload.py. Nhận danh sách document
đã dedupe, distill mỗi cặp (schema_record, blueprint) thành 1 lib_record
chuẩn hoá để ghi vào collection `lib_entities`.

Triết lý:
- Rule-based extraction TRƯỚC, LLM chỉ làm fallback parse câu tự nhiên.
- "nếu Python if/else làm được thì không đưa cho LLM" (§101 tài liệu gốc).
- temperature=0.1-0.3, tái dùng _call_gemini() của summarizer.py (single
  source of truth cho mọi Gemini call trong Repo 1).
- run_library_distill() mutate in-place deduped_docs (thêm key "lib_record")
  → t5_upload.py đọc lib_record từ cùng 1 doc để giữ 3-phase transaction.

Kiến trúc (Gate 6.5 Strategy Pattern refactor — xem
SPEC_t4_5_distillers_refactor_v1_0.md): phần trích payload đặc thù theo
library_type đã CHUYỂN sang `distillers/*.py` (BaseLibraryDistiller +
DistillerRegistry). File này chỉ còn giữ phần logic dùng chung, KHÔNG
đổi theo library_type: routing, entity_id, LLM fallback structuring, và
điều phối distill_one() qua DistillerRegistry.

KHÔNG được:
- Tạo Gemini client thứ 2 độc lập (vi phạm single-source-of-truth).
- Đụng vào rule_library.py / world_rule_library.
- Đụng vào compute_visual_id() của t4_deduplicate.py.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from distillers.registry import DistillerRegistry
from library_routing import (
    ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE,
    LIBRARY_REQUIRED_FIELDS,
    TARGET_FORM_FIELD_TO_LIBRARY_TYPE,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import _call_gemini từ summarizer.py — single source of truth cho Gemini.
# Dùng lazy import để tránh circular hoặc import error khi chạy tests không
# cần LLM.
# ---------------------------------------------------------------------------
def _get_call_gemini():
    """Lazy import _call_gemini từ summarizer.py."""
    try:
        from summarizer import _call_gemini
        return _call_gemini
    except ImportError as e:
        logger.warning(f"⚠️ [Gate 6.5] Không thể import _call_gemini từ summarizer: {e}")
        return None


# =============================================================================
# 1. ROUTING
# =============================================================================

def route_library_type(doc: dict) -> Optional[str]:
    """Xác định library_type cho 1 doc đã dedupe.

    Logic (theo thứ tự ưu tiên):
    1. Lấy target_form_field từ schema_record.provenance_and_metadata (nếu có).
    2. Duyệt TARGET_FORM_FIELD_TO_LIBRARY_TYPE, trả library_type của entry đầu
       tiên mà target_form_field.startswith(prefix).
    3. Nếu bước 2 không match VÀ blueprint có field \"clothing_and_gear\" không
       rỗng → \"costume\".
    4. Nếu bước 2 không match, fallback dùng blueprint.entity_type qua
       ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE.
    5. Nếu vẫn không match → return None (Gate 6.5 sẽ reject có log).

    Args:
        doc: 1 phần tử của deduped_docs, có keys: visual_id, blueprint,
             schema_record (có thể None), merged, manual_review_needed (có
             thể absent).

    Returns:
        str: library_type hợp lệ, hoặc None nếu không suy luận được.
    """
    schema_record = doc.get("schema_record")
    blueprint = doc.get("blueprint") or {}

    # Bước 1: lấy target_form_field
    target_form_field = ""
    if schema_record:
        target_form_field = (
            (schema_record.get("provenance_and_metadata") or {}).get("target_form_field", "")
            or ""
        )

    # Bước 2: match theo prefix TARGET_FORM_FIELD_TO_LIBRARY_TYPE
    if target_form_field:
        for prefix, lib_type in TARGET_FORM_FIELD_TO_LIBRARY_TYPE:
            if target_form_field.startswith(prefix):
                return lib_type

    # Bước 3: clothing_and_gear không rỗng → costume
    clothing = blueprint.get("clothing_and_gear")
    if clothing and isinstance(clothing, dict) and len(clothing) > 0:
        return "costume"

    # Bước 4: fallback dùng entity_type
    entity_type = blueprint.get("entity_type", "")
    if entity_type in ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE:
        return ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE[entity_type]

    # Bước 5: không xác định được
    return None


# =============================================================================
# 2. ENTITY ID
# =============================================================================

def generate_entity_id(library_type: str, doc: dict) -> str:
    """Tạo entity_id ổn định từ visual_id đã có.

    Convention: '{LIBRARY_TYPE_UPPER}_{visual_id_suffix}'
    Dùng visual_id đã có (compute_visual_id() ở t4_deduplicate.py, dạng
    'VB_<ENTITY>_<hash8>') làm nguồn ổn định duy nhất — KHÔNG tự sinh hash
    riêng để tránh 2 ID độc lập trỏ cùng 1 entity gây lệch dữ liệu.

    VD: visual_id='VB_SPECIES_a1b2c3d4', library_type='species'
        → entity_id='SPECIES_a1b2c3d4'

    Idempotent: cùng đầu vào → cùng đầu ra (đảm bảo upsert theo
    {library_type, entity_id} ở t5_upload.py không tạo bản ghi trùng).
    """
    visual_id = doc.get("visual_id", "")
    suffix = visual_id.split("_")[-1] if visual_id else "unknown"
    return f"{library_type.upper()}_{suffix}"


# =============================================================================
# 3. LLM FALLBACK STRUCTURING
# =============================================================================

def structure_via_llm(
    schema_record: dict,
    missing_fields: list[str],
    budget=None,
    obs=None,
) -> dict:
    """Fallback LLM: parse câu tự nhiên trong Master Schema thành field có
    kiểu cho các field còn thiếu sau _extract_payload() của Distiller.

    Chỉ dùng khi Python rule-based không lấy được — KHÔNG sáng tạo nội dung,
    chỉ diễn đạt lại (đúng vai trò LLM theo §101 tài liệu gốc).

    Tái dùng _call_gemini() của summarizer.py (single source of truth).
    temperature=0.1-0.3 (bám sát Phase B hiện tại về cách gọi model).

    Nếu budget.max_gemini_calls đã cạn → return {} (KHÔNG raise),
    Gate 6.5 dùng payload đã có + đánh dấu incomplete.
    """
    if budget is not None and hasattr(budget, "is_gemini_budget_exhausted"):
        if budget.is_gemini_budget_exhausted():
            logger.warning("⚠️ [Gate 6.5] Gemini budget cạn — bỏ qua LLM structuring.")
            if obs and hasattr(obs, "budget_exhausted"):
                obs.budget_exhausted(resource="gemini", agent="t4_5_library_distill")
            return {}

    _call_gemini = _get_call_gemini()
    if _call_gemini is None:
        logger.warning("⚠️ [Gate 6.5] _call_gemini không khả dụng — bỏ qua LLM structuring.")
        return {}

    # Trích raw text từ schema_record để LLM parse
    content_for_llm = _extract_raw_text_from_schema(schema_record)
    if not content_for_llm.strip():
        return {}

    fields_str = ", ".join(f'"{f}"' for f in missing_fields)
    system_prompt = (
        "Bạn là parser dữ liệu cấu trúc. Nhiệm vụ: trích xuất CHÍNH XÁC các field "
        "được yêu cầu từ đoạn văn mô tả bên dưới. Chỉ trả JSON, không thêm gì khác. "
        "Nếu một field không tìm thấy trong văn bản, để giá trị là null. "
        "KHÔNG được bịa đặt hay sáng tạo thêm nội dung không có trong văn bản."
    )
    user_content = (
        f"Văn bản mô tả:\n{content_for_llm}\n\n"
        f"Hãy trích xuất các field sau (trả JSON flat):\n"
        f"{fields_str}\n\n"
        f"Chỉ trả về JSON object, không có markdown, không có giải thích."
    )

    try:
        raw = _call_gemini(system_prompt, user_content, temperature=0.15, budget=budget)
        if not raw:
            return {}

        # Strip markdown fence nếu có
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            ).strip()

        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return {}

        # Lọc bỏ null values
        result = {k: v for k, v in parsed.items() if v is not None and v != ""}
        logger.info(
            f"✅ [Gate 6.5] LLM structuring trích được {len(result)} field: {list(result.keys())}"
        )
        return result

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"⚠️ [Gate 6.5] LLM structuring lỗi: {e}")
        return {}


def _extract_raw_text_from_schema(schema_record: dict) -> str:
    """Gom text tự nhiên từ Master Schema để gửi cho LLM parse.
    Duyệt đệ quy, ghép các list[str] và str lại thành 1 block text."""
    parts: list[str] = []
    _collect_text(schema_record, parts, skip_keys={"provenance_and_metadata", "_id"})
    return "\n".join(p for p in parts if p.strip())


def _collect_text(obj, parts: list, skip_keys: set = None, depth: int = 0) -> None:
    """Helper đệ quy cho _extract_raw_text_from_schema."""
    if depth > 10:
        return
    skip_keys = skip_keys or set()

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip_keys:
                continue
            _collect_text(v, parts, skip_keys, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, str):
                parts.append(item)
            else:
                _collect_text(item, parts, skip_keys, depth + 1)
    elif isinstance(obj, str) and obj.strip():
        parts.append(obj)


# =============================================================================
# 4. CORE DISTILL FUNCTIONS
# =============================================================================

def distill_one(doc: dict, budget=None, obs=None) -> Optional[dict]:
    """Distill 1 doc đã dedupe thành lib_record, hoặc None nếu:
    (a) route_library_type() không xác định được library_type — reject vì
        THIẾU NGUỒN HARVEST tương ứng (log mức "❌ Gate 6.5 reject"), hoặc
    (b) library_type xác định được NHƯNG chưa có Distiller implement —
        reject vì THIẾU IMPLEMENTATION (log message khác, mức "⚠️ Gate 6.5
        chưa có Distiller"), phân biệt rõ 2 nguyên nhân theo mục 1.2 tài
        liệu Architect.

    Luồng:
    1. route_library_type(doc) — KHÔNG đổi, vẫn hàm cũ trong file này.
    2. DistillerRegistry.get(library_type) — tra class Distiller.
    3. distiller_cls().distill(doc, budget, obs) — template method lo hết
       phần còn lại (entity_id, payload, LLM fallback, provenance, flatten).

    Args:
        doc: 1 phần tử của deduped_docs từ t4_deduplicate.deduplicate().
        budget: BudgetManager instance (có thể None khi test).
        obs: PipelineLogger instance (có thể None khi test).

    Returns:
        dict: lib_record đã flatten, sẵn để upsert vào lib_entities.
        None: nếu library_type không xác định được, hoặc xác định được
              nhưng chưa có Distiller implement (không phải lỗi hệ thống).
    """
    visual_id = doc.get("visual_id", "unknown")
    blueprint = doc.get("blueprint") or {}

    # Bước 1: routing — KHÔNG đổi
    library_type = route_library_type(doc)
    if library_type is None:
        entity_type = blueprint.get("entity_type", "unknown")
        logger.warning(
            f"❌ [Gate 6.5] '{visual_id}' (entity_type={entity_type!r}) — "
            f"không xác định được library_type, reject khỏi lib_entities "
            f"(vẫn tiếp tục upload bình thường vào visual_blueprint_collection"
            f"/fiction_knowledge ở T5)."
        )
        return None

    # Bước 2: tra Distiller theo library_type (KHÔNG theo entity_type thô
    # — xem mục 0.1 tài liệu Architect)
    distiller_cls = DistillerRegistry.get(library_type)
    if distiller_cls is None:
        logger.warning(
            f"⚠️ [Gate 6.5] '{visual_id}' — library_type={library_type!r} đã "
            f"route thành công NHƯNG chưa có Distiller implement (gap thiếu "
            f"code, khác gap thiếu nguồn harvest ở trên) — reject khỏi "
            f"lib_entities, cần bổ sung distillers/{library_type}.py + "
            f"register() trong distillers/registry.py."
        )
        return None

    # Bước 3: distill — template method lo toàn bộ phần còn lại
    distiller = distiller_cls()
    return distiller.distill(doc, budget=budget, obs=obs)


def run_library_distill(
    deduped_docs: List[dict],
    budget=None,
    obs=None,
) -> List[dict]:
    """Gate 6.5 — Library Distillation: loop qua deduped_docs, gọi
    distill_one() cho từng doc, GẮN kết quả ngược lại vào chính doc đó
    dưới key \"lib_record\" (None nếu distill_one trả None).

    Quan trọng: MUTATE IN-PLACE deduped_docs (không tạo list riêng) để
    t5_upload.py đọc lib_record từ cùng 1 doc → giữ 3-phase transaction
    trên 1 entity.

    Returns:
        Chính deduped_docs (đã mutate in-place) — convention giống
        t4_deduplicate.deduplicate() trả về List[deduped_documents].
    """
    total = len(deduped_docs)
    routed = 0
    complete_count = 0

    for doc in deduped_docs:
        lib_record = distill_one(doc, budget=budget, obs=obs)
        doc["lib_record"] = lib_record  # None nếu route thất bại
        if lib_record is not None:
            routed += 1
            if lib_record.get("status") == "complete":
                complete_count += 1

    logger.info(
        f"✅ [Gate 6.5] Library Distillation hoàn thành — "
        f"{routed}/{total} document có lib_record "
        f"({complete_count} complete, {routed - complete_count} incomplete)."
    )
    return deduped_docs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
