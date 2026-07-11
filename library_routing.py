"""
library_routing.py — Field Routing Table cho Gate 6.5 (Library Distillation)
==============================================================================
Bảng cấu hình tĩnh (constants), KHÔNG chứa logic LLM và KHÔNG import
pymongo/genai (đúng nguyên tắc config.py: file constants thuần).

Chỉ được import bởi t4_5_library_distill.py. Nguồn:
REPO1_DESTINATION_LIBRARIES_ARCHITECTURE.md mục 3 +
SPEC_GATE_6_5_LIBRARY_DISTILL_v1_0.md mục 2.

Vấn đề mismatch đã được giải quyết (mục 2.1 Spec):
- `entity_type` trong VisualBlueprint30 chỉ có 4 giá trị (species/creature/
  architecture/planet_environment) — quá hẹp để suy luận `library_type`.
- `library_type` có 10 giá trị (species/creature/flora/architecture/costume/
  technology/culture/occupation/visual_style/character_blueprint).
→ Suy luận `library_type` DỰA CHỦ YẾU VÀO `target_form_field` (dot-path
  trong provenance_and_metadata của Master Schema 2.0, bao phủ đủ mọi nhánh),
  với fallback dùng `blueprint.entity_type` khi target_form_field rỗng/không
  match.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# TARGET_FORM_FIELD_PREFIX -> library_type
#
# Match theo PREFIX của dot-path (startswith), duyệt tuần tự, dừng ở match
# đầu tiên. Thứ tự khai báo CÓ Ý NGHĨA — path dài/cụ thể hơn phải đứng
# TRƯỚC path ngắn/chung hơn để tránh match nhầm.
# Ví dụ: "form_2_civilization_layer.society_and_infrastructure.architecture_patterns"
#         phải đứng TRƯỚC "form_2_civilization_layer.society_and_infrastructure"
#         nếu có (không có ở đây nhưng cần chú ý khi mở rộng).
# ---------------------------------------------------------------------------
TARGET_FORM_FIELD_TO_LIBRARY_TYPE: list[tuple[str, str]] = [
    # Species (biology / morphology)
    ("form_2_civilization_layer.biology_and_behavior", "species"),

    # Flora (ecosystem foundation)
    ("form_1_planet_foundation.ecosystem_foundation", "flora"),

    # Architecture (cụ thể hơn → trước technology/culture chung)
    (
        "form_2_civilization_layer.society_and_infrastructure.architecture_patterns",
        "architecture",
    ),

    # Technology
    (
        "form_2_civilization_layer.society_and_infrastructure.technology_patterns",
        "technology",
    ),

    # Culture (bao gộp religion/language/art/daily_life/history/diplomatic)
    ("form_2_civilization_layer.culture_and_history", "culture"),

    # KHÔNG có entry cho "occupation" — lib Occupation chưa có nguồn harvest
    # tương ứng trong t0_search.py (gap thật sự). route_library_type() trả
    # None → Gate 6.5 reject có log (mục 2.3 Spec). Cần Sếp quyết định lâu dài:
    # bổ sung query pattern mới vào t0_search.py hay seed thủ công 1 lần.

    # KHÔNG có entry cho "planet_environment" (mục 2.4 Spec) — entity_type này
    # của VisualBlueprint không có library_type tương ứng trong §16-27.
    # route_library_type() trả None → Gate 6.5 reject có log, không phải lỗi
    # hệ thống. Blueprint vẫn upload bình thường vào visual_blueprint_collection
    # / fiction_knowledge qua nhánh hiện có của T5.
]

# ---------------------------------------------------------------------------
# Fallback khi target_form_field rỗng hoặc không match bảng trên.
# Dùng blueprint.entity_type trực tiếp (áp dụng khi entity_type nằm trong
# tập hợp lệ của VisualBlueprint30). "planet_environment" cố ý KHÔNG có
# entry → route_library_type() trả None (mục 2.4 Spec).
# ---------------------------------------------------------------------------
ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE: dict[str, str] = {
    "species": "species",
    "creature": "creature",
    "architecture": "architecture",
    # "planet_environment": cố ý KHÔNG có entry → None
}

# ---------------------------------------------------------------------------
# LIBRARY_REQUIRED_FIELDS — baseline tối thiểu theo ví dụ mục 5 + mục 6
# tài liệu Architect.
#
# Species: bắt buộc skin_color (nhận dạng thị giác chính) + prompt_keywords
#   (output sẵn cho Repo 4).
# Architecture: bắt buộc style + material (2 trụ cột visual identity).
# Các library_type khác chưa có đặc tả riêng → baseline [\"prompt_keywords\"]
#   (field này luôn cần có để Repo 4 lắp ráp). Cần review lại nếu tỉ lệ
#   incomplete > 50% qua dry-run (mục 2.5 Spec).
# ---------------------------------------------------------------------------
LIBRARY_REQUIRED_FIELDS: dict[str, list[str]] = {
    "species": ["skin_color", "prompt_keywords"],
    "creature": ["prompt_keywords"],
    "flora": ["prompt_keywords"],
    "architecture": ["style", "material"],
    "costume": ["prompt_keywords"],
    "technology": ["prompt_keywords"],
    "culture": ["prompt_keywords"],
    "character_blueprint": ["prompt_keywords"],
    "visual_style": ["style_preset"],
    # "occupation": không khai báo vì không bao giờ route tới đây (không có
    # nguồn harvest) — nếu vô tình lọt qua, gate sẽ dùng default [\"prompt_keywords\"].
}
