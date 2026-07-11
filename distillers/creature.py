"""
distillers/creature.py — CreatureDistiller
=============================================
Map field từ character_blueprint (biology/morphology — cùng nhánh với
Species) + environment_blueprint (habitat) + additional_features
(đặc điểm phi chuẩn: chimera parts, chi bất thường) vào lib_creature
chuẩn (mục 18 tài liệu Architect).

Khác Species ở chỗ creature có thể phi sinh học / không có màu da rõ
ràng, nên "prompt_keywords" là required duy nhất (theo
LIBRARY_REQUIRED_FIELDS["creature"] trong library_routing.py), không bắt
buộc skin_color như species.

Toàn bộ field lấy theo nguyên tắc "an toàn" — không có field nào được
coi là chắc chắn tồn tại trong nguồn harvest thực tế; mọi truy cập dùng
`.get(..) or {}` / `.get(..) or ""` để KHÔNG BAO GIỜ crash nếu nguồn
thiếu dữ liệu (Gap-Filling Station ở t3_normalize/summarizer sẽ điền bù
sau, hoặc LLM fallback trong base.distill() sẽ xử lý các required_fields
còn thiếu).
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class CreatureDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "creature"
    # Bám đúng LIBRARY_REQUIRED_FIELDS["creature"] trong library_routing.py
    required_fields: ClassVar[list] = ["prompt_keywords"]

    # Từ khoá suy luận creature_type từ species_base.name / prompt_fragment
    # khi nguồn harvest không gắn tag rõ ràng — đây là heuristic tối thiểu,
    # KHÔNG phải phân loại khoa học, chỉ để có giá trị mặc định hợp lý thay
    # vì để trống hoàn toàn.
    _CREATURE_TYPE_KEYWORDS: ClassVar[list] = [
        ("mount", "thú cưỡi"),
        ("cưỡi", "thú cưỡi"),
        ("ride", "thú cưỡi"),
        ("monster", "quái vật"),
        ("quái vật", "quái vật"),
        ("beast", "quái vật"),
        ("sea", "sinh vật biển"),
        ("marine", "sinh vật biển"),
        ("aquatic", "sinh vật biển"),
        ("biển", "sinh vật biển"),
        ("bird", "chim"),
        ("avian", "chim"),
        ("chim", "chim"),
        ("insect", "côn trùng"),
        ("côn trùng", "côn trùng"),
        ("bug", "côn trùng"),
        ("flying", "sinh vật bay"),
        ("fly", "sinh vật bay"),
        ("winged", "sinh vật bay"),
        ("bay", "sinh vật bay"),
    ]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}
        if not isinstance(blueprint, dict):
            return payload

        character = blueprint.get("character_blueprint") or {}
        environment = blueprint.get("environment_blueprint") or {}

        if not isinstance(character, dict):
            character = {}
        if not isinstance(environment, dict):
            environment = {}

        physical = character.get("physical_attributes") or {}
        if not isinstance(physical, dict):
            physical = {}
        species_base = character.get("species_base") or {}
        if not isinstance(species_base, dict):
            species_base = {}
        skin = physical.get("skin") or {}
        if not isinstance(skin, dict):
            skin = {}
        height_info = physical.get("height") or {}
        if not isinstance(height_info, dict):
            height_info = {}
        body_structure = physical.get("body_structure") or {}
        if not isinstance(body_structure, dict):
            body_structure = {}

        # --- creature_type: suy từ species_base.name hoặc prompt_fragment,
        # fallback rỗng nếu không khớp từ khoá nào (chờ Gap-Filling điền).
        creature_type = self._infer_creature_type(species_base)
        if creature_type:
            payload["creature_type"] = creature_type

        # --- size: từ physical_attributes.height (giữ nguyên string, không
        # parse số — cùng nguyên tắc với SpeciesDistiller.height)
        size_val = height_info.get("value") or height_info.get("prompt_fragment") or ""
        if size_val:
            payload["size"] = size_val

        # --- morphology: từ physical_attributes.body_structure.prompt_fragment
        morphology = body_structure.get("prompt_fragment") or ""
        if morphology:
            payload["morphology"] = morphology

        # --- habitat: từ environment_blueprint.biome
        habitat = environment.get("biome") or ""
        if habitat:
            payload["habitat"] = habitat

        # --- behavior_tags: không có nguồn Master Schema trực tiếp. Suy
        # tối thiểu từ additional_features (nếu mô tả có gợi ý hành vi),
        # nếu không có gì thì để list rỗng — chờ Gap-Filling Station điền
        # sau (KHÔNG bịa).
        additional = character.get("additional_features") or []
        if not isinstance(additional, list):
            additional = [additional] if additional else []
        behavior_tags = [str(item) for item in additional if item]
        if behavior_tags:
            payload["behavior_tags"] = behavior_tags

        # --- skin_or_hide: tương tự "skin" của species nhưng KHÔNG bắt buộc
        skin_or_hide = skin.get("base_color") or skin.get("prompt_fragment") or skin.get("texture") or ""
        if skin_or_hide:
            payload["skin_or_hide"] = skin_or_hide

        # --- additional_features: giữ nguyên list gốc (cùng field name như
        # Species) để Repo 4 đọc thống nhất giữa species/creature.
        if additional:
            payload["additional_features"] = additional

        # prompt_keywords được base._extract_prompt_keywords() tự động điền
        # từ pre_built_prompts nếu payload không set — không cần lặp lại ở
        # đây (tránh 2 nguồn sự thật).

        return payload

    def _infer_creature_type(self, species_base: dict) -> str:
        """Heuristic tối thiểu: dò từ khoá trong name/prompt_fragment để
        gán 1 trong 7 loại creature_type theo mục 18 tài liệu Architect.
        Trả "" nếu không khớp gì — KHÔNG bịa loại."""
        if not isinstance(species_base, dict):
            return ""
        text = " ".join(
            str(species_base.get(k, ""))
            for k in ("name", "prompt_fragment", "inspiration")
        ).lower()
        if not text.strip():
            return ""
        for keyword, ctype in self._CREATURE_TYPE_KEYWORDS:
            if keyword in text:
                return ctype
        return ""
