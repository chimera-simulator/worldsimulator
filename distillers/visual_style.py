"""
distillers/visual_style.py — VisualStyleDistiller (mục 25 tài liệu Architect)
================================================================================
Nguồn: blueprint.prompt_metadata (style_preset, quality_tags, resolution,
aspect_ratio) + blueprint.environment_blueprint.lighting (ánh sáng, dùng
làm proxy cho "độ chi tiết"/lighting_style vì Visual Blueprint 3.0 không
có field "detail_level" tường minh — quality_tags là nguồn gần nhất).

Mục 25 tài liệu gốc: "Visual Style Library... định nghĩa: Màu sắc, Ánh
sáng, Độ chi tiết, Chất liệu, Cách dựng hình. Điều này giúp hàng trăm
tập phim có cùng bản sắc hình ảnh." — VisualStyleDistiller là Distiller
DUY NHẤT đọc trực tiếp prompt_metadata (mọi Distiller khác đọc
character_blueprint/environment_blueprint/clothing_and_gear).
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class VisualStyleDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "visual_style"
    # Bám đúng LIBRARY_REQUIRED_FIELDS["visual_style"] trong
    # library_routing.py — style_preset là trụ cột nhận dạng phong cách.
    required_fields: ClassVar[list] = ["style_preset"]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}
        if not blueprint:
            return payload

        metadata = blueprint.get("prompt_metadata") or {}
        environment = blueprint.get("environment_blueprint") or {}
        lighting = environment.get("lighting") or {}

        # style_preset (required) — VD "semi_realistic_sci_fi" trong mẫu
        # Visual Blueprint 3.0 (mục 28.5).
        style_preset = metadata.get("style_preset") or ""
        if style_preset:
            payload["style_preset"] = style_preset

        # color_palette — không có field cố định riêng cho "màu sắc tổng
        # thể" trong prompt_metadata; dùng sky/lighting color của
        # environment_blueprint làm proxy hợp lý nhất hiện có (mục 25:
        # "Màu sắc" là 1 trong các trục style). Fallback rỗng nếu thiếu.
        sky = environment.get("sky") or {}
        color_palette = (
            environment.get("color_palette")
            or lighting.get("color")
            or sky.get("color")
            or ""
        )
        if color_palette:
            payload["color_palette"] = color_palette

        # lighting_style — environment_blueprint.lighting.type ưu tiên
        # (giá trị có cấu trúc, VD "bioluminescent"), fallback
        # prompt_fragment (mô tả tự do, VD "soft bioluminescent lighting,
        # cyan ambient glow").
        lighting_style = lighting.get("type") or lighting.get("prompt_fragment") or ""
        if lighting_style:
            payload["lighting_style"] = lighting_style

        # detail_level — suy từ quality_tags (VD "masterpiece, best
        # quality, ultra detailed, 8k") vì không có field số/enum riêng
        # cho độ chi tiết trong schema hiện tại. Giữ nguyên chuỗi thay vì
        # cố gắng parse thành số/enum (tránh suy diễn sai).
        detail_level = metadata.get("quality_tags") or ""
        if detail_level:
            payload["detail_level"] = detail_level

        # material_rendering — cách dựng hình (VD "3D Stylized"/"Semi
        # Realistic"/"Anime"/"Painterly" theo mục 25). Không có field
        # riêng biệt với style_preset trong prompt_metadata — dùng lại
        # style_preset làm giá trị material_rendering khi không có field
        # "rendering_style"/"material_rendering" riêng, để tránh bỏ trống
        # một field có ý nghĩa tương đương.
        material_rendering = (
            metadata.get("rendering_style")
            or metadata.get("material_rendering")
            or style_preset
            or ""
        )
        if material_rendering:
            payload["material_rendering"] = material_rendering

        # resolution — VD "1024x1536"
        resolution = metadata.get("resolution") or ""
        if resolution:
            payload["resolution"] = resolution

        # aspect_ratio — VD "2:3"
        aspect_ratio = metadata.get("aspect_ratio") or ""
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio

        # prompt_keywords — VisualStyleDistiller không bắt buộc field này
        # (required_fields chỉ có style_preset), nhưng vẫn set nếu
        # metadata/environment có sẵn quality_tags để hữu ích cho Repo 4;
        # nếu không, base._extract_prompt_keywords() sẽ fallback đọc
        # pre_built_prompts như mọi Distiller khác.
        prompt_keywords = metadata.get("quality_tags") or ""
        if prompt_keywords:
            payload["prompt_keywords"] = prompt_keywords

        return payload
