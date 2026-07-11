"""
rule_library.py — Global Rule Library client & evaluation engine
==================================================================
Chỉ đọc từ collection `world_rule_library` (MongoDB 1). Không Agent nào
trong t0..t5 được ghi vào collection này — việc thêm/sửa rule thuộc về
manage_rules.py (CLI thủ công, ngoài luồng pipeline tự động).

Nguyên tắc fail-open: nếu không load được rule (Mongo offline / collection
rỗng / lỗi query), trả về [] và log WARNING — KHÔNG raise, KHÔNG làm sập
Gate 5.

MVP chỉ hỗ trợ rule_type == "forbidden_term_combo". Rule_type khác (Phase 2:
field_condition, required_term_if) bị bỏ qua có log INFO, KHÔNG raise.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import config as _config

logger = logging.getLogger(__name__)

SUPPORTED_RULE_TYPES = frozenset({"forbidden_term_combo"})


def load_active_rules(
    db, entity_scope: Optional[str] = None
) -> Tuple[List[dict], bool]:
    """Load toàn bộ rule active, lọc theo entity_scope nếu có.

    Trả về (rules, rule_check_skipped). `rule_check_skipped=True` CHỈ khi
    Mongo offline/lỗi query (case fail-open thật sự) — KHÔNG True khi
    Mongo OK nhưng collection rỗng (0 rule active là trạng thái hợp lệ,
    không phải lỗi).

    Gọi hàm này ĐÚNG 1 LẦN mỗi chu kỳ pipeline (ở main.py, trước vòng lặp
    Gate 5), không gọi lại cho từng blueprint riêng lẻ.
    """
    if db is None:
        logger.warning(
            "⚠️ [RuleLibrary] Không có kết nối MongoDB — chạy Gate 5 "
            "KHÔNG có Global Rule Cross-Check (fail-open)."
        )
        return [], True

    try:
        coll = db[_config.MONGO_TARGET_COLLECTIONS["world_rule_library"]]
        query: dict = {"active": True}
        if entity_scope:
            query["entity_scope"] = entity_scope
        rules = list(coll.find(query))
        logger.info(
            f"✅ [RuleLibrary] Đã load {len(rules)} rule active (scope={entity_scope})."
        )
        return rules, False
    except Exception as e:
        logger.warning(f"⚠️ [RuleLibrary] Lỗi khi load rule — fail-open, dùng []: {e}")
        return [], True


def evaluate_rule(rule: dict, blueprint: dict) -> Optional[dict]:
    """Đánh giá 1 rule trên 1 blueprint. Trả về dict "hit" nếu vi phạm,
    None nếu không vi phạm hoặc rule_type chưa hỗ trợ."""
    rule_type = rule.get("rule_type")

    if rule_type == "forbidden_term_combo":
        terms = rule.get("condition", {}).get("terms", [])
        if not terms:
            return None
        blueprint_serialized = str(blueprint).lower()
        if all(str(term).lower() in blueprint_serialized for term in terms):
            return {
                "rule_id": rule.get("rule_id"),
                "severity": rule.get("severity", "WARNING"),
                "message": rule.get("message", ""),
                "suggestion": rule.get("suggestion", ""),
            }
        return None

    if rule_type not in SUPPORTED_RULE_TYPES:
        logger.info(
            f"ℹ️ [RuleLibrary] rule_id='{rule.get('rule_id')}' có rule_type="
            f"'{rule_type}' chưa được hỗ trợ ở MVP — bỏ qua."
        )
    return None


def evaluate_all(rules: List[dict], blueprint: dict) -> List[dict]:
    """Đánh giá toàn bộ rule list trên 1 blueprint, trả về list các hit
    (rỗng nếu không vi phạm gì). Không raise — 1 rule lỗi format không
    được làm hỏng đánh giá các rule còn lại."""
    hits = []
    for rule in rules:
        try:
            hit = evaluate_rule(rule, blueprint)
        except Exception as e:
            logger.warning(
                f"⚠️ [RuleLibrary] Lỗi khi evaluate rule_id="
                f"'{rule.get('rule_id')}' — bỏ qua rule này: {e}"
            )
            continue
        if hit:
            hits.append(hit)
    return hits
