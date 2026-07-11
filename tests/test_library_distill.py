"""
tests/test_library_distill.py — Unit test cho Gate 6.5 (Library Distillation)
==============================================================================
Chạy: python3 -m unittest tests.test_library_distill -v  (từ thư mục repo1/)

Convention: unittest, mock không dùng external service. Theo đúng mẫu của
tests/test_rule_library.py.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from t4_5_library_distill import (
    distill_one,
    generate_entity_id,
    route_library_type,
)


# =============================================================================
# Helpers: builder cho mock doc
# =============================================================================

def _make_doc(
    visual_id: str = "VB_SPECIES_a1b2c3d4",
    entity_type: str = "species",
    target_form_field: str = "",
    clothing_and_gear: dict = None,
    pre_built_prompts: dict = None,
    schema_record: dict = None,
    character_blueprint: dict = None,
) -> dict:
    blueprint = {
        "visual_id": visual_id,
        "entity_type": entity_type,
        "character_blueprint": character_blueprint or {},
        "clothing_and_gear": clothing_and_gear or {},
        "pre_built_prompts": pre_built_prompts or {},
        "environment_blueprint": None,
        "prompt_metadata": {"style_preset": "", "quality_tags": ""},
        "consistency_lock": {"locked_fields": [], "variable_fields": []},
    }
    _schema_record = schema_record
    if _schema_record is None:
        _schema_record = {
            "provenance_and_metadata": {
                "target_form_field": target_form_field,
                "ip_filter_status": "cleaned",
            }
        }
    elif target_form_field:
        _schema_record = dict(_schema_record)
        pm = dict(_schema_record.get("provenance_and_metadata") or {})
        pm["target_form_field"] = target_form_field
        _schema_record["provenance_and_metadata"] = pm

    return {
        "visual_id": visual_id,
        "blueprint": blueprint,
        "schema_record": _schema_record,
        "merged": False,
    }


# =============================================================================
# Test 1: route từ target_form_field
# =============================================================================
class TestRouteLibraryTypeFromTargetFormField(unittest.TestCase):
    def _route(self, field: str) -> str | None:
        doc = _make_doc(target_form_field=field, entity_type="species")
        return route_library_type(doc)

    def test_species_from_biology_field(self):
        result = self._route("form_2_civilization_layer.biology_and_behavior.species_morphology")
        self.assertEqual(result, "species")

    def test_flora_from_ecosystem_field(self):
        result = self._route("form_1_planet_foundation.ecosystem_foundation.dominant_ecosystem")
        self.assertEqual(result, "flora")

    def test_architecture_from_architecture_patterns(self):
        result = self._route(
            "form_2_civilization_layer.society_and_infrastructure.architecture_patterns"
        )
        self.assertEqual(result, "architecture")

    def test_technology_from_technology_patterns(self):
        result = self._route(
            "form_2_civilization_layer.society_and_infrastructure.technology_patterns"
        )
        self.assertEqual(result, "technology")

    def test_culture_from_culture_field(self):
        result = self._route("form_2_civilization_layer.culture_and_history.cultural_patterns")
        self.assertEqual(result, "culture")


# =============================================================================
# Test 2: fallback từ entity_type khi target_form_field rỗng
# =============================================================================
class TestRouteLibraryTypeFallbackEntityType(unittest.TestCase):
    def test_creature_fallback(self):
        doc = _make_doc(target_form_field="", entity_type="creature")
        self.assertEqual(route_library_type(doc), "creature")

    def test_architecture_fallback(self):
        doc = _make_doc(target_form_field="", entity_type="architecture")
        self.assertEqual(route_library_type(doc), "architecture")

    def test_species_fallback(self):
        doc = _make_doc(target_form_field="", entity_type="species")
        self.assertEqual(route_library_type(doc), "species")


# =============================================================================
# Test 3: trả None khi không match gì (planet_environment)
# =============================================================================
class TestRouteLibraryTypeNoneWhenNoMatch(unittest.TestCase):
    def test_planet_environment_returns_none(self):
        doc = _make_doc(target_form_field="", entity_type="planet_environment")
        self.assertIsNone(route_library_type(doc))

    def test_unknown_entity_type_returns_none(self):
        doc = _make_doc(target_form_field="", entity_type="unknown_type")
        self.assertIsNone(route_library_type(doc))

    def test_no_match_field_returns_none(self):
        doc = _make_doc(
            target_form_field="form_99_nonexistent.something",
            entity_type="planet_environment",
        )
        self.assertIsNone(route_library_type(doc))


# =============================================================================
# Test 4: costume từ clothing_and_gear không rỗng
# =============================================================================
class TestRouteLibraryTypeCostumeFromClothingField(unittest.TestCase):
    def test_costume_when_clothing_not_empty(self):
        doc = _make_doc(
            target_form_field="",            # không match bảng
            entity_type="species",           # fallback sẽ là species, nhưng
            clothing_and_gear={"top": "armor_plate"},  # clothing ưu tiên hơn fallback
        )
        # Theo logic: bước 2 không match → bước 3 costume check trước fallback entity_type
        result = route_library_type(doc)
        self.assertEqual(result, "costume")

    def test_no_costume_when_clothing_empty(self):
        doc = _make_doc(
            target_form_field="",
            entity_type="creature",
            clothing_and_gear={},
        )
        # Không phải costume vì clothing rỗng → fallback creature
        result = route_library_type(doc)
        self.assertEqual(result, "creature")


# =============================================================================
# Test 5: distill_one → status complete khi đủ required fields
# =============================================================================
class TestDistillOneCompleteStatus(unittest.TestCase):
    def test_complete_without_llm(self):
        """Species có đủ skin_color + prompt_keywords từ blueprint."""
        doc = _make_doc(
            visual_id="VB_SPECIES_aabbccdd",
            entity_type="species",
            target_form_field="form_2_civilization_layer.biology_and_behavior.species_morphology",
            character_blueprint={
                "physical_attributes": {
                    "skin": {"base_color": "#4A90E2", "prompt_fragment": "translucent blue"},
                }
            },
            pre_built_prompts={
                "full_character": "bipedal crystalline being, translucent blue skin",
                "negative": "human face, eyes",
            },
        )

        with patch("t4_5_library_distill._get_call_gemini", return_value=None):
            result = distill_one(doc, budget=None, obs=None)

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["library_type"], "species")
        self.assertFalse(result["source_provenance"]["llm_structuring_used"])
        self.assertEqual(result["missing_required_fields"], [])

    def test_entity_id_correct(self):
        """entity_id phải là SPECIES_aabbccdd (hash suffix từ visual_id)."""
        doc = _make_doc(
            visual_id="VB_SPECIES_aabbccdd",
            entity_type="species",
            target_form_field="form_2_civilization_layer.biology_and_behavior.species_morphology",
            pre_built_prompts={"full_character": "test prompt"},
            character_blueprint={
                "physical_attributes": {"skin": {"base_color": "#000"}},
            },
        )
        with patch("t4_5_library_distill._get_call_gemini", return_value=None):
            result = distill_one(doc)
        self.assertEqual(result["entity_id"], "SPECIES_aabbccdd")


# =============================================================================
# Test 6: distill_one → incomplete khi LLM trả rỗng
# =============================================================================
class TestDistillOneIncompleteWhenMissingAfterLlm(unittest.TestCase):
    def test_incomplete_when_llm_returns_empty(self):
        """Species thiếu skin_color, LLM mock trả {} → incomplete."""
        doc = _make_doc(
            visual_id="VB_SPECIES_11223344",
            entity_type="species",
            target_form_field="form_2_civilization_layer.biology_and_behavior.species_morphology",
            # Không có skin trong character_blueprint → skin_color sẽ thiếu
            character_blueprint={},
            pre_built_prompts={"full_character": "some prompt"},
        )

        # Mock structure_via_llm trả {} (LLM không giúp được)
        with patch("t4_5_library_distill.structure_via_llm", return_value={}):
            result = distill_one(doc, budget=None, obs=None)

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("skin_color", result["missing_required_fields"])


# =============================================================================
# Test 7: distill_one → None khi không route được
# =============================================================================
class TestDistillOneNoneWhenUnrouted(unittest.TestCase):
    def test_returns_none_for_planet_environment(self):
        doc = _make_doc(target_form_field="", entity_type="planet_environment")
        result = distill_one(doc)
        self.assertIsNone(result)

    def test_does_not_raise(self):
        doc = _make_doc(target_form_field="", entity_type="planet_environment")
        try:
            distill_one(doc)
        except Exception as exc:
            self.fail(f"distill_one raised unexpectedly: {exc}")


# =============================================================================
# Test 8: generate_entity_id idempotent
# =============================================================================
class TestGenerateEntityIdStableAcrossRuns(unittest.TestCase):
    def test_same_visual_id_same_entity_id(self):
        doc = {"visual_id": "VB_SPECIES_a1b2c3d4"}
        id1 = generate_entity_id("species", doc)
        id2 = generate_entity_id("species", doc)
        self.assertEqual(id1, id2)

    def test_format_correct(self):
        doc = {"visual_id": "VB_CREATURE_deadbeef"}
        result = generate_entity_id("creature", doc)
        self.assertEqual(result, "CREATURE_deadbeef")

    def test_different_types_different_ids(self):
        doc = {"visual_id": "VB_SPECIES_a1b2c3d4"}
        id_species = generate_entity_id("species", doc)
        id_creature = generate_entity_id("creature", doc)
        self.assertNotEqual(id_species, id_creature)

    def test_no_visual_id_uses_unknown(self):
        doc = {}
        result = generate_entity_id("flora", doc)
        self.assertEqual(result, "FLORA_unknown")


if __name__ == "__main__":
    unittest.main()
