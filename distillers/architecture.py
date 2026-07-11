"""
distillers/architecture.py — ArchitectureDistiller
=====================================================
Map field từ environment_blueprint vào lib_architecture chuẩn (mục 20
tài liệu Architect): style, material, roof + mọi field môi trường khác.
Tách 1-1 từ nhánh "flora/architecture" cũ trong extract_from_blueprint().

Lưu ý: nhánh cũ dùng CHUNG code cho cả "flora" và "architecture" (cùng
đọc environment_blueprint). Theo kiến trúc mới, FloraDistiller là 1 class
riêng (không thuộc phạm vi SPEC này) sẽ tái dùng same pattern nhưng
required_fields khác (theo LIBRARY_REQUIRED_FIELDS["flora"] =
["prompt_keywords"], không bắt buộc style/material như architecture).
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class ArchitectureDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "architecture"
    # Bám đúng LIBRARY_REQUIRED_FIELDS["architecture"] — style + material
    # là 2 trụ cột nhận dạng thị giác cho kiến trúc.
    required_fields: ClassVar[list] = ["style", "material"]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}
        environment = blueprint.get("environment_blueprint") or {}
        if not environment:
            return payload

        # style: ưu tiên field "style", fallback "style_preset" (tên field
        # có thể khác nhau tuỳ phiên bản Visual Blueprint nguồn)
        style = environment.get("style") or environment.get("style_preset") or ""
        if style:
            payload["style"] = style

        # material: ưu tiên "material", fallback "primary_material"
        material = environment.get("material") or environment.get("primary_material") or ""
        if material:
            payload["material"] = material

        # roof — field đặc thù kiến trúc (mục 20 tài liệu Architect), không
        # có trong nhánh flora nên xử lý riêng ở đây thay vì loop chung.
        roof = environment.get("roof") or environment.get("roof_type") or ""
        if roof:
            payload["roof"] = roof

        # Copy toàn bộ field môi trường còn lại (structure, ornamentation,
        # scale, foundation, v.v. — bất kỳ field nào nguồn harvest có sẵn),
        # KHÔNG whitelist cứng vì các nguồn worldbuilding khác nhau có thể
        # mô tả kiến trúc bằng field tên khác nhau. Chỉ bỏ qua field đã gán
        # ở trên để tránh ghi đè, và bỏ qua giá trị rỗng/falsy.
        for k, v in environment.items():
            if k not in payload and v:
                payload[k] = v

        return payload
