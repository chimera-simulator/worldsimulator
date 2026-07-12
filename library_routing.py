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
    # [MỚI — SPEC_FIX_2_6 §CODER 2] Flora (ecosystem foundation) — path CỤ
    # THỂ hơn "form_1_planet_foundation" chung (planet, xem entry ngay dưới)
    # nên PHẢI đứng TRƯỚC, đúng quy ước "path dài/cụ thể hơn đứng trước path
    # ngắn/chung hơn" đã ghi ở đầu file.
    #
    # LƯU Ý LỆCH SO VỚI VĂN BẢN SPEC (mục 2 §CODER 2 phần A): SPEC yêu cầu
    # đặt entry ("form_1_planet_foundation", "planet") TRƯỚC entry
    # ecosystem_foundation. Làm đúng y văn bản đó sẽ khiến MỌI dot-path
    # ecosystem_foundation.* (vì cũng startswith "form_1_planet_foundation")
    # bị entry "planet" nuốt mất trước khi vòng lặp chạm tới entry "flora"
    # — route_library_type() dùng "return ở match đầu tiên", nên flora sẽ
    # KHÔNG BAO GIỜ được chọn nữa, phá vỡ toàn bộ FloraDistiller đang hoạt
    # động. Giữ đúng tinh thần thật của SPEC (field planet_identity.* phải
    # về "planet", không lọt vào flora — điều này ĐÃ đúng vì flora chỉ match
    # "...ecosystem_foundation", không match "...planet_identity") bằng
    # cách đặt flora (cụ thể hơn) trước, planet (chung hơn, bắt phần còn lại
    # của form_1_planet_foundation.*) sau. Hành vi cuối cùng giống hệt ý đồ
    # của SPEC, chỉ đổi thứ tự khai báo để không vỡ flora.
    ("form_1_planet_foundation.ecosystem_foundation", "flora"),

    # [MỚI — SPEC_FIX_2_6] Planet — bắt phần còn lại của
    # form_1_planet_foundation.* (planet_identity, v.v.) mà KHÔNG phải
    # ecosystem_foundation (đã match ở entry flora bên trên).
    ("form_1_planet_foundation", "planet"),

    # Species (biology / morphology)
    ("form_2_civilization_layer.biology_and_behavior", "species"),

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

    # [CẬP NHẬT — SPEC_FIX_2_6] "form_1_planet_foundation" (entry ở trên) giờ
    # bắt được các dot-path của planet_environment qua target_form_field.
    # Ghi chú cũ ở đây ("KHÔNG có entry cho planet_environment") đã hết hiệu
    # lực kể từ SPEC_PLANET_ROTATION_MASTER.md — xem thêm fallback tương ứng
    # trong ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE bên dưới cho trường hợp
    # target_form_field rỗng.
]

# ---------------------------------------------------------------------------
# Fallback khi target_form_field rỗng hoặc không match bảng trên.
# Dùng blueprint.entity_type trực tiếp (áp dụng khi entity_type nằm trong
# tập hợp lệ của VisualBlueprint30). [CẬP NHẬT — SPEC_FIX_2_6]
# "planet_environment" nay CÓ entry → "planet" (trước đây cố ý bỏ trống).
# ---------------------------------------------------------------------------
ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE: dict[str, str] = {
    "species": "species",
    "creature": "creature",
    "architecture": "architecture",
    # [MỚI — SPEC_FIX_2_6 §CODER 2] planet_environment (entity_type cũ của
    # VisualBlueprint30) giờ có library_type tương ứng — "planet". Trước đây
    # cố ý KHÔNG có entry (route trả None); nay bổ sung theo mục 2 §CODER 2
    # phần B của SPEC_PLANET_ROTATION_MASTER.md.
    "planet_environment": "planet",
}

# ---------------------------------------------------------------------------
# [SPEC_FIX_2_6 §CODER 2 phần C] LIBRARY_REQUIRED_FIELDS ĐÃ DI CHUYỂN sang
# config.py (Coder 1 sở hữu — xem config.py, ngay dưới PLANET_TYPE_CATALOG).
# Theo quy tắc §4.6 SPEC_PLANET_ROTATION_MASTER.md, dict này chỉ được định
# nghĩa 1 nơi DUY NHẤT. Import + re-export ở đây để bất kỳ module nào đang
# `from library_routing import LIBRARY_REQUIRED_FIELDS` (VD:
# t4_5_library_distill.py) không bị vỡ — KHÔNG cần sửa nơi khác.
#
# Bản định nghĩa cũ tại đây (trước bản này) đã được xoá theo đúng lộ trình
# Coder 1 mô tả trong CODER1_DELIVERABLE_NOTES_PLANET_ROTATION.md: "Coder 2
# sẽ đổi library_routing.py sang import từ config trước khi bản cũ được dọn
# ở merge review cuối cùng" — merge review đó chính là bước này.
# ---------------------------------------------------------------------------
from config import LIBRARY_REQUIRED_FIELDS  # noqa: E402, F401 (re-export cho backward compat)
