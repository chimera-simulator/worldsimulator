"""
tests/test_planet_distiller.py — Unit test cho PlanetDistiller + planet
routing (SPEC_PLANET_ROTATION_MASTER.md, mục 2 §CODER 2 "Test cần viết")
==========================================================================
Chạy: python3 -m unittest tests.test_planet_distiller -v  (từ thư mục repo1/)

Convention: unittest, không mock external service — giống
tests/test_library_distill.py (mẫu tham khảo trực tiếp).

LƯU Ý MÔI TRƯỜNG: các test đi qua distillers.registry / distillers.base /
t4_5_library_distill cần `pydantic` (dùng bởi schemas/lib_entity.py,
schemas/master_schema_2_0.py). Trong sandbox offline biên soạn zip này,
`pydantic` không cài được (không có mạng) — xem CODER2_DELIVERABLE_NOTES.md
mục "Kiểm chứng đã chạy". `requirements.txt` của repo đã có `pydantic`,
nên các test này sẽ chạy đầy đủ trong CI thật/máy có mạng.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library_routing import (  # noqa: E402
    ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE,
    TARGET_FORM_FIELD_TO_LIBRARY_TYPE,
)


# =============================================================================
# Helper: route trực tiếp trên bảng TARGET_FORM_FIELD_TO_LIBRARY_TYPE, KHÔNG
# import route_library_type() từ t4_5_library_distill.py để tránh kéo theo
# chuỗi import distillers.base -> schemas -> pydantic khi chỉ cần test bảng
# routing thuần (dùng cho các test không cần load Distiller thật).
# =============================================================================
def _route_by_table(target_form_field: str) -> str | None:
    for prefix, lib_type in TARGET_FORM_FIELD_TO_LIBRARY_TYPE:
        if target_form_field.startswith(prefix):
            return lib_type
    return None


# =============================================================================
# Test 4/5/6 trong SPEC — không cần pydantic, chạy được ở mọi môi trường.
# =============================================================================
class TestLibraryRoutingPlanetRoute(unittest.TestCase):
    def test_library_routing_planet_route(self):
        """route theo dot-path planet_identity.* -> 'planet', KHÔNG phải
        'flora' (mục 2 §CODER 2, test #4 trong SPEC)."""
        result = _route_by_table(
            "form_1_planet_foundation.planet_identity.terrain_patterns"
        )
        self.assertEqual(result, "planet")

    def test_flora_route_not_broken_by_planet_entry(self):
        """Bổ sung: ecosystem_foundation.* vẫn phải route đúng 'flora',
        không bị entry 'planet' (chung hơn) nuốt mất (xem giải thích trong
        library_routing.py về thứ tự khai báo)."""
        result = _route_by_table(
            "form_1_planet_foundation.ecosystem_foundation.dominant_ecosystem"
        )
        self.assertEqual(result, "flora")

    def test_planet_environment_fallback_maps_to_planet(self):
        self.assertEqual(
            ENTITY_TYPE_FALLBACK_TO_LIBRARY_TYPE.get("planet_environment"),
            "planet",
        )

    def test_library_required_fields_has_planet(self):
        """SPEC test #5: from config import LIBRARY_REQUIRED_FIELDS ->
        'planet' in LIBRARY_REQUIRED_FIELDS."""
        from config import LIBRARY_REQUIRED_FIELDS

        self.assertIn("planet", LIBRARY_REQUIRED_FIELDS)
        self.assertEqual(
            LIBRARY_REQUIRED_FIELDS["planet"],
            [
                "form_1_planet_foundation.planet_identity.planet_type",
                "form_1_planet_foundation.planet_identity.terrain_patterns",
                "form_1_planet_foundation.planet_identity.climate_patterns",
                "form_1_planet_foundation.ecosystem_foundation.dominant_ecosystem",
            ],
        )

    def test_library_routing_import_from_config(self):
        """SPEC test #6: from library_routing import LIBRARY_REQUIRED_FIELDS
        hoạt động bình thường (re-export, không định nghĩa lại)."""
        from library_routing import LIBRARY_REQUIRED_FIELDS as reexported
        from config import LIBRARY_REQUIRED_FIELDS as original

        self.assertIs(reexported, original)


# =============================================================================
# Test #1/2/3 trong SPEC — cần load PlanetDistiller thật. Stub module
# distillers.base bằng 1 class rỗng để tránh chuỗi import cần pydantic khi
# môi trường chạy test không có pydantic; nếu pydantic CÓ sẵn (CI thật),
# distillers.base thật đã được import từ trước bởi module khác thì
# sys.modules đã có sẵn bản thật -> không bị stub đè lên bản thật.
# =============================================================================
class TestPlanetDistillerExtractPayload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import types

        if "distillers.base" not in sys.modules:
            try:
                import distillers.base  # noqa: F401  (thử import thật trước)
            except ImportError:
                stub = types.ModuleType("distillers.base")

                class _BaseLibraryDistillerStub:
                    pass

                stub.BaseLibraryDistiller = _BaseLibraryDistillerStub
                sys.modules["distillers.base"] = stub

        import importlib

        if "distillers.planet" in sys.modules:
            importlib.reload(sys.modules["distillers.planet"])
        import distillers.planet as planet_mod

        cls.PlanetDistiller = planet_mod.PlanetDistiller

    def test_planet_distiller_class_attrs(self):
        self.assertEqual(self.PlanetDistiller.library_type, "planet")
        self.assertEqual(
            sorted(self.PlanetDistiller.required_fields),
            sorted(
                [
                    "planet_type",
                    "terrain_patterns",
                    "climate_patterns",
                    "dominant_ecosystem",
                ]
            ),
        )

    def test_extract_payload_from_environment_blueprint(self):
        d = self.PlanetDistiller()
        blueprint = {
            "entity_type": "planet_environment",
            "environment_blueprint": {
                "planet_type": "jungle_world",
                "terrain_patterns": ["dense canopy", "river deltas"],
                "climate_patterns": "tropical humid",
                "dominant_ecosystem": ["rainforest", "wetlands"],
                "energy_sources": "bioluminescent flora",
            },
        }
        payload = d._extract_payload(blueprint)
        self.assertEqual(payload["planet_type"], "jungle_world")
        self.assertEqual(payload["terrain_patterns"], ["dense canopy", "river deltas"])
        self.assertEqual(payload["climate_patterns"], ["tropical humid"])
        self.assertEqual(payload["dominant_ecosystem"], ["rainforest", "wetlands"])
        self.assertEqual(payload["energy_sources"], ["bioluminescent flora"])

    def test_extract_payload_fallback_planet_type_from_entity_type(self):
        d = self.PlanetDistiller()
        blueprint = {
            "entity_type": "planet_environment",
            "environment_blueprint": {"terrain_patterns": "flat plains"},
        }
        payload = d._extract_payload(blueprint)
        self.assertEqual(payload["planet_type"], "planet_environment")
        self.assertEqual(payload["terrain_patterns"], ["flat plains"])

    def test_extract_payload_empty_blueprint(self):
        d = self.PlanetDistiller()
        self.assertEqual(d._extract_payload({}), {})
        self.assertEqual(d._extract_payload(None), {})
        self.assertEqual(d._extract_payload({"environment_blueprint": {}}), {})


# =============================================================================
# Test #1 trong SPEC — cần DistillerRegistry thật (cần pydantic đầy đủ vì
# registry.py import mọi Distiller khác, không chỉ planet). Tách riêng để
# skip rõ ràng thay vì để lỗi import mập mờ nếu môi trường thiếu pydantic.
# =============================================================================
class TestPlanetDistillerRegistered(unittest.TestCase):
    def test_planet_distiller_registered(self):
        try:
            from distillers.registry import DistillerRegistry
        except ImportError as e:
            self.skipTest(f"Bỏ qua — thiếu dependency để import registry: {e}")
            return

        planet_cls = DistillerRegistry.get("planet")
        self.assertIsNotNone(planet_cls)
        self.assertEqual(planet_cls.library_type, "planet")

        # Alias cũ vẫn phải trỏ về cùng 1 class thật (không phải stub cũ).
        alias_cls = DistillerRegistry.get("planet_environment")
        self.assertIs(alias_cls, planet_cls)


if __name__ == "__main__":
    unittest.main()
