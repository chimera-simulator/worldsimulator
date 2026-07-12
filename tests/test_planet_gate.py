"""
tests/test_planet_gate.py — Unit/integration test cho Planet Required
Fields Check (Gate 5) trong t3_normalize.py, theo mục 2 §CODER 3
"Test cần viết (Coder 3)" của SPEC_PLANET_ROTATION_MASTER.md.

Không cần MongoDB — mọi test dùng dict thuần Python / dependency injection.

Chạy: python3 -m unittest tests.test_planet_gate -v  (từ repo1/)
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from t3_normalize import (
    check_planet_required_fields,
    run_gate_5,
)


REQUIRED_PLANET_FIELDS = [
    "form_1_planet_foundation.planet_identity.planet_type",
    "form_1_planet_foundation.planet_identity.terrain_patterns",
    "form_1_planet_foundation.planet_identity.climate_patterns",
    "form_1_planet_foundation.ecosystem_foundation.dominant_ecosystem",
]


class _FakeCfg:
    """cfg giả lập chỉ có đúng LIBRARY_REQUIRED_FIELDS["planet"] — tránh phụ
    thuộc vào config.py thật (đã có sẵn entry "planet" từ Coder 1, nhưng
    test này cô lập khỏi thay đổi tương lai của config.py)."""

    LIBRARY_REQUIRED_FIELDS = {"planet": REQUIRED_PLANET_FIELDS}


def _make_full_planet_schema_record() -> dict:
    """schema_record có đủ 4 field bắt buộc của planet."""
    return {
        "schema_version": "2.0",
        "document_type": "worldbuilding_design_pattern",
        "form_1_planet_foundation": {
            "planet_identity": {
                "planet_type": "jungle_world",
                "terrain_patterns": ["dense canopy", "river delta"],
                "climate_patterns": ["tropical humid"],
            },
            "ecosystem_foundation": {
                "dominant_ecosystem": ["rainforest"],
            },
        },
    }


def _make_combined_output(schema_record, entity_type="planet") -> dict:
    """Blueprint tối thiểu hợp lệ để qua Check A/B/C/G/F/D/E — dùng chung
    cho các test integration qua run_gate_5()."""
    return {
        "visual_blueprint": {
            "visual_id": "vid_planet_001",
            "entity_type": entity_type,
            "multi_view_references": {
                "front_view": "a front view image",
                "side_view": "a side view image",
                "back_view": None,
                "close_up_face": None,
                "environment_context": None,
            },
            "pre_built_prompts": {
                "full_character": "x" * 200,
            },
            "validation_rules": {
                "forbidden_combinations": [],
                "required_fields": [],
                "min_prompt_length": 150,
                "max_prompt_length": 700,
            },
            "metadata": {
                "gap_filling_status": {"pending_fields": []},
            },
        },
        "schema_record": schema_record,
    }


class TestCheckPlanetRequiredFieldsUnit(unittest.TestCase):
    def test_check_planet_required_fields_pass(self):
        """schema_record có đủ 4 field → trả []."""
        schema_record = _make_full_planet_schema_record()
        missing = check_planet_required_fields(schema_record, "planet", _FakeCfg)
        self.assertEqual(missing, [])

    def test_check_planet_required_fields_missing(self):
        """schema_record thiếu terrain_patterns → trả đúng dot-path đó."""
        schema_record = _make_full_planet_schema_record()
        del schema_record["form_1_planet_foundation"]["planet_identity"]["terrain_patterns"]
        missing = check_planet_required_fields(schema_record, "planet", _FakeCfg)
        self.assertEqual(
            missing,
            ["form_1_planet_foundation.planet_identity.terrain_patterns"],
        )

    def test_check_planet_skips_non_planet_entity(self):
        """entity_type="species" → trả [] (không check planet), kể cả khi
        schema_record thiếu toàn bộ field planet."""
        missing = check_planet_required_fields({}, "species", _FakeCfg)
        self.assertEqual(missing, [])

    def test_check_planet_environment_alias_also_checked(self):
        """entity_type="planet_environment" (alias cũ) vẫn được check."""
        schema_record = _make_full_planet_schema_record()
        del schema_record["form_1_planet_foundation"]["ecosystem_foundation"]["dominant_ecosystem"]
        missing = check_planet_required_fields(schema_record, "planet_environment", _FakeCfg)
        self.assertEqual(
            missing,
            ["form_1_planet_foundation.ecosystem_foundation.dominant_ecosystem"],
        )


class TestRunGate5PlanetIntegration(unittest.TestCase):
    def test_run_gate_5_planet_missing_returns_missing_fields(self):
        """gate_result["missing_required_fields"] có giá trị khi reject."""
        schema_record = _make_full_planet_schema_record()
        del schema_record["form_1_planet_foundation"]["planet_identity"]["climate_patterns"]
        combined = _make_combined_output(schema_record, entity_type="planet")

        result, report = run_gate_5(combined)

        self.assertEqual(result.get("reject_reason"), "planet_required_fields_missing")
        self.assertEqual(
            result.get("missing_required_fields"),
            ["form_1_planet_foundation.planet_identity.climate_patterns"],
        )
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(
            report.get("missing_required_fields"),
            ["form_1_planet_foundation.planet_identity.climate_patterns"],
        )

    def test_run_gate_5_pass_has_empty_missing_fields(self):
        """gate_result["missing_required_fields"] = [] khi PASS."""
        schema_record = _make_full_planet_schema_record()
        combined = _make_combined_output(schema_record, entity_type="planet")

        result, report = run_gate_5(combined)

        self.assertIsNone(result.get("reject_reason"))
        self.assertEqual(result.get("missing_required_fields"), [])
        self.assertEqual(report.get("missing_required_fields"), [])

    def test_gate_report_has_missing_required_fields_key(self):
        """gate_report["missing_required_fields"] luôn có key (kể cả với
        entity không phải planet, và khi PASS)."""
        combined = _make_combined_output(None, entity_type="species")
        result, report = run_gate_5(combined)

        self.assertIn("missing_required_fields", result)
        self.assertIn("missing_required_fields", report)
        self.assertEqual(report["missing_required_fields"], [])


if __name__ == "__main__":
    unittest.main()
