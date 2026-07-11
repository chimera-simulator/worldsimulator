"""
distillers/species.py — SpeciesDistiller
===========================================
Map field từ character_blueprint (Visual Blueprint 3.0) vào lib_species
chuẩn (mục 17 tài liệu Architect). Tách 1-1 từ nhánh
"species/creature/character_blueprint" cũ trong extract_from_blueprint()
của t4_5_library_distill.py — KHÔNG đổi logic, chỉ đổi nơi chứa.
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class SpeciesDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "species"
    # Bám đúng LIBRARY_REQUIRED_FIELDS["species"] trong library_routing.py
    # — skin_color là nhận dạng thị giác chính, prompt_keywords là output
    # sẵn cho Repo 4 (được base._extract_prompt_keywords() điền, không cần
    # khai báo lại ở đây).
    required_fields: ClassVar[list] = ["skin_color", "prompt_keywords"]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}

        character = blueprint.get("character_blueprint") or {}
        physical = character.get("physical_attributes") or {}
        skin = physical.get("skin") or {}
        height_info = physical.get("height") or {}
        species_base = character.get("species_base") or {}

        # skin_color: ưu tiên base_color (giá trị có cấu trúc), fallback
        # prompt_fragment (câu mô tả tự do đã viết sẵn cho prompt)
        skin_color = skin.get("base_color") or skin.get("prompt_fragment") or ""
        if skin_color:
            payload["skin_color"] = skin_color

        # height — giữ nguyên string value, KHÔNG parse ra số (đơn vị có
        # thể khác nhau giữa các nguồn, việc chuẩn hoá đơn vị không thuộc
        # phạm vi Gate 6.5)
        height_val = height_info.get("value") or ""
        if height_val:
            payload["height"] = height_val

        # face / eye / hair / hand / foot / horn / tail / ear — mỗi field
        # có thể nằm ở character_blueprint (top-level) hoặc physical_attributes
        # tuỳ nguồn harvest; ưu tiên character trước, fallback physical.
        for feature_key in ("face", "eye", "hair", "hand", "foot", "horn", "tail", "ear"):
            feature = character.get(feature_key) or physical.get(feature_key) or {}
            if isinstance(feature, dict):
                frag = feature.get("prompt_fragment") or ""
                if frag:
                    payload[feature_key] = frag
            elif feature:
                # Trường hợp nguồn cũ lưu thẳng string thay vì dict có
                # prompt_fragment — giữ tương thích ngược.
                payload[feature_key] = str(feature)

        # species_base_prompt — mô tả gốc loài (VD "amphibious humanoid,
        # deep-sea adapted"), dùng làm anchor cho consistency_lock.
        base_frag = species_base.get("prompt_fragment") or ""
        if base_frag:
            payload["species_base_prompt"] = base_frag

        # additional_features — list tự do cho các đặc điểm không thuộc
        # tập field cố định ở trên (VD "gill slits", "webbed fingers").
        additional = character.get("additional_features") or []
        if additional:
            payload["additional_features"] = additional

        return payload
