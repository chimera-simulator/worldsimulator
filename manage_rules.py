"""
manage_rules.py — CLI quản trị Global Rule Library (collection
`world_rule_library`, MongoDB 1).

KHÔNG phải Agent t0-t5 — chạy tay, ngoài GitHub Actions cron. Không Agent
nào trong pipeline tự động được ghi vào collection này; mọi thêm/sửa/tắt
rule đi qua đây, có audit trail (`source`, `created_at`/`updated_at`).

Usage:
    python3 manage_rules.py list [--scope SCOPE]
    python3 manage_rules.py add --rule-id ID --scope SCOPE [--scope SCOPE ...] \
        --type forbidden_term_combo --severity ERROR|WARNING|INFO \
        --terms "term1,term2" --message "..." [--suggestion "..."] \
        [--source manual] [--active | --no-active]
    python3 manage_rules.py deactivate --rule-id ID
    python3 manage_rules.py bump-version --rule-id ID
    python3 manage_rules.py seed          # seed 3 rule mẫu migrate từ legacy/rule_engine.py

Fail-open KHÔNG áp dụng ở đây (khác với rule_library.py) — đây là CLI thủ
công chạy tay, lỗi Mongo phải báo rõ ràng cho người vận hành, KHÔNG được
âm thầm nuốt lỗi.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import List, Optional

import config as _config
from mongo_shared import get_shared_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_SEVERITIES = ("ERROR", "WARNING", "INFO")


def _rule_collection(db):
    return db[_config.MONGO_TARGET_COLLECTIONS["world_rule_library"]]


def add_rule(
    db,
    rule_id: str,
    entity_scope: List[str],
    rule_type: str,
    severity: str,
    condition: dict,
    message: str,
    suggestion: str = "",
    source: str = "manual",
    active: bool = False,
) -> bool:
    """Thêm 1 rule mới. Mặc định `active=False` — người vận hành phải chủ
    động kích hoạt sau khi review (xem §7 rủi ro #5 trong spec: rule ERROR
    reject cứng toàn hệ thống, không nên auto-active khi mới tạo)."""
    if severity not in VALID_SEVERITIES:
        logger.error(f"❌ severity không hợp lệ: '{severity}' (phải là {VALID_SEVERITIES}).")
        return False

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "rule_id": rule_id,
        "version": 1,
        "entity_scope": entity_scope,
        "rule_type": rule_type,
        "severity": severity,
        "condition": condition,
        "message": message,
        "suggestion": suggestion,
        "source": source,
        "active": active,
        "created_at": now,
        "updated_at": now,
    }
    try:
        _rule_collection(db).insert_one(doc)
        logger.info(f"✅ Đã thêm rule '{rule_id}' (active={active}).")
        return True
    except Exception as e:
        logger.error(f"❌ Không thể thêm rule '{rule_id}': {e}")
        return False


def deactivate_rule(db, rule_id: str) -> bool:
    try:
        result = _rule_collection(db).update_one(
            {"rule_id": rule_id},
            {"$set": {"active": False, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        if result.matched_count == 0:
            logger.warning(f"⚠️ Không tìm thấy rule_id='{rule_id}'.")
            return False
        logger.info(f"✅ Đã deactivate rule '{rule_id}'.")
        return True
    except Exception as e:
        logger.error(f"❌ Không thể deactivate rule '{rule_id}': {e}")
        return False


def activate_rule(db, rule_id: str) -> bool:
    """Kích hoạt 1 rule sau khi đã review (không có trong §6 gốc nhưng cần
    thiết để đối xứng với deactivate_rule — không đổi 4 hàm bắt buộc)."""
    try:
        result = _rule_collection(db).update_one(
            {"rule_id": rule_id},
            {"$set": {"active": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        if result.matched_count == 0:
            logger.warning(f"⚠️ Không tìm thấy rule_id='{rule_id}'.")
            return False
        logger.info(f"✅ Đã activate rule '{rule_id}'.")
        return True
    except Exception as e:
        logger.error(f"❌ Không thể activate rule '{rule_id}': {e}")
        return False


def list_rules(db, scope: Optional[str] = None) -> List[dict]:
    try:
        query: dict = {}
        if scope:
            query["entity_scope"] = scope
        return list(_rule_collection(db).find(query))
    except Exception as e:
        logger.error(f"❌ Không thể list rule (scope={scope}): {e}")
        return []


def bump_version(db, rule_id: str) -> bool:
    try:
        result = _rule_collection(db).update_one(
            {"rule_id": rule_id},
            {
                "$inc": {"version": 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            },
        )
        if result.matched_count == 0:
            logger.warning(f"⚠️ Không tìm thấy rule_id='{rule_id}'.")
            return False
        logger.info(f"✅ Đã bump version rule '{rule_id}'.")
        return True
    except Exception as e:
        logger.error(f"❌ Không thể bump version rule '{rule_id}': {e}")
        return False


# =============================================================================
# SEED — 3 rule migrate từ legacy/rule_engine.py (xem §6 spec).
#
# LƯU Ý QUAN TRỌNG (§6/§7 rủi ro #1): match là substring, KHÔNG word-
# boundary. RULE-ENV-001 dùng term "snow" — có thể false-positive với cụm
# như "no snow" / "snow-free terrain". Vì vậy 3 rule seed dưới đây được tạo
# với active=False theo mặc định của add_rule(); PHẢI review + activate
# thủ công (activate_rule) sau khi rà lại thuật toán match, KHÔNG auto-active
# ở đây.
# =============================================================================
SEED_RULES = [
    {
        "rule_id": "RULE-MC-001",
        "entity_scope": ["character", "mc"],
        "rule_type": "forbidden_term_combo",
        "severity": "ERROR",
        "condition": {"terms": ["mc_female", "heavy armor"]},
        "message": (
            "MC nữ không được mặc giáp hạng nặng (vi phạm quy tắc bất biến "
            "của MC — mục 103.2 tài liệu gốc)."
        ),
        "suggestion": "Bỏ heavy armor khỏi clothing_and_gear của MC nữ, hoặc đổi material sang loại nhẹ hơn.",
        "source": "migrated_from_legacy_rule_engine",
    },
    {
        "rule_id": "RULE-PLANET-001",
        "entity_scope": ["planet"],
        "rule_type": "forbidden_term_combo",
        "severity": "ERROR",
        "condition": {"terms": ["desert", "tropical rainforest"]},
        "message": "Một hành tinh/khu vực không thể vừa là desert vừa là tropical rainforest cùng lúc.",
        "suggestion": "Chọn 1 biome chính, hoặc tách thành 2 khu vực địa lý riêng biệt.",
        "source": "migrated_from_legacy_rule_engine",
    },
    {
        "rule_id": "RULE-ENV-001",
        "entity_scope": ["environment", "planet"],
        "rule_type": "forbidden_term_combo",
        "severity": "WARNING",
        "condition": {"terms": ["desert", "snow"]},
        "message": "Desert kèm snow bất thường trừ khi planet đã khai báo rõ vùng khí hậu lạnh.",
        "suggestion": "Xác nhận lại climate_zone của planet, hoặc tách thành 2 biome riêng.",
        "source": "migrated_from_legacy_rule_engine",
    },
]


def seed_rules(db) -> None:
    for spec in SEED_RULES:
        ok = add_rule(
            db,
            rule_id=spec["rule_id"],
            entity_scope=spec["entity_scope"],
            rule_type=spec["rule_type"],
            severity=spec["severity"],
            condition=spec["condition"],
            message=spec["message"],
            suggestion=spec["suggestion"],
            source=spec["source"],
            active=False,
        )
        if not ok:
            logger.warning(f"⚠️ Seed '{spec['rule_id']}' thất bại hoặc đã tồn tại — bỏ qua.")
    logger.info(
        "✅ Seed hoàn tất — 3 rule đã tạo với active=False. Rà lại thuật "
        "toán match (đặc biệt RULE-ENV-001, xem §7 rủi ro #1) TRƯỚC khi "
        "activate_rule() từng rule."
    )


# =============================================================================
# CLI
# =============================================================================
def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quản trị Global Rule Library (world_rule_library).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Liệt kê rule (tuỳ chọn lọc theo scope).")
    p_list.add_argument("--scope", default=None)

    p_add = sub.add_parser("add", help="Thêm 1 rule mới (mặc định active=False).")
    p_add.add_argument("--rule-id", required=True)
    p_add.add_argument("--scope", action="append", required=True, dest="entity_scope")
    p_add.add_argument("--type", default="forbidden_term_combo", dest="rule_type")
    p_add.add_argument("--severity", required=True, choices=VALID_SEVERITIES)
    p_add.add_argument("--terms", required=True, help="Danh sách term, phân cách bởi dấu phẩy.")
    p_add.add_argument("--message", required=True)
    p_add.add_argument("--suggestion", default="")
    p_add.add_argument("--source", default="manual")
    p_add.add_argument("--active", action="store_true")

    p_deact = sub.add_parser("deactivate", help="Deactivate 1 rule theo rule_id.")
    p_deact.add_argument("--rule-id", required=True)

    p_act = sub.add_parser("activate", help="Activate 1 rule theo rule_id (sau khi review).")
    p_act.add_argument("--rule-id", required=True)

    p_bump = sub.add_parser("bump-version", help="Tăng version 1 rule theo rule_id.")
    p_bump.add_argument("--rule-id", required=True)

    sub.add_parser("seed", help="Seed 3 rule mẫu migrate từ legacy/rule_engine.py (active=False).")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    db = get_shared_db()
    if db is None:
        logger.error("❌ Không kết nối được MongoDB — không thể chạy manage_rules.py.")
        return 1

    if args.command == "list":
        rules = list_rules(db, scope=args.scope)
        for r in rules:
            print(
                f"{r.get('rule_id'):<18} v{r.get('version')} "
                f"scope={r.get('entity_scope')} severity={r.get('severity')} "
                f"active={r.get('active')} terms={r.get('condition', {}).get('terms')}"
            )
        print(f"— {len(rules)} rule.")
        return 0

    if args.command == "add":
        terms = [t.strip() for t in args.terms.split(",") if t.strip()]
        ok = add_rule(
            db,
            rule_id=args.rule_id,
            entity_scope=args.entity_scope,
            rule_type=args.rule_type,
            severity=args.severity,
            condition={"terms": terms},
            message=args.message,
            suggestion=args.suggestion,
            source=args.source,
            active=args.active,
        )
        return 0 if ok else 1

    if args.command == "deactivate":
        return 0 if deactivate_rule(db, args.rule_id) else 1

    if args.command == "activate":
        return 0 if activate_rule(db, args.rule_id) else 1

    if args.command == "bump-version":
        return 0 if bump_version(db, args.rule_id) else 1

    if args.command == "seed":
        seed_rules(db)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
