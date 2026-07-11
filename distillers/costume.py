"""
distillers/costume.py — CostumeDistiller
===========================================
Map field từ `blueprint.clothing_and_gear` (key top-level riêng của
VisualBlueprint30 — KHÔNG lồng trong character_blueprint) vào lib_costume
chuẩn (mục 21 tài liệu Architect).

`planet_compatibility` / `species_compatibility` KHÔNG có nguồn trực tiếp
trong Visual Blueprint 3.0 hiện tại (chỉ có `visual_id` gợi ý species gốc
qua liên kết ngoài) — để "" / đánh cờ `inferred_by_llm`, chờ Gap-Filling
Station điền, tuyệt đối KHÔNG bịa.
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class CostumeDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "costume"
    # Bám đúng LIBRARY_REQUIRED_FIELDS["costume"] trong library_routing.py
    required_fields: ClassVar[list] = ["prompt_keywords"]

    # Từ khoá suy luận costume_type từ armor.type / accessories[].type khi
    # nguồn harvest không gắn tag rõ ràng — heuristic tối thiểu, KHÔNG phải
    # phân loại thời trang học, chỉ để có giá trị mặc định hợp lý.
    _COSTUME_TYPE_KEYWORDS: ClassVar[list] = [
        ("armor", "giáp"),
        ("giáp", "giáp"),
        ("plate", "giáp"),
        ("helmet", "mũ"),
        ("mũ", "mũ"),
        ("hat", "mũ"),
        ("glove", "găng tay"),
        ("gauntlet", "găng tay"),
        ("găng tay", "găng tay"),
        ("boot", "giày"),
        ("shoe", "giày"),
        ("giày", "giày"),
        ("dress", "váy"),
        ("skirt", "váy"),
        ("váy", "váy"),
        ("pants", "quần"),
        ("trouser", "quần"),
        ("quần", "quần"),
        ("jewel", "trang sức"),
        ("accessory", "trang sức"),
        ("trang sức", "trang sức"),
        ("shirt", "áo"),
        ("robe", "áo"),
        ("áo", "áo"),
    ]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}
        if not isinstance(blueprint, dict):
            return payload

        clothing = blueprint.get("clothing_and_gear") or {}
        if not isinstance(clothing, dict) or not clothing:
            return payload

        armor = clothing.get("armor") or {}
        if not isinstance(armor, dict):
            armor = {}
        accessories = clothing.get("accessories") or []
        if not isinstance(accessories, list):
            accessories = [accessories] if accessories else []

        # --- costume_type: ưu tiên armor.type, fallback armor.category,
        # fallback suy từ accessories[0].type / prompt_fragment, cuối cùng
        # heuristic từ khoá.
        costume_type = (
            armor.get("type")
            or armor.get("category")
            or self._first_accessory_type(accessories)
            or self._infer_costume_type(armor, accessories)
            or ""
        )
        if costume_type:
            payload["costume_type"] = costume_type

        # --- material: armor.material
        material = armor.get("material") or ""
        if material:
            payload["material"] = material

        # --- color: armor.color
        color = armor.get("color") or ""
        if color:
            payload["color"] = color

        # --- coverage: armor.coverage
        coverage = armor.get("coverage") or ""
        if coverage:
            payload["coverage"] = coverage

        # --- style: nếu có (không phải field bắt buộc trong armor theo
        # spec Visual Blueprint 3.0 hiện tại, nhưng giữ chỗ nếu nguồn có)
        style = armor.get("style") or clothing.get("style") or ""
        if style:
            payload["style"] = style

        # --- planet_compatibility / species_compatibility: KHÔNG có nguồn
        # trực tiếp trong Visual Blueprint hiện tại -> đánh cờ chờ
        # Gap-Filling Station, KHÔNG bịa giá trị.
        payload["planet_compatibility"] = armor.get("planet_compatibility") or "inferred_by_llm"
        payload["species_compatibility"] = armor.get("species_compatibility") or "inferred_by_llm"

        # --- accessories: copy list gốc nguyên vẹn
        if accessories:
            payload["accessories"] = accessories

        # prompt_keywords được base._extract_prompt_keywords() tự động điền
        # từ pre_built_prompts nếu payload không set — không lặp lại ở đây.

        return payload

    def _first_accessory_type(self, accessories: list) -> str:
        for item in accessories:
            if isinstance(item, dict):
                t = item.get("type") or ""
                if t:
                    return str(t)
        return ""

    def _infer_costume_type(self, armor: dict, accessories: list) -> str:
        """Heuristic tối thiểu: dò từ khoá trong armor/accessories để gán
        1 trong 8 loại costume_type theo mục 21 tài liệu Architect. Trả ""
        nếu không khớp gì — KHÔNG bịa loại."""
        text_parts = []
        if isinstance(armor, dict):
            text_parts.extend(
                str(armor.get(k, "")) for k in ("prompt_fragment", "type", "category", "coverage")
            )
        for item in accessories:
            if isinstance(item, dict):
                text_parts.append(str(item.get("prompt_fragment", "")))
                text_parts.append(str(item.get("type", "")))
        text = " ".join(text_parts).lower()
        if not text.strip():
            return ""
        for keyword, ctype in self._COSTUME_TYPE_KEYWORDS:
            if keyword in text:
                return ctype
        return ""
