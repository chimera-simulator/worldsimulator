"""
distillers/flora.py — FloraDistiller
=======================================
Map field từ environment_blueprint vào lib_flora chuẩn (mục 19 tài liệu
Architect). Dùng CHUNG pattern nguồn với ArchitectureDistiller (comment
trong distillers/architecture.py đã xác nhận: nhánh cũ đọc chung
environment_blueprint cho cả flora/architecture), nhưng required_fields
khác — theo LIBRARY_REQUIRED_FIELDS["flora"] = ["prompt_keywords"], KHÔNG
bắt buộc style/material như architecture vì flora không phải công trình.
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class FloraDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "flora"
    # Bám đúng LIBRARY_REQUIRED_FIELDS["flora"] trong library_routing.py
    required_fields: ClassVar[list] = ["prompt_keywords"]

    # Từ khoá suy luận flora_type từ prompt_fragment/biome khi nguồn harvest
    # không gắn tag rõ ràng — heuristic tối thiểu, KHÔNG phải phân loại
    # thực vật học, chỉ để có giá trị mặc định hợp lý thay vì để trống.
    _FLORA_TYPE_KEYWORDS: ClassVar[list] = [
        ("mushroom", "nấm"),
        ("fungus", "nấm"),
        ("nấm", "nấm"),
        ("flower", "hoa"),
        ("bloom", "hoa"),
        ("hoa", "hoa"),
        ("moss", "rong"),
        ("algae", "rong"),
        ("kelp", "rong"),
        ("rong", "rong"),
        ("forest", "rừng"),
        ("jungle", "rừng"),
        ("rừng", "rừng"),
        ("bush", "bụi cây"),
        ("shrub", "bụi cây"),
        ("bụi cây", "bụi cây"),
        ("tree", "cây"),
        ("cây", "cây"),
    ]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}
        if not isinstance(blueprint, dict):
            return payload

        environment = blueprint.get("environment_blueprint") or {}
        if not isinstance(environment, dict) or not environment:
            return payload

        # --- flora_type: suy từ prompt_fragment/biome, fallback rỗng nếu
        # không khớp từ khoá nào (chờ Gap-Filling điền).
        flora_type = self._infer_flora_type(environment)
        if flora_type:
            payload["flora_type"] = flora_type

        # --- color: ưu tiên field "color" có cấu trúc, fallback suy từ
        # prompt_fragment (không parse, giữ nguyên câu mô tả)
        color = environment.get("color") or environment.get("base_color") or ""
        if not color:
            lighting = environment.get("lighting") or {}
            if isinstance(lighting, dict):
                color = lighting.get("color") or ""
        if color:
            payload["color"] = color

        # --- size
        size = environment.get("size") or environment.get("scale") or ""
        if size:
            payload["size"] = size

        # --- shape: environment.shape hoặc structure
        shape = environment.get("shape") or environment.get("structure") or ""
        if shape:
            payload["shape"] = shape

        # --- environment_habitat: environment.biome
        habitat = environment.get("biome") or ""
        if habitat:
            payload["environment_habitat"] = habitat

        # --- glow_or_bioluminescence: tái dùng pattern glow_effects như
        # species (species.physical_attributes.glow_effects), nhưng ở đây
        # field có thể nằm trực tiếp trong environment_blueprint.
        glow = environment.get("glow_effects") or environment.get("bioluminescence") or {}
        if isinstance(glow, dict) and glow:
            glow_frag = glow.get("prompt_fragment") or ""
            if glow_frag:
                payload["glow_or_bioluminescence"] = glow_frag
            elif glow.get("enabled"):
                payload["glow_or_bioluminescence"] = "bioluminescent"
        elif isinstance(glow, str) and glow:
            payload["glow_or_bioluminescence"] = glow

        # --- copy toàn bộ field còn lại của environment_blueprint không
        # trùng key (giống cách ArchitectureDistiller copy phần dư), bỏ
        # qua giá trị rỗng/falsy để không ghi đè bằng rác.
        for k, v in environment.items():
            if k not in payload and v:
                payload[k] = v

        return payload

    def _infer_flora_type(self, environment: dict) -> str:
        """Heuristic tối thiểu: dò từ khoá trong prompt_fragment/biome để
        gán 1 trong 6 loại flora_type theo mục 19 tài liệu Architect.
        Trả "" nếu không khớp gì — KHÔNG bịa loại."""
        if not isinstance(environment, dict):
            return ""
        text = " ".join(
            str(environment.get(k, ""))
            for k in ("prompt_fragment", "biome", "planet_type", "name")
        ).lower()
        if not text.strip():
            return ""
        for keyword, ftype in self._FLORA_TYPE_KEYWORDS:
            if keyword in text:
                return ftype
        return ""
