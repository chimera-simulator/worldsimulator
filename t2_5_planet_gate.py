"""
t2_5_planet_gate.py — Agent 3.5: Planet-Scoped Aggregate Gate (T2.5)
=======================================================================
[CX — theo SPEC_ADDENDUM_2_7_T2_5_PLANET_GATE_MERGED_v2.md mục 3 + 5]
- Chạy SAU t2_scrape.py (Gate 2, per-URL), TRƯỚC summarizer.py (Gemini).
  Gate 2 không thấy được bức tranh cả batch/field; T2.5 mới có đủ dữ
  liệu để quyết định "có đáng tốn Gemini không" ở cấp field/batch.
- 4 nhiệm vụ: (1) dedupe raw_text sớm theo target_form_field, (2) đếm
  doc còn lại theo NHÓM library_type (bảng TARGET_FORM_FIELD_TO_LIBRARY_TYPE,
  6 nhóm: flora/planet/species/architecture/technology/culture) để xác
  định field nào "insufficient", (3) quyết định send_to_t3, (4) để
  main.py factor retry qua state machine sẵn có (_mark_planet_retry_or_fail),
  KHÔNG tự làm retry ở đây — module này chỉ trả decision_report.
- KHÔNG gọi LLM, KHÔNG parse Gemini output — thuần rule-based như Gate 2.

Import ranh giới (đúng SPEC — "chỉ import, không sửa"):
- `compute_prompt_similarity` từ t4_deduplicate.py (TF-IDF cosine + fallback
  Jaccard khi sklearn lỗi/không có sẵn).
- `TARGET_FORM_FIELD_TO_LIBRARY_TYPE` từ library_routing.py (bảng routing
  prefix->library_type, CHỈ ĐỌC — không phải route_library_type() của Gate
  6.5, vì hàm đó dùng cho schema_record ĐÃ qua Gemini/dedupe, khác ngữ
  cảnh raw ScrapedDocument ở đây; T2.5 tự làm phép match prefix riêng bên
  dưới trên đúng field `target_form_field` — cùng convention dot-path đầy
  đủ mà t0_search.py sinh ra qua `config.get_form_fields()`).
- 2 hằng số ngưỡng `RAW_TEXT_DEDUP_THRESHOLD`, `MIN_DOCS_PER_FIELD` từ
  config.py (đã được Coder 1 thêm).

Danh sách 4 field KHÔNG có route (hard-code tại đây theo đúng SPEC —
KHÔNG thêm vào library_routing.py, file đó chỉ chứa bảng routing, không
phải danh sách loại trừ): transportation_patterns, government_patterns,
economic_patterns, military_patterns (đều thuộc
form_2_civilization_layer.society_and_infrastructure.*). 4 field này bị
loại khỏi MỌI gate (không tính insufficient_fields, không trigger retry,
không chặn send_to_t3) — nhưng KHÔNG bị drop khỏi batch: doc thuộc 4 field
này vẫn được coi là "đủ điều kiện" mặc định và đi tiếp cùng các field đủ
điều kiện khác khi send_to_t3=True (chỉ khi TOÀN BỘ field CÓ route đều
insufficient thì send_to_t3=False mới cắt luôn cả các doc này — do
main.py return sớm 0 document trong nhánh đó, xem mục 4 SPEC). Điều này
khớp với chú thích SPEC "T0 vẫn tiếp tục tìm như hiện trạng, quota
T0/T2/T3 cho 4 field này vẫn bị tiêu — chấp nhận được ở phạm vi lần này".
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from config import MIN_DOCS_PER_FIELD, RAW_TEXT_DEDUP_THRESHOLD
from library_routing import TARGET_FORM_FIELD_TO_LIBRARY_TYPE
from t4_deduplicate import compute_prompt_similarity

# [MỚI] Import ScrapedDocument CHỈ cho type-checking (không ở runtime) — file
# này KHÔNG được phép kéo theo dependency httpx/bs4 của t2_scrape.py chỉ để
# dùng 1 TypedDict thuần (t2_5_planet_gate.py chỉ xử lý dict thuần, không
# gọi bất kỳ hàm nào của t2_scrape.py). Tránh vỡ import ở môi trường CI/test
# chưa cài httpx (đúng pattern SKIP đã dùng ở
# tests/test_t2_5_coder1_scrape_fields.py cho chính t2_scrape.py).
if TYPE_CHECKING:  # pragma: no cover
    from t2_scrape import ScrapedDocument
else:
    ScrapedDocument = Dict[str, object]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# [SPEC_ADDENDUM_2_7 mục 3, nhiệm vụ 2] 4 field KHÔNG xuất hiện trong
# TARGET_FORM_FIELD_TO_LIBRARY_TYPE (cũng không có trong
# ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE) — dot-path đầy đủ đúng convention
# config.get_form_fields() (verify: config.py MASTER_SCHEMA_2_0,
# form_2_civilization_layer.society_and_infrastructure.*).
# ---------------------------------------------------------------------------
NO_ROUTE_FORM_FIELDS: frozenset[str] = frozenset(
    {
        "form_2_civilization_layer.society_and_infrastructure.transportation_patterns",
        "form_2_civilization_layer.society_and_infrastructure.government_patterns",
        "form_2_civilization_layer.society_and_infrastructure.economic_patterns",
        "form_2_civilization_layer.society_and_infrastructure.military_patterns",
    }
)


def _route_library_type(target_form_field: str) -> Optional[str]:
    """Match `target_form_field` (dot-path đầy đủ) theo PREFIX của
    TARGET_FORM_FIELD_TO_LIBRARY_TYPE, dừng ở match đầu tiên — CÙNG logic
    match với route_library_type() của Gate 6.5 (t4_5_library_distill.py),
    nhưng KHÔNG có fallback theo entity_type/clothing_and_gear (không áp
    dụng ở raw ScrapedDocument, chưa có blueprint) và KHÔNG import hàm đó
    trực tiếp (khác ngữ cảnh input theo đúng ranh giới SPEC).

    Trả về None nếu không match — bao gồm cả 4 field trong
    NO_ROUTE_FORM_FIELDS (không match bất kỳ prefix nào trong bảng, đã
    verify tại library_routing.py) lẫn field lạ/rỗng ngoài dự kiến.
    """
    if not target_form_field:
        return None
    for prefix, library_type in TARGET_FORM_FIELD_TO_LIBRARY_TYPE:
        if target_form_field.startswith(prefix):
            return library_type
    return None


def _is_no_route_field(target_form_field: str) -> bool:
    """True nếu field bị loại khỏi mọi gate (mục 3 nhiệm vụ 2 SPEC).

    Ưu tiên khớp đúng 4 field đã hard-code (hard-code theo yêu cầu SPEC,
    tường minh, không phụ thuộc ngầm vào việc bảng routing "tình cờ"
    không match). Dự phòng thêm: bất kỳ field nào khác cũng không match
    được prefix nào (route trả None) được xử lý CÙNG như no-route, để
    không có document nào bị "kẹt" tính sai insufficient_fields chỉ vì
    một field lạ ngoài 6 nhóm + 4 field loại trừ đã biết.
    """
    if target_form_field in NO_ROUTE_FORM_FIELDS:
        return True
    return _route_library_type(target_form_field) is None


def _better_of(doc_a: ScrapedDocument, doc_b: ScrapedDocument) -> Tuple[ScrapedDocument, ScrapedDocument]:
    """Trả (doc_giữ, doc_drop) khi 2 doc bị coi là trùng lặp.

    "Giữ bản dài hơn/nhiều ảnh hơn" (SPEC mục 3, nhiệm vụ 1) — so sánh
    theo tuple (len(raw_text), số ảnh), ưu tiên độ dài text trước vì đó
    là tín hiệu chính cho similarity/dedupe raw_text; số ảnh dùng làm
    tiêu chí phụ khi độ dài text bằng nhau.
    """
    score_a = (len(doc_a.get("raw_text", "")), len(doc_a.get("image_metadata", [])))
    score_b = (len(doc_b.get("raw_text", "")), len(doc_b.get("image_metadata", [])))
    if score_a >= score_b:
        return doc_a, doc_b
    return doc_b, doc_a


def _dedupe_raw_text(
    scraped_docs: List[ScrapedDocument],
) -> Tuple[List[ScrapedDocument], int]:
    """Nhiệm vụ 1: dedupe raw_text sớm, so cặp TRONG CÙNG target_form_field.

    Tái dùng `compute_prompt_similarity()` (TF-IDF cosine + fallback
    Jaccard) trên `raw_text` thô — dùng ngưỡng riêng
    `RAW_TEXT_DEDUP_THRESHOLD`, KHÔNG dùng `DEDUP_SIMILARITY_THRESHOLD`
    (ngưỡng đó tính cho prompt đã qua LLM chuẩn hoá).

    Convention so sánh giống `t4_deduplicate.deduplicate()`: coi là trùng
    khi `similarity >= threshold` (ngưỡng là "đạt mức trùng", không phải
    cận trên loại trừ).

    O(n^2) trong từng nhóm field — batch T2.5 thường nhỏ (vài chục URL/
    field/chu kỳ 25 phút), chấp nhận được, không cần tối ưu thêm ở lần
    này.
    """
    by_field: Dict[str, List[int]] = defaultdict(list)
    for idx, doc in enumerate(scraped_docs):
        by_field[doc.get("target_form_field", "")].append(idx)

    dropped_indices: set = set()

    for _field, indices in by_field.items():
        for i in range(len(indices)):
            idx_a = indices[i]
            if idx_a in dropped_indices:
                continue
            for j in range(i + 1, len(indices)):
                idx_b = indices[j]
                if idx_b in dropped_indices:
                    continue

                similarity = compute_prompt_similarity(
                    scraped_docs[idx_a].get("raw_text", ""),
                    scraped_docs[idx_b].get("raw_text", ""),
                )
                if similarity >= RAW_TEXT_DEDUP_THRESHOLD:
                    keep_doc, drop_doc = _better_of(scraped_docs[idx_a], scraped_docs[idx_b])
                    drop_idx = idx_a if drop_doc is scraped_docs[idx_a] else idx_b
                    dropped_indices.add(drop_idx)
                    if drop_idx == idx_a:
                        # idx_a vừa bị drop — không còn gì để so tiếp với nó.
                        break

    kept_docs = [doc for idx, doc in enumerate(scraped_docs) if idx not in dropped_indices]
    return kept_docs, len(dropped_indices)


def run_planet_gate(
    scraped_docs: List[ScrapedDocument],
    working_planet_id: str,
    archetype_id: str,
    blackbook: dict,
    budget=None,
    obs=None,
) -> Tuple[List[ScrapedDocument], dict]:
    """T2.5 — Planet-Scoped Aggregate Gate.

    Args:
        scraped_docs: output của t2_scrape.run_scrape_pipeline() (đã qua
            Gate 2 per-URL).
        working_planet_id / archetype_id: gắn sẵn trên từng ScrapedDocument
            (Coder 1), truyền riêng ở đây để tương lai module có thể dùng
            cho log/lookup mà không cần lục lại từ doc đầu tiên — hiện tại
            CHƯA dùng trong logic gate (gate hoạt động thuần trên
            target_form_field/raw_text/image_metadata của batch nhận vào,
            đúng phạm vi mục 3 SPEC — không query DB/blackbook theo 2 tham
            số này).
        blackbook: giữ đúng chữ ký SPEC cho tương lai (VD: nếu cần tra cứu
            trạng thái planet); T2.5 KHÔNG tự ghi retry vào blackbook ở
            đây — đó là việc của `_mark_planet_retry_or_fail()` do main.py
            gọi (nhiệm vụ 4 SPEC, thuộc phạm vi Coder 3).
        budget / obs: giữ đúng chữ ký để tương lai gắn budget-tracking/
            logging riêng cho T2.5 nếu cần; KHÔNG bắt buộc ở phạm vi SPEC
            này (main.py tự log `obs.event(step="T2_5_PLANET_GATE", ...)`
            sau khi gọi hàm này — xem mục 4 SPEC).

    Returns:
        (gated_docs, decision_report) với:
        decision_report = {
            "send_to_t3": bool,
            "retry_triggered": bool,
            "duplicate_dropped": int,
            "insufficient_fields": List[str],
        }
    """
    # --- Nhiệm vụ 1: dedupe raw_text sớm -----------------------------------
    deduped_docs, duplicate_dropped = _dedupe_raw_text(scraped_docs)

    # --- Nhiệm vụ 2: đếm doc/nhóm field sau dedupe -------------------------
    # routed_group_docs: library_type -> list[ScrapedDocument] (chỉ field CÓ
    # route). no_route_docs: doc thuộc 4 field bị loại khỏi mọi gate (hoặc
    # field lạ không match — xem _is_no_route_field), luôn coi là "đủ điều
    # kiện" mặc định.
    routed_group_docs: Dict[str, List[ScrapedDocument]] = defaultdict(list)
    # routed_group_fields: library_type -> set(target_form_field) THẬT SỰ có
    # mặt trong batch này — dùng để trả insufficient_fields theo đúng field
    # dot-path (định dạng mà t0_search.py/`_mark_planet_retry_or_fail`
    # dùng để tra lại/tìm bù), KHÔNG trả tên nhóm library_type (nhóm chỉ là
    # đơn vị đếm nội bộ, không phải field name hợp lệ cho t0_search).
    routed_group_fields: Dict[str, set] = defaultdict(set)
    no_route_docs: List[ScrapedDocument] = []

    for doc in deduped_docs:
        field = doc.get("target_form_field", "")
        if _is_no_route_field(field):
            no_route_docs.append(doc)
            continue
        library_type = _route_library_type(field)
        routed_group_docs[library_type].append(doc)
        routed_group_fields[library_type].add(field)

    insufficient_fields: List[str] = []
    sufficient_routed_docs: List[ScrapedDocument] = []
    any_routed_group = bool(routed_group_docs)
    all_routed_insufficient = True

    for library_type, docs in routed_group_docs.items():
        if len(docs) < MIN_DOCS_PER_FIELD:
            insufficient_fields.extend(sorted(routed_group_fields[library_type]))
        else:
            all_routed_insufficient = False
            sufficient_routed_docs.extend(docs)

    insufficient_fields = sorted(set(insufficient_fields))

    # --- Nhiệm vụ 3: quyết định send_to_t3 ---------------------------------
    # Toàn bộ field CÓ route đều insufficient (hoặc không có field nào có
    # route trong batch này) -> send_to_t3=False, bỏ T3/T4/T5 hoàn toàn chu
    # kỳ này (main.py return sớm — mục 4 SPEC). Nếu KHÔNG có field nào có
    # route trong cả batch (chỉ toàn field loại trừ), coi như "không đủ dữ
    # liệu có route để gửi" -> vẫn False, khớp tinh thần "chỉ gửi doc thuộc
    # field đủ điều kiện" (không field nào được xác nhận đủ điều kiện).
    send_to_t3 = any_routed_group and not all_routed_insufficient

    if send_to_t3:
        gated_docs = sufficient_routed_docs + no_route_docs
    else:
        gated_docs = []

    decision_report = {
        "send_to_t3": send_to_t3,
        "retry_triggered": not send_to_t3,
        "duplicate_dropped": duplicate_dropped,
        "insufficient_fields": insufficient_fields,
    }

    logger.info(
        f"✅ [T2.5] Planet gate hoàn thành cho working_planet_id='{working_planet_id}' "
        f"(archetype='{archetype_id}') — send_to_t3={send_to_t3}, "
        f"duplicate_dropped={duplicate_dropped}, "
        f"insufficient_fields={len(insufficient_fields)}, "
        f"gated_docs={len(gated_docs)}/{len(scraped_docs)}."
    )

    return gated_docs, decision_report
