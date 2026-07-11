"""
core/quality_scorer.py — Quality Scorer (SOFT / OBSERVABILITY) cho Gate 5
============================================================================
- Chấm điểm 0-100 cho 1 record ĐÃ SỐNG SÓT qua Check A/C/G/F của Gate 5
  (t3_normalize.validate_combined_output). Không tự gọi ở đâu khác.
- KHÔNG BAO GIỜ raise. KHÔNG BAO GIỜ tự set reject_reason — đây không phải
  Check H. Điểm số chỉ dùng để (a) set quality_gate_passed (field đã có sẵn
  trong schema, xem config.MASTER_SCHEMA_2_0.provenance_and_metadata),
  (b) observability qua quality_gate_report, (c) xếp hạng gap-filling ở
  Repo 4 (đọc log, không đọc field mới trong Mongo — xem §0 mục 3 spec TL).
- Trọng số/băng điểm 100% config-driven (QUALITY_SCORE_WEIGHTS,
  ALL_VIEW_SLOTS, IP_CLEANLINESS_SCORE_MAP, PROMPT_DEPTH_BANDS,
  QUALITY_SCORE_PASS_THRESHOLD trong config.py) — không hardcode số trong
  file này, đúng nguyên tắc Layer 0 của config.py.
"""
from __future__ import annotations

from typing import Optional

import config as _config


def _score_view_completeness(blueprint: dict, cfg) -> int:
    """(0–30) Tỉ lệ view slot có mặt trên tổng số ALL_VIEW_SLOTS."""
    mvr = blueprint.get("multi_view_references", {}) or {}
    slots = cfg.ALL_VIEW_SLOTS
    present = sum(1 for v in slots if mvr.get(v))
    if not slots:
        return 0
    return round(present / len(slots) * cfg.QUALITY_SCORE_WEIGHTS["view_completeness"])


def _score_ip_cleanliness(schema_record: Optional[dict], cfg) -> int:
    """(0–20) Dựa trên provenance_and_metadata.ip_filter_status /
    .original_ip_detected. schema_record=None (Gate 4 chưa gắn) -> 0 điểm,
    không crash."""
    if not schema_record:
        return 0
    prov = schema_record.get("provenance_and_metadata", {}) or {}
    status = prov.get("ip_filter_status", "unverified")
    detected = prov.get("original_ip_detected") or []

    if status == "cleaned" and not detected:
        key = "cleaned_no_ip_detected"
    elif status == "cleaned" and detected:
        key = "cleaned_but_ip_found"
    elif status in cfg.IP_CLEANLINESS_SCORE_MAP:
        key = status
    else:
        key = "unverified"  # giá trị lạ/không hợp lệ -> fail-safe về mức thấp nhất có nghĩa

    return cfg.IP_CLEANLINESS_SCORE_MAP[key]


def _score_prompt_depth(blueprint: dict, cfg) -> int:
    """(0–20) Dải điểm graduated theo độ dài pre_built_prompts.full_character,
    đọc SAU khi Check D (t3_normalize.py) đã truncate nếu quá dài."""
    prompt = (blueprint.get("pre_built_prompts", {}) or {}).get("full_character", "") or ""
    length = len(prompt)
    for lo, hi, points in cfg.PROMPT_DEPTH_BANDS:
        if lo <= length < hi:
            return points
    return 0  # fallback an toàn nếu bands không phủ hết (không nên xảy ra)


def _score_schema_completeness(schema_record: Optional[dict], cfg) -> int:
    """(0–30) Tỉ lệ leaf field (form_1 + form_2) được điền, tái sử dụng
    config.get_form_fields() — không hardcode field."""
    if not schema_record:
        return 0
    all_leaf_fields = (
        cfg.get_form_fields("form_1_planet_foundation")
        + cfg.get_form_fields("form_2_civilization_layer")
    )
    if not all_leaf_fields:
        return 0

    filled = 0
    for dotted_path in all_leaf_fields:
        # dotted_path đã bao gồm prefix form_name (vd:
        # "form_1_planet_foundation.planet_identity.terrain_patterns"),
        # y hệt output của config.get_form_fields() — dùng lại logic
        # duyệt dot-path giống _get_nested() của t3_normalize.py.
        value = schema_record
        for key in dotted_path.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value not in ("", [], None):
            filled += 1

    return round(filled / len(all_leaf_fields) * cfg.QUALITY_SCORE_WEIGHTS["schema_completeness"])


def compute_quality_score(
    blueprint: dict,
    schema_record: Optional[dict],
    cfg=None,
) -> dict:
    """
    Chấm điểm 1 record ĐÃ QUA Check A/C/G/F (reject_reason is None). KHÔNG
    gọi hàm này cho record đã bị reject — không có ý nghĩa và lãng phí.

    Args:
        blueprint: VisualBlueprint30 đã model_dump() (dict), lấy từ
            result["blueprint"] của validate_combined_output().
        schema_record: MasterSchema20 dict, HOẶC None nếu Gate 4 (t4) chưa
            gắn được — không crash trong trường hợp này, score_D = 0.
        cfg: cho phép tiêm config khác khi test (giống mọi hàm khác trong
            t3_normalize.py) — mặc định dùng module config.py thật.

    Returns:
        {
          "total": int,                 # 0-100, clamp
          "breakdown": {
              "view_completeness": int,
              "ip_cleanliness": int,
              "prompt_depth": int,
              "schema_completeness": int,
          },
          "passed_threshold": bool,     # total >= cfg.QUALITY_SCORE_PASS_THRESHOLD
        }

    KHÔNG raise trong bất kỳ trường hợp nào — mọi field thiếu/None đều được
    .get() với default an toàn (giống style check_b_multi_view_completeness).
    """
    cfg = cfg or _config

    score_a = _score_view_completeness(blueprint, cfg)
    score_b = _score_ip_cleanliness(schema_record, cfg)
    score_c = _score_prompt_depth(blueprint, cfg)
    score_d = _score_schema_completeness(schema_record, cfg)

    total = max(0, min(100, score_a + score_b + score_c + score_d))

    return {
        "total": total,
        "breakdown": {
            "view_completeness": score_a,
            "ip_cleanliness": score_b,
            "prompt_depth": score_c,
            "schema_completeness": score_d,
        },
        "passed_threshold": total >= cfg.QUALITY_SCORE_PASS_THRESHOLD,
    }
