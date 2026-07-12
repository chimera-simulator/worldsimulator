"""
distillers/registry.py — DistillerRegistry
=============================================
Registry tĩnh ánh xạ library_type -> class Distiller. Đăng ký thủ công
(KHÔNG dùng auto-discovery/import-scan) để tường minh, dễ audit — đúng
tinh thần "nếu Python if/else làm được thì không đưa cho LLM/tự động
hoá quá đà" của tài liệu gốc §101.
"""
from __future__ import annotations

from typing import Optional, Type

from distillers.base import BaseLibraryDistiller


class DistillerRegistry:
    _registry: dict[str, Type[BaseLibraryDistiller]] = {}

    @classmethod
    def register(cls, library_type: str, distiller_cls: Type[BaseLibraryDistiller]) -> None:
        """Đăng ký 1 Distiller cho 1 library_type. Cho phép override có chủ
        đích (VD test dùng mock Distiller) — không raise nếu đã tồn tại,
        chỉ log qua caller nếu cần audit."""
        cls._registry[library_type] = distiller_cls

    @classmethod
    def get(cls, library_type: str) -> Optional[Type[BaseLibraryDistiller]]:
        return cls._registry.get(library_type)

    @classmethod
    def all_registered_types(cls) -> list[str]:
        """Tiện ích cho test/observability — liệt kê mọi library_type đã
        có Distiller thật (khác với LibraryType Literal đầy đủ 10 giá trị
        trong lib_entity.py, một số có thể CHƯA có Distiller impl)."""
        return sorted(cls._registry.keys())


# ---------------------------------------------------------------------------
# Đăng ký các Distiller đã implement. Import ở cuối file (sau khi class
# DistillerRegistry đã định nghĩa xong) để tránh circular import với các
# module distillers/*.py (chúng không cần import ngược registry).
# ---------------------------------------------------------------------------
from distillers.species import SpeciesDistiller        # noqa: E402
from distillers.architecture import ArchitectureDistiller  # noqa: E402
from distillers.stubs import CreatureDistiller          # noqa: E402 (giữ creature stub)
from distillers.planet import PlanetDistiller           # noqa: E402 (MỚI — real impl, SPEC_FIX_2_6)
from distillers.technology import TechnologyDistiller  # noqa: E402
from distillers.culture import CultureDistiller  # noqa: E402
from distillers.character_blueprint import CharacterBlueprintDistiller  # noqa: E402
from distillers.visual_style import VisualStyleDistiller  # noqa: E402
from distillers.flora import FloraDistiller  # noqa: E402
from distillers.costume import CostumeDistiller  # noqa: E402

DistillerRegistry.register("species", SpeciesDistiller)
DistillerRegistry.register("architecture", ArchitectureDistiller)
DistillerRegistry.register("creature", CreatureDistiller)
DistillerRegistry.register("technology", TechnologyDistiller)
DistillerRegistry.register("culture", CultureDistiller)
DistillerRegistry.register("character_blueprint", CharacterBlueprintDistiller)
DistillerRegistry.register("visual_style", VisualStyleDistiller)
DistillerRegistry.register("flora", FloraDistiller)
DistillerRegistry.register("costume", CostumeDistiller)

# [MỚI — SPEC_FIX_2_6 §CODER 2 phần E] PlanetDistiller: implementation
# thật (distillers/planet.py), thay thế stub cũ trong distillers/stubs.py
# (stub vẫn giữ nguyên trong file đó — tham khảo lịch sử, không xoá).
# Đăng ký dưới CẢ HAI key:
#   - "planet"             → key chính thức, khớp library_type mới trong
#                             LibraryType Literal (schemas/lib_entity.py)
#                             và route_library_type() (library_routing.py).
#   - "planet_environment" → alias cũ, giữ tương thích ngược cho bất kỳ
#                             caller nào còn tra registry bằng entity_type
#                             gốc thay vì library_type đã suy luận.
DistillerRegistry.register("planet", PlanetDistiller)
DistillerRegistry.register("planet_environment", PlanetDistiller)
