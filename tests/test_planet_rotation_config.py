"""
tests/test_planet_rotation_config.py — [SPEC_FIX_2_6][Coder 1 — pass 1]
=========================================================================
Unit test cho phần nền móng của Planet-Type Rotation (mục 2.6) mà Coder 1
giao trong lượt đầu tiên: `config.PLANET_TYPE_CATALOG` +
`config.LIBRARY_REQUIRED_FIELDS["planet"]`.

KHÔNG test generate_queries_for_field() / _get_current_planet_archetype() /
_advance_planet_cursor() / _handle_planet_gate_result() ở đây — các hàm đó
thuộc t0_search.py / main.py, sẽ được Coder 1 giao ở lượt 2 (sau khi Coder 3
hoàn tất interface missing_required_fields trong t3_normalize.py, theo đúng
thứ tự dependency ở mục 3 của SPEC_PLANET_ROTATION_MASTER.md).
File test đầy đủ cho phần rotation engine (`tests/test_planet_rotation.py`,
6 case theo mục 2 §Coder 1) sẽ được bổ sung ở lượt giao đó.
"""
from __future__ import annotations

import unittest

import config


class TestPlanetTypeCatalog(unittest.TestCase):
    def test_catalog_has_16_archetypes(self):
        self.assertEqual(len(config.PLANET_TYPE_CATALOG), 16)

    def test_catalog_entries_are_unique(self):
        self.assertEqual(
            len(config.PLANET_TYPE_CATALOG),
            len(set(config.PLANET_TYPE_CATALOG)),
        )

    def test_catalog_contains_expected_archetypes(self):
        expected = {
            "desert_world", "desert_ruins_world", "ocean_world", "jungle_world",
            "forest_ruins_world", "crystal_world", "ice_world", "volcanic_world",
            "gas_giant_world", "toxic_world", "mechanical_world", "hollow_world",
            "shadow_world", "celestial_world", "fungal_world", "ruined_city_world",
        }
        self.assertEqual(set(config.PLANET_TYPE_CATALOG), expected)

    def test_confusable_pairs_present(self):
        # Mục 1.4 Spec: 2 cặp dễ trùng domain cần giám sát khi sinh query.
        for pair in (
            ("desert_world", "desert_ruins_world"),
            ("jungle_world", "forest_ruins_world"),
        ):
            for archetype in pair:
                self.assertIn(archetype, config.PLANET_TYPE_CATALOG)


class TestLibraryRequiredFieldsPlanet(unittest.TestCase):
    def test_planet_key_present(self):
        self.assertIn("planet", config.LIBRARY_REQUIRED_FIELDS)

    def test_planet_required_fields_are_exact_4_dot_paths(self):
        expected = [
            "form_1_planet_foundation.planet_identity.planet_type",
            "form_1_planet_foundation.planet_identity.terrain_patterns",
            "form_1_planet_foundation.planet_identity.climate_patterns",
            "form_1_planet_foundation.ecosystem_foundation.dominant_ecosystem",
        ]
        self.assertEqual(config.LIBRARY_REQUIRED_FIELDS["planet"], expected)

    def test_planet_dot_paths_resolve_in_master_schema(self):
        # Mỗi dot-path phải khớp thật với MASTER_SCHEMA_2_0 (không hardcode
        # field không tồn tại — quy tắc §4.3 SPEC_PLANET_ROTATION_MASTER).
        for dot_path in config.LIBRARY_REQUIRED_FIELDS["planet"]:
            node = config.MASTER_SCHEMA_2_0
            for part in dot_path.split("."):
                self.assertIsInstance(node, dict, msg=f"broken path: {dot_path}")
                self.assertIn(part, node, msg=f"missing '{part}' in path: {dot_path}")
                node = node[part]

    def test_existing_library_types_unchanged(self):
        # Không được vô tình đổi baseline của các library_type đã có (chỉ
        # THÊM "planet", không sửa cái cũ).
        self.assertEqual(
            config.LIBRARY_REQUIRED_FIELDS["species"],
            ["skin_color", "prompt_keywords"],
        )
        self.assertEqual(
            config.LIBRARY_REQUIRED_FIELDS["architecture"],
            ["style", "material"],
        )
        self.assertEqual(config.LIBRARY_REQUIRED_FIELDS["visual_style"], ["style_preset"])
        self.assertNotIn("occupation", config.LIBRARY_REQUIRED_FIELDS)


if __name__ == "__main__":
    unittest.main()
