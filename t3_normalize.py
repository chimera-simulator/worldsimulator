"""
t3_normalize.py — Agent 5a: Validator (Gate 5, chính)
========================================================
[CX]
- Gate 5 nằm ở đây — gate quan trọng nhất vì output của gate này phải
  "sẵn sàng để Repo 4 dùng".
- Thứ tự check PHẢI đúng như liệt kê (A -> B -> C -> G -> F -> D -> E). Check
  A, C, G và F là reject cứng (dừng pipeline cho record đó); B/D/E chỉ đánh
  cờ hoặc tự sửa, không reject.
- Khi FAIL: chỉ đánh cờ reject_reason và ghi log — KHÔNG raise exception.
- Import schema class trực tiếp từ schemas/, không re-define.

[CẬP NHẬT — SPEC_FIX_P1_ARCHITECTURE, Vấn đề 2]
- Trước đây Check B tự kiểm tra cứng {"front_view", "side_view"} trong
  logic của validate_combined_output(). Từ giờ, danh sách view bắt buộc
  lấy từ `config.MIN_REQUIRED_VIEWS` (cấu hình được, không hardcode), qua
  hàm riêng `check_b_multi_view_completeness()`.
- Đây là nơi DUY NHẤT trong toàn bộ codebase được phép quyết định "thiếu
  view có chấp nhận được không" — `schemas/visual_blueprint_3_0.py` đã bỏ
  hoàn toàn model_validator raise cứng cho việc này (xem file đó).
  `t2_scrape.py` và `summarizer.py` không có (và không được phép có) logic
  tương tự.
- Thêm `run_gate_5()` — wrapper tổng hợp theo đúng tên/interface trong
  spec, trả về (result, quality_gate_report) và ghi log JSON chuẩn hoá
  (mục 105 tài liệu gốc) qua `log_json()`. `run_normalize()` được GIỮ LẠI
  làm wrapper tương thích ngược (chỉ trả `result`, không đổi cách gọi ở
  những nơi khác nếu có).

[CẬP NHẬT — Global Rule Library, Check G]
- Check G đọc collection `world_rule_library` (đã load sẵn ở main.py qua
  `rule_library.load_active_rules()`, truyền vào bằng dependency injection
  qua tham số `rules`) — t3_normalize.py KHÔNG tự query Mongo.
- Fail-open: `rules=None`/`rules=[]` → Check G bỏ qua hoàn toàn, hành vi
  giống hệt code trước khi có Check G (an toàn để rollout dần).
- `run_gate_5()`/`validate_combined_output()` nhận `rules` với default
  `None` → mọi lời gọi cũ `run_gate_5(c)`/`run_gate_5(c, cfg)` không vỡ.

[CẬP NHẬT — SPEC_QualityScorer_TL, QualityScorer]
- Sau Check E, gọi core.quality_scorer.compute_quality_score() — SOFT,
  KHÔNG reject, KHÔNG phải Check mới. Set
  schema_record["provenance_and_metadata"]["quality_gate_passed"] (field
  đã có sẵn trong schema). Điểm chi tiết (total/breakdown) chỉ nằm trong
  quality_gate_report (JSON log), KHÔNG ghi field số nguyên mới vào
  MasterSchema20/VisualBlueprint30 — việc đó cần version bump 2.1/3.1,
  chưa được duyệt (xem DESIGN_QualityScorer_Provenance.md §1.4, §3).
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional, Tuple

import config as _config
from builders.visual_prompt_builder import VisualPromptBuilder
from core.quality_scorer import compute_quality_score
from rule_library import evaluate_all

logger = logging.getLogger(__name__)


def _get_nested(d: dict, dot_path: str):
    keys = dot_path.split(".")
    value = d
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _truncate_at_sentence_boundary(text: str, max_len: int) -> str:
    """Truncate an toàn tại ranh giới câu gần nhất <= max_len."""
    if len(text) <= max_len:
        return text

    truncated = text[:max_len]
    last_boundary = max(
        truncated.rfind(". "), truncated.rfind(", "), truncated.rfind("; ")
    )
    if last_boundary > 0:
        return truncated[: last_boundary + 1].rstrip()
    return truncated.rstrip()


def log_json(report: dict) -> None:
    """Ghi log chuẩn hoá JSON (mục 105 tài liệu gốc) — chỉ log, không
    raise, không side-effect nào khác. Observability thuần túy."""
    try:
        logger.info(json.dumps(report, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"⚠️ [Gate 5] Không thể serialize quality_gate_report: {e}")


# ---------------------------------------------------------------------------
# CHECK B — Multi-view completeness (SOFT ONLY, config-driven)
# ---------------------------------------------------------------------------
def check_b_multi_view_completeness(
    blueprint: dict, min_required_views: Optional[List[str]] = None
) -> dict:
    """
    Check B (soft): kiểm tra Visual Blueprint có đủ số view tối thiểu không.
    KHÔNG reject cứng — chỉ đánh cờ để hạ lưu (Repo 4 / gap-filling) biết mà
    xử lý.

    `blueprint` là dict (đã model_dump() từ VisualBlueprint30 ở summarizer.py).
    `multi_view_references` giờ là 1 dict cố định field (front_view,
    side_view, back_view, close_up_face, environment_context), giá trị là
    None nếu view đó chưa có — KHÔNG còn là dict tự do với key động.

    Mutate + return `blueprint` với 2 field top-level:
      - blueprint["missing_view_fields"]: List[str]
      - blueprint["needs_more_views"]: bool
    """
    required = min_required_views if min_required_views is not None else _config.MIN_REQUIRED_VIEWS
    mvr = blueprint.get("multi_view_references", {}) or {}

    missing = [field for field in required if not mvr.get(field)]

    blueprint["missing_view_fields"] = missing
    blueprint["needs_more_views"] = len(missing) > 0

    if missing:
        logger.info(
            f"⚠️ [Gate 5][Check B] '{blueprint.get('visual_id')}' thiếu view "
            f"{missing} — flag needs_more_views (KHÔNG reject)."
        )

    return blueprint


# ---------------------------------------------------------------------------
# CHECK F — Prompt assembly verification (HARD REJECT)
# [SPEC_FIX_P2 — Vấn đề 4] VisualPromptBuilder trước đây chỉ được import,
# không hề được gọi -> không ai xác nhận blueprint thực sự ghép được prompt
# trước khi ghi DB. Từ giờ: Gate 5 PHẢI tự instantiate builder và gọi
# build_prompt() thật; nếu raise ValueError (thiếu required_field, prompt
# sai length) -> reject cứng, không cho đi tiếp vào DB.
# ---------------------------------------------------------------------------
def check_prompt_assembly_verification(blueprint: dict) -> Optional[str]:
    """Trả về reject_reason (str) nếu VisualPromptBuilder không ghép được
    prompt vì lý do KHÁC độ dài prompt. Trả None nếu build thành công HOẶC
    nếu lỗi duy nhất là 'Prompt too long' / 'Prompt too short' — trong 2
    trường hợp đó, Check F không reject và nhường quyền xử lý lại cho
    Check D (tự sửa / đánh cờ), vì build_prompt() chỉ raise SAU KHI đã có
    đủ dữ liệu để build, tức nội dung blueprint hợp lệ về cấu trúc.
    """
    try:
        builder = VisualPromptBuilder(blueprint)
        builder.build_prompt()
    except ValueError as e:
        msg = str(e)
        if "too short" in msg or "too long" in msg:
            logger.info(
                f"ℹ️ [Gate 5][Check F] '{blueprint.get('visual_id')}' prompt "
                f"lệch độ dài ({msg}) — KHÔNG reject ở Check F, nhường cho Check D."
            )
            return None
        logger.error(f"❌ [Gate 5][Check F] Prompt assembly thất bại: {e}")
        return f"prompt_assembly_failed:{e}"
    except Exception as e:
        logger.error(f"❌ [Gate 5][Check F] Lỗi không mong muốn khi build prompt: {e}")
        return f"prompt_assembly_unexpected_error:{e}"
    return None


def check_g_global_rule_cross_check(blueprint: dict, rules: List[dict]) -> Optional[dict]:
    """Check G (hard reject nếu có hit severity=ERROR): đối chiếu blueprint
    với Global Rule Library (đã load sẵn, truyền vào qua tham số `rules` —
    KHÔNG tự query Mongo ở đây, tránh N query cho N blueprint).

    Trả về dict {"reject_reason":..., "rule_hits":[...]} nếu có ERROR hit.
    Trả về None nếu không có rule nào hoặc không có ERROR hit (WARNING/INFO
    hit được xử lý riêng ở validate_combined_output, không reject).
    """
    if not rules:
        return None

    hits = evaluate_all(rules, blueprint)
    error_hits = [h for h in hits if h.get("severity") == "ERROR"]

    if error_hits:
        rule_ids = [h["rule_id"] for h in error_hits]
        logger.error(
            f"❌ [Gate 5][Check G] Reject '{blueprint.get('visual_id')}' — "
            f"vi phạm global rule: {rule_ids}."
        )
        return {
            "reject_reason": f"global_rule_violated:{','.join(rule_ids)}",
            "rule_hits": hits,
        }

    if hits:
        logger.info(
            f"⚠️ [Gate 5][Check G] '{blueprint.get('visual_id')}' có "
            f"{len(hits)} rule WARNING/INFO hit (không reject)."
        )

    return {"reject_reason": None, "rule_hits": hits}


def validate_combined_output(
    combined: dict, cfg=None, rules: Optional[List[dict]] = None
) -> dict:
    """
    combined: output của summarizer.run_summarizer(), dict với keys
    visual_blueprint, schema_record, target_form_field, phase_a_ok, phase_b_ok.

    `cfg`: cho phép tiêm config khác (dùng bởi run_gate_5/test) — mặc định
    dùng module config.py thật của hệ thống nếu không truyền.

    Returns: {"visual_id": str, "blueprint": dict, "schema_record": dict|None,
              "reject_reason": Optional[str], ...flags}
    """
    cfg = cfg or _config
    blueprint = combined.get("visual_blueprint")
    schema_record = combined.get("schema_record")
    flags: dict = {}

    if not blueprint:
        return {
            "visual_id": None,
            "blueprint": None,
            "schema_record": None,
            "reject_reason": "missing_blueprint",
        }

    visual_id = blueprint.get("visual_id", "")

    # ------------------------------------------------------------------
    # CHECK A (reject hoàn toàn): schema_version + document_type
    # ------------------------------------------------------------------
    if schema_record is not None:
        if (
            schema_record.get("schema_version") != "2.0"
            or schema_record.get("document_type") != "worldbuilding_design_pattern"
        ):
            logger.error(f"❌ [Gate 5][Check A] Reject '{visual_id}' — invalid_schema_version_or_type.")
            return {
                "visual_id": visual_id,
                "blueprint": blueprint,
                "schema_record": None,
                "reject_reason": "invalid_schema_version_or_type",
            }

    # ------------------------------------------------------------------
    # CHECK B (không reject, chỉ đánh cờ): multi-view completeness
    # [CẬP NHẬT] Dùng config.MIN_REQUIRED_VIEWS thay vì hardcode
    # {"front_view", "side_view"} — logic tách riêng ở
    # check_b_multi_view_completeness() để có thể tái sử dụng/độc lập test.
    # ------------------------------------------------------------------
    blueprint = check_b_multi_view_completeness(blueprint, cfg.MIN_REQUIRED_VIEWS)
    if blueprint.get("needs_more_views"):
        flags["needs_more_views"] = True
        flags["missing_view_fields"] = blueprint.get("missing_view_fields", [])

    # ------------------------------------------------------------------
    # CHECK C (reject hoàn toàn): forbidden_combinations
    # ------------------------------------------------------------------
    validation_rules = blueprint.get("validation_rules", {}) or {}
    forbidden_combinations = validation_rules.get("forbidden_combinations", []) or []
    blueprint_serialized = str(blueprint).lower()

    for combo in forbidden_combinations:
        if all(str(term).lower() in blueprint_serialized for term in combo):
            logger.error(f"❌ [Gate 5][Check C] Reject '{visual_id}' — forbidden_combination_violated: {combo}.")
            return {
                "visual_id": visual_id,
                "blueprint": blueprint,
                "schema_record": None,
                "reject_reason": "forbidden_combination_violated",
            }

    # ------------------------------------------------------------------
    # CHECK G (reject nếu ERROR hit, chỉ flag nếu WARNING/INFO): Global
    # Rule Library cross-check. Chạy NGAY SAU Check C (cùng họ "term
    # combination", khác nguồn dữ liệu) và TRƯỚC Check F (Check G không
    # phụ thuộc kết quả build prompt, chạy sớm để fail-fast, tiết kiệm 1
    # lần gọi VisualPromptBuilder không cần thiết nếu đã bị reject).
    # ------------------------------------------------------------------
    rules = rules or []
    check_g_result = check_g_global_rule_cross_check(blueprint, rules)
    if check_g_result and check_g_result.get("reject_reason"):
        return {
            "visual_id": visual_id,
            "blueprint": blueprint,
            "schema_record": None,
            "reject_reason": check_g_result["reject_reason"],
        }
    if check_g_result and check_g_result.get("rule_hits"):
        flags["global_rule_hits"] = check_g_result["rule_hits"]

    # ------------------------------------------------------------------
    # CHECK F (reject hoàn toàn nếu lỗi cấu trúc): xác nhận
    # VisualPromptBuilder build được prompt thật từ blueprint — lỗi
    # "too long" / "too short" KHÔNG reject ở đây, nhường cho Check D.
    # ------------------------------------------------------------------
    assembly_reject = check_prompt_assembly_verification(blueprint)
    if assembly_reject:
        return {
            "visual_id": visual_id,
            "blueprint": blueprint,
            "schema_record": None,
            "reject_reason": assembly_reject,
        }

    # ------------------------------------------------------------------
    # CHECK D (không reject, tự sửa): prompt_length trong range
    # ------------------------------------------------------------------
    pre_built = blueprint.get("pre_built_prompts", {}) or {}
    full_prompt = pre_built.get("full_character", "")
    min_len = validation_rules.get("min_prompt_length", 150)
    max_len = validation_rules.get("max_prompt_length", 700)

    if full_prompt:
        if len(full_prompt) > max_len:
            pre_built["full_character"] = _truncate_at_sentence_boundary(full_prompt, max_len)
            blueprint["pre_built_prompts"] = pre_built
            flags["prompt_truncated"] = True
            logger.info(f"✂️ [Gate 5][Check D] '{visual_id}' prompt quá dài — đã truncate an toàn.")
        elif len(full_prompt) < min_len:
            flags["prompt_too_short"] = True
            logger.info(f"⚠️ [Gate 5][Check D] '{visual_id}' prompt quá ngắn — flag, KHÔNG tự bịa thêm.")

    # ------------------------------------------------------------------
    # CHECK E (không reject, chỉ ghi nhận): pending_fields khai báo
    # ------------------------------------------------------------------
    gap_status = _get_nested(blueprint, "metadata.gap_filling_status") or {}
    if "pending_fields" not in gap_status:
        flags["pending_fields_undeclared"] = True
        logger.info(f"⚠️ [Gate 5][Check E] '{visual_id}' thiếu khai báo pending_fields tường minh.")

    # ------------------------------------------------------------------
    # QUALITY SCORER (SOFT / OBSERVABILITY — không phải Check mới, không
    # reject). Chạy sau Check D vì cần đọc pre_built_prompts.full_character
    # ĐÃ được Check D tự sửa (truncate) nếu có. Gắn quality_gate_passed vào
    # schema_record (field đã khai báo sẵn trong MasterSchema20, chỉ chưa
    # từng được set — xem config.MASTER_SCHEMA_2_0.provenance_and_metadata).
    # ------------------------------------------------------------------
    qscore = compute_quality_score(blueprint, schema_record, cfg)
    flags["quality_score"] = qscore
    if schema_record is not None:
        schema_record.setdefault("provenance_and_metadata", {})
        schema_record["provenance_and_metadata"]["quality_gate_passed"] = qscore["passed_threshold"]

    # Nếu qua hết A, C -> merge/return theo target_form_field
    result = {
        "visual_id": visual_id,
        "blueprint": blueprint,
        "schema_record": schema_record,
        "reject_reason": None,
    }
    result.update(flags)

    logger.info(f"✅ [Gate 5] '{visual_id}' pass (flags={list(flags.keys())}).")
    return result


def run_gate_5(
    combined_output: dict, cfg=None, rules: Optional[List[dict]] = None
) -> Tuple[dict, dict]:
    """Gate 5 tổng hợp — chạy Check A (schema/master-schema), Check B
    (multi-view, soft), Check C/G/D/E, KHÔNG raise exception ở đây.

    Trả về (result, quality_gate_report). `result` giữ nguyên shape của
    `validate_combined_output()` (tương thích ngược với run_normalize()).
    `quality_gate_report` là dict chuẩn hoá theo mục 105 tài liệu gốc, đã
    được ghi log qua `log_json()`.

    `cfg` cho phép tiêm config khác khi test (mặc định dùng module config.py
    thật của hệ thống).
    `rules`: list rule active đã load sẵn từ `rule_library.load_active_rules()`
    (dependency injection, KHÔNG tự query Mongo ở đây). Mặc định `None` ->
    Check G bỏ qua hoàn toàn, tương thích ngược với mọi lời gọi cũ.
    """
    cfg = cfg or _config

    try:
        result = validate_combined_output(combined_output, cfg, rules)
    except Exception as e:
        logger.error(f"❌ [T3 Normalize] Lỗi không mong muốn khi validate: {e}")
        result = {
            "visual_id": (combined_output or {}).get("visual_blueprint", {}).get("visual_id"),
            "blueprint": (combined_output or {}).get("visual_blueprint"),
            "schema_record": None,
            "reject_reason": "unexpected_error",
        }

    blueprint = result.get("blueprint") or {}
    needs_more_views = bool(blueprint.get("needs_more_views", False))
    missing_view_fields = blueprint.get("missing_view_fields", [])
    rule_hits = result.get("global_rule_hits", [])
    quality_score = result.get("quality_score")  # None nếu REJECTED (không chấm điểm record bị loại)

    if result.get("reject_reason"):
        status = "REJECTED"
    elif needs_more_views:
        status = "PASS_WITH_FLAG"
    else:
        status = "PASS"

    report = {
        "visual_id": result.get("visual_id"),
        "gate": "GATE_5_NORMALIZE",
        "reject_reason": result.get("reject_reason"),
        "needs_more_views": needs_more_views,
        "missing_view_fields": missing_view_fields,
        "rule_hits": rule_hits,
        "quality_score": quality_score,
        "status": status,
    }

    # Log chuẩn hóa JSON theo mục 105 tài liệu gốc — KHÔNG raise exception.
    log_json(report)

    return result, report


def run_normalize(combined_output: dict) -> dict:
    """Wrapper tương thích ngược: chỉ trả `result` (không kèm report), để
    những nơi gọi cũ (nếu còn) không phải đổi cách dùng. Implementation
    thực tế đã chuyển vào `run_gate_5()`."""
    result, _report = run_gate_5(combined_output)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
