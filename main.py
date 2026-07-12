"""
MAIN — Orchestrator Repo 1 (Visual-First Design Pattern Harvester)
=====================================================================
[CẬP NHẬT — spec §14 (rewrite trước)]
- Bỏ import t6_world_forge.py / t6_rule_engine_bridge.py / rule_engine.py
  khỏi luồng orchestrate chính (đã đánh dấu OUT_OF_SCOPE_REPO1).
- Orchestrate đúng thứ tự: t0 -> t1 -> t2 -> summarizer -> t3 -> t4 -> t5.

[CẬP NHẬT — SPEC_FIX_P1_ARCHITECTURE, Vấn đề 1]
Trước đây `run_search_pipeline()` (t0) và `run_scrape_pipeline()` (t2) mỗi
hàm tự load/save "blackbook.json" riêng -> race giữa hai lần ghi, T2 có thể
ghi đè state mà T0 vừa cập nhật (mất dedup keyword, mất round-robin cursor).

Fix: `main.py` là nơi DUY NHẤT load/save `blackbook.json` (qua
`load_blackbook()`/`save_blackbook()`), load đúng 1 lần đầu run, truyền
CÙNG 1 object `blackbook` (dependency injection) vào cả `run_search_pipeline`
và `run_scrape_pipeline`, hai hàm này chỉ được MUTATE IN-PLACE, không tự mở
file. Ghi file đúng 1 lần cuối run, trong khối `finally` để không mất tiến
độ nếu có exception giữa chừng.

[CẬP NHẬT — SPEC_FIX_P1_ARCHITECTURE, Vấn đề 2]
Bước T3 giờ gọi `t3_normalize.run_gate_5()` (thay vì `run_normalize()`) để
lấy thêm `quality_gate_report` phục vụ observability (mục 105 tài liệu gốc)
— report này đã được `t3_normalize.py` tự log JSON, `main.py` chỉ cần đọc
lại `status`/`needs_more_views` để tổng hợp thống kê chu kỳ.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import config
from config import get_form_fields
from t0_search import run_search_pipeline
from t1_classify import classify_and_rank
from t2_scrape import run_scrape_pipeline
from summarizer import run_summarizer
from t3_normalize import run_gate_5
from t4_deduplicate import deduplicate
from t4_5_library_distill import run_library_distill
from t5_upload import run_upload
from mongo_shared import close_shared_client, get_shared_db
from rule_library import load_active_rules
from core.budget_manager import BudgetManager
from core.logger import PipelineLogger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("MAIN")


# =============================================================================
# [SPEC_FIX_P1 — Vấn đề 1] blackbook.json — load/save DUY NHẤT ở main.py
# =============================================================================
def load_blackbook(path: str) -> dict:
    """Đọc JSON, nếu không tồn tại -> trả về schema rỗng mặc định (không
    side-effect ghi file)."""
    if not os.path.exists(path):
        return {"keywords": {}, "scrape_state": {}, "version": 1}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"⚠️ [MAIN] '{path}' đọc lỗi ({e}) — dùng schema rỗng mặc định.")
        return {"keywords": {}, "scrape_state": {}, "version": 1}


def save_blackbook(path: str, blackbook: dict) -> None:
    """Ghi atomic: viết ra file .tmp rồi os.replace() để tránh corrupt khi
    crash giữa chừng."""
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(blackbook, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError as e:
        logger.error(f"❌ [MAIN] Không thể ghi blackbook '{path}': {e}")


# =============================================================================
# [SPEC_FIX_2_6][Coder 1 — lượt 2] Planet-Type Rotation — engine trong main.py
# =============================================================================
PLANET_ROTATION_KEY = "planet_rotation"


def _get_current_planet_archetype(blackbook: dict) -> dict:
    """Đọc trạng thái planet rotation hiện tại từ blackbook.
    Khởi tạo schema mặc định nếu chưa tồn tại."""
    if PLANET_ROTATION_KEY not in blackbook:
        blackbook[PLANET_ROTATION_KEY] = {
            "cursor_index": 0,
            "in_progress": None,
            "completed_this_week": [],
            "failed_aborted_log": [],
        }
    return blackbook[PLANET_ROTATION_KEY]


def _advance_planet_cursor(blackbook: dict, cfg=None) -> str:
    """Xoay cursor sang archetype kế tiếp trong PLANET_TYPE_CATALOG.
    Chỉ gọi khi archetype hiện tại đã COMPLETED hoặc FAILED_ABORTED.
    Trả về archetype_id tiếp theo."""
    cfg = cfg or config
    catalog = cfg.PLANET_TYPE_CATALOG
    rotation = _get_current_planet_archetype(blackbook)
    next_idx = (rotation["cursor_index"] + 1) % len(catalog)
    rotation["cursor_index"] = next_idx
    archetype_id = catalog[next_idx]
    logger.info(f"🔄 [PlanetRotation] Cursor → [{next_idx}] '{archetype_id}'")
    return archetype_id


def _handle_planet_gate_result(
    blackbook: dict,
    gate_result: dict,
    gate_report: dict,
    working_planet_id: str,
    cfg=None,
) -> None:
    """Xử lý kết quả Gate 5 cho planet document:
    - PASS → status = "completed", ghi completed_this_week, xoay cursor
    - REJECT do thiếu required_fields → status = "retry_pending",
      retry_count += 1, nạp missing fields vào fields_pending
    - retry_count >= 3 → status = "failed_aborted", ghi failed_aborted_log,
      xoay cursor. Data MongoDB KHÔNG xóa.

    QUAN TRỌNG: retry_count đếm theo SỐ CỬA SỔ 25 PHÚT KHÁC NHAU (tức số
    lần run_pipeline_once() khác nhau reject cùng 1 working planet),
    KHÔNG phải số lần gọi API trong cùng 1 cửa sổ — vì hàm này chỉ được
    gọi tối đa 1 lần / chu kỳ pipeline (1 cửa sổ) cho working planet hiện
    tại, retry_count += 1 mỗi lần gọi tự nhiên khớp đúng định nghĩa này.
    """
    cfg = cfg or config
    rotation = _get_current_planet_archetype(blackbook)
    in_progress = rotation.get("in_progress") or {}
    archetype_id = in_progress.get("archetype_id", "unknown")
    reject_reason = gate_result.get("reject_reason")

    if reject_reason is None:
        # PASS → hoàn thành
        in_progress["status"] = "completed"
        if archetype_id not in rotation["completed_this_week"]:
            rotation["completed_this_week"].append(archetype_id)
        rotation["in_progress"] = None
        _advance_planet_cursor(blackbook, cfg)
        logger.info(f"✅ [PlanetRotation] '{archetype_id}' COMPLETED.")

    else:
        # REJECT
        current_retry = in_progress.get("retry_count", 0)
        missing_fields = gate_result.get("missing_required_fields", [])

        if current_retry >= 2:  # retry_count 0,1,2 → sau lần 3 này thành failed
            in_progress["retry_count"] = current_retry + 1  # = 3
            in_progress["status"] = "failed_aborted"
            rotation["failed_aborted_log"].append({
                "working_planet_id": working_planet_id,
                "archetype_id": archetype_id,
                "retry_count": current_retry + 1,
                "aborted_at": datetime.now(timezone.utc).isoformat(),
            })
            rotation["in_progress"] = None
            _advance_planet_cursor(blackbook, cfg)
            logger.warning(
                f"⛔ [PlanetRotation] '{archetype_id}' FAILED_ABORTED "
                f"(retry_count={current_retry + 1}). "
                f"Data MongoDB giữ nguyên với flag failed_aborted."
            )
        else:
            # retry_pending — cursor KHÔNG xoay
            in_progress["retry_count"] = current_retry + 1
            in_progress["status"] = "retry_pending"
            # Nạp lại đúng field còn thiếu (không cào lại từ đầu)
            if missing_fields:
                in_progress["fields_pending"] = missing_fields
                logger.info(
                    f"🔁 [PlanetRotation] '{archetype_id}' retry_pending "
                    f"(retry_count={current_retry + 1}), "
                    f"{len(missing_fields)} field thiếu: {missing_fields}"
                )
            rotation["in_progress"] = in_progress


def _load_existing_visual_ids() -> dict:
    """Nạp visual_id đã tồn tại trong DB để t4_deduplicate.py biết đâu là
    document mới, đâu là document cần merge/flag review."""
    existing: dict = {}
    db = get_shared_db()
    if db is None:
        return existing

    try:
        coll = db[config.MONGO_TARGET_COLLECTIONS["visual_blueprint_collection"]]
        for doc in coll.find({}, {"visual_id": 1, "_id": 0}):
            visual_id = doc.get("visual_id")
            if visual_id:
                existing[visual_id] = {"blueprint": doc}
    except Exception as e:
        logger.warning(f"⚠️ [MAIN] Không thể nạp existing visual_id từ DB: {e}")

    return existing


# =============================================================================
# [MỚI — Progressive Gap Filling, SPEC_PROGRESSIVE_GAP_FILLING_T0 §1]
# =============================================================================
def _load_pending_fields_from_db() -> Optional[List[str]]:
    """Quét `visual_blueprint_collection`, gom TẤT CẢ dot-path field đang
    nằm trong `metadata.gap_filling_status.pending_fields` của MỌI
    document có mảng này không rỗng.

    Trả về:
        - List[str] rỗng-đã-loại-trùng nếu có ít nhất 1 pending field.
        - None nếu DB rỗng, hoặc không document nào có pending_fields,
          hoặc kết nối DB thất bại (fail-safe -> để main.py tự quyết
          định fallback full-scan, KHÔNG tự ý trả [] gây nhầm lẫn với
          "đã đầy đủ" ở bước (4)).
    """
    db = get_shared_db()
    if db is None:
        logger.warning(
            "⚠️ [MAIN] Không kết nối được MongoDB khi load pending_fields — "
            "fallback full-scan 29 field."
        )
        return None

    try:
        coll = db[config.MONGO_TARGET_COLLECTIONS["visual_blueprint_collection"]]

        # Chỉ lấy document CÓ mảng pending_fields không rỗng — dùng
        # $exists + $ne: [] ngay ở tầng query (không kéo cả collection
        # về rồi filter bằng Python, tránh tốn băng thông/RAM khi DB lớn).
        cursor = coll.find(
            {
                "metadata.gap_filling_status.pending_fields": {
                    "$exists": True,
                    "$ne": [],
                }
            },
            {"metadata.gap_filling_status.pending_fields": 1, "_id": 0},
        )

        pending_set: set = set()
        doc_count = 0
        for doc in cursor:
            doc_count += 1
            fields = (
                doc.get("metadata", {})
                .get("gap_filling_status", {})
                .get("pending_fields", [])
            )
            pending_set.update(f for f in fields if f)

    except Exception as e:
        logger.warning(
            f"⚠️ [MAIN] Lỗi truy vấn pending_fields từ DB: {e} — "
            "fallback full-scan 29 field."
        )
        return None

    if doc_count == 0:
        # Không có document nào từng khai báo pending_fields không rỗng.
        # Có 2 khả năng: (a) DB hoàn toàn rỗng (Run 1) -> full-scan là
        # đúng, hoặc (b) DB có document nhưng TẤT CẢ đã pending_fields=[]
        # (đầy đủ 100%) -> phải phân biệt để quyết định dừng hẳn (mục 4).
        # -> _load_pending_fields_from_db() không tự đủ thông tin phân
        # biệt (a) vs (b); main.py sẽ tự kiểm tra thêm qua
        # _visual_blueprint_collection_is_empty().
        return None

    pending_fields = sorted(pending_set)
    logger.info(
        f"🔍 [MAIN] Tìm thấy {len(pending_fields)} pending field từ "
        f"{doc_count} document trong visual_blueprint_collection."
    )
    return pending_fields


def _visual_blueprint_collection_is_empty() -> bool:
    """True nếu collection visual_blueprint_collection chưa có document
    nào (Run 1 / cold-start thật sự)."""
    db = get_shared_db()
    if db is None:
        return True  # fail-safe: coi như rỗng -> full-scan, không dừng nhầm
    try:
        coll = db[config.MONGO_TARGET_COLLECTIONS["visual_blueprint_collection"]]
        return coll.estimated_document_count() == 0
    except Exception:
        return True


# =============================================================================
# [CODER 2 — Budget Theo Thời Gian, Vấn đề #2] Graceful stop từ bên trong
# Python, thay cho hard-kill timeout-minutes của GitHub Actions.
# =============================================================================
def _check_time_and_stop(budget, obs, step_name: str) -> bool:
    """Kiểm tra time budget sau mỗi bước lớn.

    Returns:
        True nếu time budget đã cạn (caller phải dừng ngay, return kết quả tạm).
        False nếu vẫn còn thời gian (tiếp tục bình thường).
    """
    if budget.is_time_budget_exhausted():
        remaining = budget.seconds_remaining()  # sẽ âm
        logger.warning(
            f"⏱️ [MAIN] Time budget cạn sau bước '{step_name}' "
            f"({abs(remaining):.0f}s quá hạn). Graceful stop."
        )
        if obs:
            obs.event(
                step=step_name, agent="main", status="GRACEFUL_STOP",
                message=(
                    f"Time budget exhausted — pipeline dừng sau '{step_name}'. "
                    f"Blackbook sẽ được lưu trong finally block."
                ),
                extra={"budget": budget.snapshot().to_dict()},
            )
        return True
    return False


async def run_pipeline_once(cfg=None) -> dict:
    """Chạy đúng 1 chu kỳ đầy đủ của Repo 1: t0 -> t1 -> t2 -> summarizer
    -> t3 -> t4 -> t5. Trả về Upload Report tổng hợp."""
    cfg = cfg or config

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    start = time.time()

    # [MỚI] Khởi tạo Budget và Logger — 1 lần duy nhất / chu kỳ, truyền
    # xuống tất cả agent (dependency injection, giống pattern blackbook).
    budget = BudgetManager()
    obs = PipelineLogger(run_id=run_id, budget=budget)

    obs.event(step="PIPELINE_START", agent="main", status="START",
              message=f"Bắt đầu chu kỳ Repo 1 — run_id={run_id}",
              extra={"budget_config": {
                  "max_urls": budget.max_urls,
                  "max_gemini_calls": budget.max_gemini_calls,
                  "max_tokens": budget.max_tokens,
                  "max_seconds": budget.max_seconds,  # [MỚI — CODER 2]
              }})

    # (1) Load blackbook MỘT lần duy nhất cho cả chu kỳ.
    blackbook = load_blackbook(cfg.BLACKBOOK_PATH)

    # [CODER 1] Reset blackbook nếu được yêu cầu qua env var
    import os as _os
    if _os.getenv("RESET_BLACKBOOK", "false").lower() == "true":
        from domain_ban import force_unban_all
        unban_count = force_unban_all(blackbook)
        logger.warning(
            f"⚠️ [MAIN] RESET_BLACKBOOK=true — đã gỡ ban {unban_count} domain. "
            "Blackbook vẫn giữ round-robin cursor và adapter labels."
        )
        if obs:
            obs.event(
                step="PIPELINE_START", agent="main", status="WARNING",
                message=f"RESET_BLACKBOOK triggered — {unban_count} domains unbanned.",
            )

    # (2) [SPEC_FIX_2_6][Coder 1 — lượt 2] Planet-Type Rotation — xác định
    # archetype đang làm việc TRƯỚC T0, để seed_kw/anchor_name ép ngữ cảnh
    # đúng archetype cho toàn bộ query của chu kỳ này.
    rotation = _get_current_planet_archetype(blackbook)
    in_progress = rotation.get("in_progress")
    # [SPEC_FIX_2_6 — lượt 2, fix REJECT] Tính 1 lần, dùng lại ở cả nhánh
    # xác định archetype VÀ ở bước (3)/(4) bên dưới — tránh lặp điều kiện
    # rải rác nhiều chỗ dễ lệch nhau giữa các lần sửa.
    is_retry_pending = bool(in_progress and in_progress.get("status") == "retry_pending")

    if is_retry_pending:
        # Lấy lại fields_pending từ lần trước để chỉ search bù phần thiếu
        current_planet_archetype_id = in_progress["archetype_id"]
        working_planet_id = in_progress["working_planet_id"]
        planet_target_fields = in_progress.get("fields_pending", [])
        logger.info(
            f"🔁 [PlanetRotation] Tiếp tục retry '{current_planet_archetype_id}' — "
            f"{len(planet_target_fields)} field pending."
        )
    else:
        # Lấy archetype mới theo cursor (bỏ qua in_progress dở dang không
        # phải retry_pending — trường hợp này không nên xảy ra bình
        # thường vì _handle_planet_gate_result() luôn set None/retry_pending
        # cuối mỗi chu kỳ, nhưng vẫn khởi tạo mới an toàn nếu gặp).
        planet_catalog = cfg.PLANET_TYPE_CATALOG
        cursor_idx = rotation["cursor_index"]
        current_planet_archetype_id = planet_catalog[cursor_idx % len(planet_catalog)]
        # [SPEC_FIX_2_6 — lượt 2, fix REJECT] full-scan cho archetype mới —
        # từ bản fix này trở đi, `effective_target_fields` ở bước (3) bên
        # dưới THẬT SỰ giữ nguyên `None` (full-scan), KHÔNG còn bị fallback
        # sang `pending_fields` toàn cục nữa (khác bản trước bị REJECT).
        planet_target_fields = None
        working_planet_id = f"PLANET_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        rotation["in_progress"] = {
            "working_planet_id": working_planet_id,
            "archetype_id": current_planet_archetype_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "in_progress",
            "retry_count": 0,
            "fields_filled": [],
            "fields_pending": [],
        }
        logger.info(
            f"🪐 [PlanetRotation] Archetype mới '{current_planet_archetype_id}' "
            f"(working_planet_id={working_planet_id})."
        )

    # seed_kw cho archetype hiện tại — ép ngữ cảnh Target_Concept ở T0.
    planet_seed_kw = f"{current_planet_archetype_id.replace('_', ' ')} planet concept art worldbuilding"

    # (3) [SPEC_FIX_2_6 — lượt 2, fix REJECT BLOCKING] Progressive Gap
    # Filling (DB-driven) CHỈ áp dụng cho trạng thái retry_pending — dùng
    # `planet_target_fields` (= fields_pending của CHÍNH working_planet_id
    # đang retry, lấy từ `in_progress`). Archetype MỚI luôn full-scan toàn
    # bộ field, KHÔNG merge với `pending_fields` toàn cục nữa.
    #
    # Lý do: `_load_pending_fields_from_db()` quét TOÀN BỘ
    # `visual_blueprint_collection`, KHÔNG lọc theo `working_planet_id`
    # hay `entity_type` (field này chưa tồn tại trong
    # `VisualBlueprint30`/metadata). `None` (full-scan) là falsy nên bản
    # cũ (`planet_target_fields if planet_target_fields else pending_fields`)
    # tự động fallback sang `pending_fields` mỗi khi archetype mới bắt đầu
    # — từ chu kỳ thứ 2 trở đi `pending_fields` gần như luôn không rỗng
    # (đúng bản chất Visual-First), nên archetype mới bị gán field thiếu
    # của archetype/entity KHÁC trong khi vẫn dùng anchor_name/seed_kw của
    # CHÍNH NÓ — tái tạo lại đúng vấn đề "mông lung, sai chủ đích" mà
    # Planet-Type Rotation (SPEC_ADDENDUM 2.6) được thiết kế để triệt tiêu.
    #
    # Fix (phương án (a) trong REJECT — MVP, không đụng schema Coder 2/3):
    # bỏ hẳn merge chéo. Nếu (a) làm giảm hiệu quả gap-filling toàn cục,
    # đây là câu hỏi để gửi lead cho Giai đoạn 2 (thêm `working_planet_id`
    # vào `metadata.gap_filling_status` — phương án (b) trong REJECT),
    # KHÔNG tự quyết định một mình ở lượt fix này.
    if is_retry_pending:
        effective_target_fields = planet_target_fields
    else:
        effective_target_fields = None  # full-scan THẬT cho archetype mới — không fallback global

    # (4) [MỚI — Progressive Gap Filling] Check "KB đã đầy" — CHỈ chạy khi
    # KHÔNG đang retry: nếu đang retry_pending thì working_planet_id hiện
    # tại CHẮC CHẮN còn field required thiếu (đó là lý do nó retry), nên
    # phải luôn chạy chu kỳ này bất kể phần còn lại của KB có vẻ đầy hay
    # không. `pending_fields`/`_load_pending_fields_from_db()` từ đây trở
    # đi CHỈ còn dùng cho việc check "KB đã đầy" này — không còn dùng để
    # set `effective_target_fields` nữa (xem bước (3) ở trên).
    if not is_retry_pending:
        pending_fields = _load_pending_fields_from_db()
        if pending_fields is None and not _visual_blueprint_collection_is_empty():
            # DB có document nhưng KHÔNG document nào còn pending_fields ->
            # Fiction Knowledge Base đã đầy đủ 100%. Dừng hẳn, không phí T0->T5.
            obs.event(step="PIPELINE_START", agent="main", status="DONE",
                      message="Fiction Knowledge Base đã đầy. Dừng pipeline.")
            logger.info("✅ [MAIN] Fiction Knowledge Base đã đầy. Dừng pipeline.")
            return {"new": 0, "merged": 0, "rejected": 0, "errors": [], "skipped_reason": "kb_full"}

    total_fields = len(
        get_form_fields("form_1_planet_foundation")
        + get_form_fields("form_2_civilization_layer")
    )
    if effective_target_fields:
        skipped = total_fields - len(effective_target_fields)
        logger.info(
            f"🎯 [MAIN] Gap-Aware Mode: Chỉ tìm {len(effective_target_fields)} "
            f"field đang thiếu, bỏ qua {skipped} field đã đầy."
        )
        obs.event(step="T0_SEARCH", agent="main", status="INFO",
                  message=(
                      f"Gap-Aware Mode: {len(effective_target_fields)}/{total_fields} "
                      f"field pending — bỏ qua {skipped} field đã đầy."
                  ),
                  extra={"pending_fields": effective_target_fields})
    else:
        logger.info(f"🔎 [MAIN] Full-Scan Mode: tìm toàn bộ {total_fields} field (Run 1 / cold-start).")

    try:
        # === T0: Search (blackbook injected — KHÔNG tự load/save) ===
        search_results = await run_search_pipeline(
            blackbook, budget=budget, obs=obs, target_fields=effective_target_fields,
            anchor_name=current_planet_archetype_id,   # [MỚI — SPEC_FIX_2_6]
            seed_kw=planet_seed_kw,                     # [MỚI — SPEC_FIX_2_6]
        )
        obs.event(step="T0_SEARCH", agent="t0_search", status="SUCCESS",
                  items_processed=len(search_results),
                  message=f"T0 hoàn thành — {len(search_results)} URL.")

        if not search_results:
            obs.event(step="T0_SEARCH", agent="t0_search", status="WARNING",
                      message="T0 không trả về URL nào — dừng chu kỳ.")
            return {"new": 0, "merged": 0, "rejected": 0, "errors": ["t0_empty"]}

        # [CODER 2] Time-budget check sau T0
        if _check_time_and_stop(budget, obs, "T0_SEARCH"):
            return {"new": 0, "merged": 0, "rejected": 0, "errors": ["graceful_stop_after_t0"]}

        # === T1: Classify (Gate 1) ===
        classified = classify_and_rank(search_results)
        obs.event(step="T1_CLASSIFY", agent="t1_classify", status="SUCCESS",
                  items_processed=len(classified),
                  message=f"T1 hoàn thành — {len(classified)} URL qua Gate 1.")

        if not classified:
            obs.event(step="T1_CLASSIFY", agent="t1_classify", status="WARNING",
                      message="T1 không còn URL nào sau Gate 1 — dừng chu kỳ.")
            return {"new": 0, "merged": 0, "rejected": 0, "errors": ["t1_empty"]}

        # [CODER 2] Time-budget check sau T1
        if _check_time_and_stop(budget, obs, "T1_CLASSIFY"):
            return {"new": 0, "merged": 0, "rejected": 0, "errors": ["graceful_stop_after_t1"]}

        # === T2: Scrape (Gate 2, async, CÙNG object blackbook với T0) ===
        scraped_docs = await run_scrape_pipeline(classified, blackbook, budget=budget, obs=obs)
        obs.event(step="T2_SCRAPE", agent="t2_scrape", status="SUCCESS",
                  items_processed=len(scraped_docs),
                  message=f"T2 hoàn thành — {len(scraped_docs)} document qua Gate 2.")

        if not scraped_docs:
            obs.event(step="T2_SCRAPE", agent="t2_scrape", status="WARNING",
                      message="T2 không còn document nào sau Gate 2 — dừng chu kỳ.")
            return {"new": 0, "merged": 0, "rejected": 0, "errors": ["t2_empty"]}

        # [CODER 2] Time-budget check sau T2
        if _check_time_and_stop(budget, obs, "T2_SCRAPE"):
            return {"new": 0, "merged": 0, "rejected": 0, "errors": ["graceful_stop_after_t2"]}

        # === Summarizer: Phase A + Phase B (Gate 3 + Gate 4) ===
        # Chạy tuần tự (không async) vì Gemini Free Tier giới hạn request/phút —
        # round-robin key trong summarizer.py đã tự chia tải, không cần thêm
        # asyncio.gather ở tầng orchestrator (tránh spike vượt rate limit).
        combined_outputs = []
        total_tokens = 0
        for doc in scraped_docs:
            try:
                combined = run_summarizer(doc, budget=budget, obs=obs)
                combined_outputs.append(combined)
                total_tokens += combined.get("_tokens_used", 0)
            except Exception as e:
                obs.event(step="T3_SUMMARIZE", agent="summarizer", status="ERROR",
                          message=f"Lỗi summarizer cho 1 document: {e}")
                continue

            # [CODER 2] Time-budget check SAU MỖI document (không chỉ sau
            # cả batch) — Summarizer là bước tốn thời gian nhất (gọi Gemini
            # tuần tự). break (không return) để tiếp tục T3 -> T5 với
            # combined_outputs đã có, dù chưa đủ hết scraped_docs.
            if _check_time_and_stop(budget, obs, "SUMMARIZER_DOC"):
                break

        phase_a_ok_count = sum(1 for c in combined_outputs if c.get("phase_a_ok"))
        obs.event(step="T3_SUMMARIZE", agent="summarizer", status="SUCCESS",
                  items_processed=phase_a_ok_count, tokens_used=total_tokens,
                  message=f"Summarizer hoàn thành — {phase_a_ok_count}/{len(combined_outputs)} qua Gate 3.")

        # === Load Global Rule Library — 1 lần / chu kỳ, TRƯỚC vòng lặp Gate 5 ===
        db = get_shared_db()  # đã có sẵn pattern get_shared_db() dùng cho T4 (_load_existing_visual_ids)
        # [FIX] load_active_rules() trả (rules, rule_check_skipped) — rule_check_skipped=True
        # nghĩa là Mongo offline/lỗi query (fail-open thật sự), KHÔNG phải 0 rule active hợp lệ.
        active_rules, rule_check_skipped = load_active_rules(db)  # scope=None -> load TẤT CẢ rule active, filter sau
        if rule_check_skipped:
            logger.warning(
                "   Rule Library — fail-open (Mongo offline/lỗi query), "
                "Gate 5 chạy KHÔNG có Global Rule Cross-Check chu kỳ này."
            )
            obs.event(step="T4_NORMALIZE", agent="rule_library", status="WARNING",
                      message="Global Rule Library fail-open — Gate 5 bỏ qua Check G chu kỳ này.")
        else:
            logger.info(f"   Rule Library — {len(active_rules)} rule active đã load.")

        # === T3: Normalize (Gate 5 — run_gate_5 trả kèm quality_gate_report) ===
        gate5_results = [run_gate_5(c, cfg, rules=active_rules) for c in combined_outputs]
        normalized = [result for result, _report in gate5_results]
        needs_more_views_count = sum(1 for _r, report in gate5_results if report.get("needs_more_views"))

        passed_gate5 = [n for n in normalized if n.get("reject_reason") is None]
        obs.event(step="T4_NORMALIZE", agent="t3_normalize", status="SUCCESS",
                  items_processed=len(passed_gate5),
                  message=(
                      f"T3 hoàn thành — {len(passed_gate5)}/{len(normalized)} qua Gate 5 "
                      f"({needs_more_views_count} flag needs_more_views)."
                  ))

        # === [SPEC_FIX_2_6][Coder 1 — lượt 2] Planet Rotation: xử lý kết quả
        # Gate 5 cho document planet (nếu có) của working planet đang track.
        # Chỉ document entity_type "planet"/"planet_environment" mới liên
        # quan tới rotation; các entity_type khác (species/creature/...) bị
        # bỏ qua ở đây (chúng không ảnh hưởng cursor/retry của planet).
        _planet_entity_types = {"planet", "planet_environment"}
        _planet_gate_results = [
            (result, report) for result, report in gate5_results
            if (result.get("blueprint") or {}).get("entity_type") in _planet_entity_types
        ]
        if _planet_gate_results:
            if len(_planet_gate_results) > 1:
                logger.warning(
                    f"⚠️ [PlanetRotation] {len(_planet_gate_results)} document "
                    f"planet trong cùng 1 chu kỳ — chỉ xử lý document đầu tiên "
                    f"cho working_planet_id='{working_planet_id}', các document "
                    f"còn lại được bỏ qua ở tầng rotation (vẫn tiếp tục qua "
                    f"T4/T5 bình thường nếu PASS Gate 5)."
                )
            _planet_result, _planet_report = _planet_gate_results[0]
            _handle_planet_gate_result(
                blackbook, _planet_result, _planet_report, working_planet_id, cfg,
            )
        else:
            logger.info(
                f"ℹ️ [PlanetRotation] Chu kỳ này không tạo ra document planet "
                f"nào cho working_planet_id='{working_planet_id}' — trạng thái "
                f"rotation giữ nguyên, thử lại chu kỳ sau."
            )

        # === T4: Deduplicate ===
        existing_visual_ids = _load_existing_visual_ids()
        deduped = deduplicate(passed_gate5, existing_visual_ids)
        obs.event(step="T5_DEDUP", agent="t4_deduplicate", status="SUCCESS",
                  items_processed=len(deduped),
                  message=f"T4 hoàn thành — {len(deduped)} document sau dedup.")

        # === T4.5: Library Distillation (Gate 6.5) — MỚI ===
        # Mutate in-place deduped_docs (thêm key "lib_record" vào mỗi doc).
        # t5_upload.py sẽ đọc lib_record từ cùng 1 doc để giữ 3-phase
        # transaction trên 1 entity (không tách list riêng).
        deduped = run_library_distill(deduped, budget=budget, obs=obs)
        lib_complete_count = sum(
            1 for d in deduped if (d.get("lib_record") or {}).get("status") == "complete"
        )
        obs.event(
            step="T5_5_LIBRARY_DISTILL",
            agent="t4_5_library_distill",
            status="SUCCESS",
            items_processed=lib_complete_count,
            message=(
                f"Gate 6.5 hoàn thành — {lib_complete_count} lib_entity "
                f"complete / {len(deduped)} document."
            ),
        )

        # === T5: Upload (Gate 6) ===
        report = run_upload(deduped)
        obs.event(step="T6_UPLOAD", agent="t5_upload", status="SUCCESS",
                  items_processed=report.get("new", 0),
                  message=(
                      f"T5 hoàn thành — new={report['new']}, merged={report['merged']}, "
                      f"rejected={report['rejected']}."
                  ))

        # [SPEC_FIX_2_6] Weekly health counter — planet rotation
        rotation_final = _get_current_planet_archetype(blackbook)
        completed_count = len(rotation_final.get("completed_this_week", []))
        failed_count = len(rotation_final.get("failed_aborted_log", []))
        retry_pending = 1 if (rotation_final.get("in_progress") or {}).get("status") == "retry_pending" else 0
        logger.info(
            f"📊 [PlanetRotation][Weekly] "
            f"Hoàn thành={completed_count} | "
            f"retry_pending={retry_pending} | "
            f"failed_aborted={failed_count}"
        )

        duration = time.time() - start
        obs.event(step="PIPELINE_DONE", agent="main", status="DONE",
                  message=f"Chu kỳ hoàn thành sau {duration:.1f}s.",
                  extra={"report": report, "duration_seconds": round(duration, 1)})
        return report

    finally:
        # (4) Ghi blackbook MỘT lần, cuối run — kể cả khi có exception giữa
        # chừng, để không mất tiến độ round-robin/dedup đã ghi nhận.
        save_blackbook(cfg.BLACKBOOK_PATH, blackbook)


def main() -> None:
    try:
        asyncio.run(run_pipeline_once())
    finally:
        close_shared_client()


if __name__ == "__main__":
    main()
