"""
t5_upload.py — Agent 6: Split Upload (Gate 6)
=================================================
[CX]
- Gate 6 nằm ở đây. Không bao giờ upload vào collection "world_rules" —
  collection này đã bị loại khỏi MONGO_TARGET_COLLECTIONS ở config.py.
- Nếu document chỉ có blueprint hợp lệ nhưng schema_record là None (Gate 4
  fail ở summarizer) -> chỉ upload vào visual_blueprint_collection, KHÔNG
  tạo record rỗng bên fiction_knowledge.
- Atomic rollback bắt buộc — không được để inconsistent state giữa 2
  collection.
"""
from __future__ import annotations

import logging
from typing import List

from config import MONGO_TARGET_COLLECTIONS
from mongo_shared import get_shared_db

logger = logging.getLogger(__name__)


def upload_document(doc: dict) -> dict:
    """
    Returns: {"status": "new"|"merged"|"rejected", "visual_id": str}
    """
    visual_id = doc.get("visual_id")
    blueprint = doc.get("blueprint")
    schema_record = doc.get("schema_record")

    if not visual_id or not blueprint:
        logger.warning("⚠️ [T5][Gate 6] Document thiếu visual_id/blueprint hợp lệ — reject.")
        return {"status": "rejected", "visual_id": visual_id}

    db = get_shared_db()
    if db is None:
        logger.error("❌ [T5] Không có kết nối MongoDB — không thể upload.")
        return {"status": "rejected", "visual_id": visual_id}

    blueprint_coll = db[MONGO_TARGET_COLLECTIONS["visual_blueprint_collection"]]
    fiction_coll = db[MONGO_TARGET_COLLECTIONS["fiction_knowledge"]]

    inserted_blueprint = False
    inserted_fiction = False
    inserted_lib = False

    try:
        # ------------------------------------------------------------
        # GATE 6a: Check visual_id unique trước khi insert (nếu record
        # mới hoàn toàn, không phải merge).
        # ------------------------------------------------------------
        existing = blueprint_coll.find_one({"visual_id": visual_id})
        is_merge = existing is not None

        # UPLOAD_A: upsert vào visual_blueprint_collection theo visual_id
        blueprint_coll.update_one(
            {"visual_id": visual_id}, {"$set": blueprint}, upsert=True
        )
        inserted_blueprint = True

        status = "merged" if is_merge or doc.get("merged") else "new"

        # Nếu schema_record là None (Gate 4 fail) -> CHỈ upload blueprint,
        # không tạo record rỗng bên fiction_knowledge.
        if schema_record is None:
            logger.info(
                f"✅ [T5] '{visual_id}' — chỉ upload visual_blueprint (schema_record=None, Gate 4 chưa pass)."
            )
            return {"status": status, "visual_id": visual_id}

        # UPLOAD_B: insert vào fiction_knowledge với visual_blueprint_ref
        fiction_record = dict(schema_record)
        fiction_record["visual_blueprint_ref"] = visual_id

        # GATE 6b: record B phải trỏ đúng tới visual_id vừa upload ở A
        if fiction_record["visual_blueprint_ref"] != visual_id:
            raise ValueError("visual_blueprint_ref không khớp visual_id — vi phạm Gate 6b.")

        fiction_coll.update_one(
            {"visual_blueprint_ref": visual_id},
            {"$set": fiction_record},
            upsert=True,
        )
        inserted_fiction = True

        # UPLOAD_C (MỚI — Gate 6.5): upsert lib_record vào lib_entities nếu
        # t4_5_library_distill đã tạo lib_record cho doc này.
        # Đặt SAU UPLOAD_B vì lib_record phụ thuộc schema_record/blueprint đã
        # ghi thành công — nếu B fail, exception nhảy thẳng xuống except, C
        # không chạy (đúng ý, không cần guard thêm).
        lib_record = doc.get("lib_record")
        if lib_record:
            lib_coll = db[MONGO_TARGET_COLLECTIONS["lib_entities"]]
            lib_coll.update_one(
                {
                    "library_type": lib_record["library_type"],
                    "entity_id": lib_record["entity_id"],
                },
                {"$set": lib_record},
                upsert=True,
            )
            inserted_lib = True
            logger.info(
                f"✅ [T5][Gate 6.5] '{lib_record['entity_id']}' "
                f"({lib_record['library_type']}) — upload lib_entities "
                f"thành công (status={lib_record.get('status')})."
            )

        logger.info(f"✅ [T5][Gate 6] '{visual_id}' — upload thành công (status={status}).")
        return {"status": status, "visual_id": visual_id}

    except Exception as e:
        logger.error(f"❌ [T5][Gate 6] Lỗi upload '{visual_id}': {e} — ROLLBACK.")
        # ROLLBACK LIFO (thứ tự ngược với thứ tự ghi: C → B → A):
        # - C (lib_entities) rollback trước nếu đã insert.
        # - B/A rollback theo logic hiện có.
        try:
            if inserted_lib and lib_record:
                lib_coll = db[MONGO_TARGET_COLLECTIONS["lib_entities"]]
                lib_coll.delete_one(
                    {
                        "library_type": lib_record["library_type"],
                        "entity_id": lib_record["entity_id"],
                    }
                )
                logger.info(
                    f"🔙 [T5] Rollback: đã xóa lib_entities '{lib_record['entity_id']}'."
                )

            if inserted_blueprint and not inserted_fiction and schema_record is not None:
                blueprint_coll.delete_one({"visual_id": visual_id})
                logger.info(f"🔙 [T5] Rollback: đã xóa '{visual_id}' khỏi visual_blueprint_collection.")
        except Exception as rollback_error:
            logger.error(f"❌ [T5] Rollback thất bại cho '{visual_id}': {rollback_error}")

        return {"status": "rejected", "visual_id": visual_id}


def run_upload(deduped_docs: List[dict]) -> dict:
    """Loop qua từng doc -> upload_document -> tổng hợp Upload Report."""
    report = {"new": 0, "merged": 0, "rejected": 0, "errors": []}

    for doc in deduped_docs:
        try:
            result = upload_document(doc)
            status = result["status"]
            if status in report:
                report[status] += 1
        except Exception as e:
            report["rejected"] += 1
            report["errors"].append(str(e))
            logger.error(f"❌ [T5] Lỗi không mong muốn khi upload document: {e}")

    logger.info(
        f"📊 [T5] Upload Report — new={report['new']}, merged={report['merged']}, "
        f"rejected={report['rejected']}, errors={len(report['errors'])}."
    )
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
