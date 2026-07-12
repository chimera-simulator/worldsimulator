"""
distillers/planet.py — PlanetDistiller
=========================================
Distill planet archetype document thành lib_planet entity. Đọc từ
environment_blueprint (Visual Blueprint 3.0) theo chiến lược tương tự
FloraDistiller (cùng đọc environment_blueprint, khác required_fields).

Sở hữu: Coder 2 (mục 2 §CODER 2 phần D — SPEC_PLANET_ROTATION_MASTER.md)
Nguồn tham khảo: distillers/flora.py (pattern _extract_payload),
distillers/base.py (Template Method BaseLibraryDistiller).

LƯU Ý về required_fields (lệch nhỏ so với snippet ví dụ trong SPEC):
SPEC mục 2 §CODER 2 phần D minh hoạ `required_fields` bằng đúng 4 dot-path
đầy đủ của `config.LIBRARY_REQUIRED_FIELDS["planet"]`
(VD: "form_1_planet_foundation.planet_identity.planet_type"). Nhưng
BaseLibraryDistiller.distill() (xem distillers/base.py, bước 4) check
required_fields bằng cách tra cứu KEY PHẲNG trong `merged_for_check`
(payload đã extract, VD "planet_type") — không phải dot-path. Đây là 2
namespace khác nhau trong toàn bộ kiến trúc:
  - config.LIBRARY_REQUIRED_FIELDS["planet"] (dot-path) → dùng bởi Gate 5
    (t3_normalize.py::check_planet_required_fields(), Coder 3) để check
    trên schema_record gốc.
  - required_fields của Distiller (flat key, giống SpeciesDistiller
    ["skin_color", "prompt_keywords"], FloraDistiller ["prompt_keywords"])
    → dùng bởi Gate 6.5 (BaseLibraryDistiller.distill()) để check trên
    payload đã extract.
Nếu dùng nguyên dot-path làm required_fields ở đây, merged_for_check.get(f)
sẽ luôn trả None (payload không có key dạng dot-path) → mọi planet document
đều bị đánh dấu status="incomplete" vĩnh viễn dù đã extract đủ dữ liệu, kể
cả khi Gate 5 đã pass. Vì vậy required_fields ở đây dùng flat key khớp
đúng tên payload do _extract_payload() sinh ra, đồng nhất với 4 field bắt
buộc theo mục 1.4/2.5 Spec (chỉ khác định dạng key, KHÔNG khác ý nghĩa
nghiệp vụ) — vẫn đúng "prefix cuối" của 4 dot-path trong
config.LIBRARY_REQUIRED_FIELDS["planet"].
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class PlanetDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "planet"

    # Flat key khớp payload do _extract_payload() sinh ra (xem docstring
    # module ở trên về lý do KHÔNG dùng dot-path đầy đủ như
    # config.LIBRARY_REQUIRED_FIELDS["planet"] ở đây).
    required_fields: ClassVar[list] = [
        "planet_type",
        "terrain_patterns",
        "climate_patterns",
        "dominant_ecosystem",
    ]

    def _extract_payload(self, blueprint: dict) -> dict:
        """Trích xuất payload từ blueprint cho planet entity.

        Đọc chủ yếu từ `environment_blueprint` — với planet,
        `blueprint` là VisualBlueprint30 và `environment_blueprint` là nơi
        chứa terrain/climate/ecosystem data sau khi summarizer chạy (cùng
        nguồn dữ liệu mà FloraDistiller đọc, khác field trích ra).
        """
        payload: dict = {}
        if not isinstance(blueprint, dict):
            return payload

        environment = blueprint.get("environment_blueprint") or {}
        if not isinstance(environment, dict) or not environment:
            return payload

        # planet_type: ưu tiên giá trị có cấu trúc trong environment_blueprint,
        # fallback về entity_type của blueprint (VD "planet_environment")
        # khi nguồn harvest không gắn tag planet_type rõ ràng.
        planet_type = (
            environment.get("planet_type")
            or blueprint.get("entity_type", "")
            or ""
        )
        if planet_type:
            payload["planet_type"] = planet_type

        # terrain_patterns — luôn chuẩn hoá về list để nhất quán cho Repo 4.
        terrain = environment.get("terrain_patterns") or []
        if terrain:
            payload["terrain_patterns"] = terrain if isinstance(terrain, list) else [terrain]

        # climate_patterns
        climate = environment.get("climate_patterns") or []
        if climate:
            payload["climate_patterns"] = climate if isinstance(climate, list) else [climate]

        # dominant_ecosystem
        ecosystem = environment.get("dominant_ecosystem") or []
        if ecosystem:
            payload["dominant_ecosystem"] = ecosystem if isinstance(ecosystem, list) else [ecosystem]

        # energy_sources (bonus, không bắt buộc theo LIBRARY_REQUIRED_FIELDS)
        energy = environment.get("energy_sources") or []
        if energy:
            payload["energy_sources"] = energy if isinstance(energy, list) else [energy]

        # Copy phần dư còn lại của environment_blueprint không trùng key
        # (cùng convention với FloraDistiller/ArchitectureDistiller), bỏ
        # qua giá trị rỗng/falsy để không ghi đè bằng rác.
        for k, v in environment.items():
            if k not in payload and v:
                payload[k] = v

        return payload
