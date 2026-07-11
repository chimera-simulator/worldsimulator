"""
MONGO_SHARED — Client MongoDB & cache hash dùng chung toàn tiến trình
======================================================================
[CẬP NHẬT — Repo 1 Visual-First] Không đổi logic connection hiện có (1
MongoClient duy nhất cho toàn tiến trình, đóng trong finally của main.py).
Chỉ THÊM reference tới 2 collection mới (visual_blueprint_collection,
fiction_knowledge) qua config.MONGO_TARGET_COLLECTIONS, dùng bởi t5_upload.py.

Repo 1 không còn tham chiếu collection "world_rules" dưới bất kỳ hình thức
nào — logic đó đã bị xoá hoàn toàn cùng đợt dọn dead code sang legacy/.
"""
import logging

from config import MONGO_TARGET_COLLECTIONS, MONGODB_DB_NAME, MONGODB_URI

logger = logging.getLogger(__name__)

_client = None
_db = None


def get_shared_client():
    """Trả về MongoClient dùng chung — chỉ tạo mới nếu chưa có hoặc chưa
    kết nối được (MONGODB_URI rỗng). Idempotent qua nhiều lần gọi."""
    global _client
    if _client is not None:
        return _client

    if not MONGODB_URI:
        return None

    try:
        from pymongo import MongoClient

        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        logger.info("✅ MongoDB connected (shared client — dùng chung toàn tiến trình).")
    except Exception as e:
        logger.warning(f"⚠️ MongoDB connection failed (shared client): {e}")
        _client = None

    return _client


def get_shared_db():
    """Trả về database handle dựa trên client dùng chung. None nếu không
    kết nối được (chạy offline / MONGODB_URI rỗng)."""
    global _db
    if _db is not None:
        return _db

    client = get_shared_client()
    if client is None:
        return None

    _db = client[MONGODB_DB_NAME]
    ensure_indexes(_db)
    return _db


def ensure_indexes(db) -> None:
    """Đảm bảo các Index cần thiết tồn tại. Idempotent.

    - visual_blueprint_collection.visual_id: unique -> chống trùng lặp ở
      tầng DB (defense-in-depth bên cạnh dedup ở t4_deduplicate.py).
    - fiction_knowledge.visual_blueprint_ref: tăng tốc lookup ngược từ
      fiction_knowledge sang visual_blueprint_collection (Gate 6b).
    - world_rule_library.rule_id: unique -> mỗi rule chỉ có 1 định danh.
    - world_rule_library.(entity_scope, active): tăng tốc load rule active
      theo scope ở rule_library.load_active_rules() (Check G / Gate 5).
    - lib_entities.(library_type, entity_id): unique compound -> lookup
      trực tiếp; upsert theo cặp này đảm bảo idempotent qua nhiều run.
    - lib_entities.(library_type, status): Repo 3/4 lọc nhanh
      status="complete", bỏ qua bản ghi "incomplete".
    Không có TTL index cho lib_entities — Library là dữ liệu nền, không
    hết hạn (khác Reality Data §104 mục 2).

    `background=True` để không khóa collection khi tạo index trên dữ
    liệu đã có sẵn.
    """
    try:
        blueprint_coll = db[MONGO_TARGET_COLLECTIONS["visual_blueprint_collection"]]
        blueprint_coll.create_index("visual_id", unique=True, background=True)

        fiction_coll = db[MONGO_TARGET_COLLECTIONS["fiction_knowledge"]]
        fiction_coll.create_index("visual_blueprint_ref", background=True)

        # [Global Rule Library]
        rule_coll = db[MONGO_TARGET_COLLECTIONS["world_rule_library"]]
        rule_coll.create_index("rule_id", unique=True, background=True)
        rule_coll.create_index([("entity_scope", 1), ("active", 1)], background=True)

        # [MỚI — Gate 6.5 / lib_entities]
        lib_coll = db[MONGO_TARGET_COLLECTIONS["lib_entities"]]
        lib_coll.create_index(
            [("library_type", 1), ("entity_id", 1)],
            unique=True,
            background=True,
        )
        lib_coll.create_index(
            [("library_type", 1), ("status", 1)],
            background=True,
        )

        logger.info(
            "✅ Đã đảm bảo indexes (visual_id unique, visual_blueprint_ref, "
            "world_rule_library.rule_id unique, entity_scope+active, "
            "lib_entities.(library_type,entity_id) unique, "
            "lib_entities.(library_type,status)) cho "
            "visual_blueprint_collection / fiction_knowledge / "
            "world_rule_library / lib_entities."
        )
    except Exception as e:
        logger.warning(f"⚠️ Không thể tạo indexes cho collection mới: {e}")


def close_shared_client():
    """Đóng MongoClient dùng chung — gọi trong finally ở main.py."""
    global _client, _db
    if _client is not None:
        try:
            _client.close()
            logger.info("🔒 Đã đóng MongoDB shared client.")
        except Exception as e:
            logger.warning(f"⚠️ Lỗi khi đóng MongoDB shared client: {e}")
    _client = None
    _db = None
