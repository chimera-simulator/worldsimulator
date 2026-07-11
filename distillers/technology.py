"""
distillers/technology.py — TechnologyDistiller (mục 22 tài liệu Architect)
=============================================================================
Khác với SpeciesDistiller/ArchitectureDistiller, Visual Blueprint 3.0
KHÔNG có sub-key riêng cho công nghệ (schema hiện tại chỉ có
character_blueprint / clothing_and_gear / environment_blueprint —
xem PHẦN 2 tài liệu, mục 28.5 "Visual Blueprint 3.0 - Prompt-Ready
Structure"). Công nghệ trong hệ thống (mục 22 — Technology Library:
xe/robot/tàu/phi thuyền/máy móc/công cụ) thường gắn với hành tinh/nền
văn minh nên fallback đọc từ blueprint.environment_blueprint, tương tự
cách ArchitectureDistiller đọc environment_blueprint cho kiến trúc.

NẾU environment_blueprint không có field công nghệ nào (payload rỗng),
_extract_payload() trả {} — required_fields (chỉ có "prompt_keywords",
xem LIBRARY_REQUIRED_FIELDS["technology"] trong library_routing.py) sẽ
buộc base.distill() kích hoạt LLM fallback (structure_via_llm) đọc từ
schema_record gốc (form_2_civilization_layer.society_and_infrastructure.
technology_patterns) — ĐÚNG cơ chế Gap-Filling Station mô tả ở mục 28.4.

⚠️ CẦN SẾP DUYỆT: nếu muốn nguồn dữ liệu ổn định hơn (không phụ thuộc
LLM fallback mỗi lần), cân nhắc bổ sung 1 sub-key "technology_blueprint"
riêng vào Visual Blueprint 3.0 (schemas/visual_blueprint_3_0.py) — thay
đổi này NẰM NGOÀI phạm vi SPEC hiện tại (chỉ viết Distiller, không sửa
schema nguồn).
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class TechnologyDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "technology"
    # Bám đúng LIBRARY_REQUIRED_FIELDS["technology"] trong library_routing.py
    # — baseline tối thiểu vì chưa có đặc tả field bắt buộc riêng (xem
    # ghi chú đầu file library_routing.py mục 87-89).
    required_fields: ClassVar[list] = ["prompt_keywords"]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}
        if not blueprint:
            return payload

        # Fallback nguồn duy nhất hiện có: environment_blueprint (công
        # nghệ gắn với hành tinh/kiến trúc, VD phương tiện, máy móc công
        # nghiệp của một nền văn minh) — KHÔNG có sub-key
        # "technology_blueprint" trong schema hiện tại.
        environment = blueprint.get("environment_blueprint") or {}

        # technology_type: xe/robot/tàu/phi thuyền/máy móc/công cụ (mục 22).
        # Không có field cố định trong environment_blueprint cho việc này
        # — thử một vài tên field khả dĩ tuỳ nguồn harvest, an toàn None
        # nếu không có gì.
        technology_type = (
            environment.get("technology_type")
            or environment.get("vehicle_type")
            or environment.get("machine_type")
            or ""
        )
        if technology_type:
            payload["technology_type"] = technology_type

        # category — nhóm công nghệ tổng quát (VD "transportation",
        # "energy", "tool"). Không có nguồn ổn định → best-effort fallback.
        category = environment.get("technology_category") or environment.get("category") or ""
        if category:
            payload["category"] = category

        # energy_source — nguồn năng lượng (mục 22: Energy trong
        # Technology Library gốc). environment_blueprint.lighting đôi khi
        # mô tả năng lượng phát sáng (bioluminescent, plasma...) nên dùng
        # làm fallback hợp lý khi không có field energy riêng.
        lighting = environment.get("lighting") or {}
        energy_source = (
            environment.get("energy_source")
            or (lighting.get("type") if isinstance(lighting, dict) else "")
            or ""
        )
        if energy_source:
            payload["energy_source"] = energy_source

        # material — chất liệu chế tạo công nghệ. fallback field môi
        # trường chung "material"/"primary_material" (đã dùng ở
        # ArchitectureDistiller cho cùng lý do: schema không tách riêng).
        material = environment.get("material") or environment.get("primary_material") or ""
        if material:
            payload["material"] = material

        # civilization_level — mức độ văn minh (Technology Library gốc:
        # Civilization_Level). Không có trong environment_blueprint hiện
        # tại của Visual Blueprint 3.0 mẫu — để None/rỗng, chờ Gap-Filling
        # Station hoặc bổ sung schema sau này.
        civilization_level = environment.get("civilization_level") or ""
        if civilization_level:
            payload["civilization_level"] = civilization_level

        # prompt_fragment — mô tả hình ảnh công nghệ, dùng luôn
        # prompt_fragment cấp environment nếu có (không có field công
        # nghệ riêng để lấy fragment chuyên biệt).
        prompt_fragment = environment.get("prompt_fragment") or ""
        if prompt_fragment:
            payload["prompt_fragment"] = prompt_fragment

        # prompt_keywords (required) — KHÔNG lấy ở đây theo field riêng vì
        # base._extract_prompt_keywords() đã tự động fallback đọc
        # blueprint["pre_built_prompts"] nếu payload không có key này (xem
        # base.py bước 3). Chỉ set tường minh nếu environment có sẵn field
        # đặc thù để tránh phải phụ thuộc pre_built_prompts (vốn được xây
        # cho nhân vật/species, không phải công nghệ).
        prompt_keywords = environment.get("prompt_keywords") or ""
        if prompt_keywords:
            payload["prompt_keywords"] = prompt_keywords

        return payload
