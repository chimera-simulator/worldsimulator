"""
tests/test_quality_scorer.py — Unit test cho core/quality_scorer.py, theo
§1.5 SPEC_QualityScorer_TL.md.

Chạy: python3 -m unittest tests.test_quality_scorer -v  (từ repo1/)
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core.quality_scorer import compute_quality_score


class TestQualityScorer(unittest.TestCase):
    def test_weights_sum_to_100(self):
        self.assertEqual(sum(config.QUALITY_SCORE_WEIGHTS.values()), 100)

    def test_full_score_matches_example(self):
        blueprint = {
            "multi_view_references": {
                "front_view": "a front view image",
                "side_view": "a side view image",
                "back_view": "a back view image",
                "close_up_face": "a close-up face image",
                "environment_context": "an environment context image",
            },
            "pre_built_prompts": {
                "full_character": "x" * 200,
            },
        }
        schema_record = {
            "provenance_and_metadata": {
                "ip_filter_status": "cleaned",
                "original_ip_detected": [],
            },
            "form_1_planet_foundation": {
                "planet_identity": {
                    "planet_type": "rocky",
                    "core_material": "iron",
                    "physical_appearance": ["a"],
                    "terrain_patterns": ["a"],
                    "climate_patterns": ["a"],
                    "energy_sources": ["a"],
                    "natural_resources": ["a"],
                    "planetary_hazards": ["a"],
                    "planetary_phenomena": ["a"],
                },
                "ecosystem_foundation": {
                    "dominant_ecosystem": ["a"],
                    "dominant_life_material": "carbon",
                    "food_chain_patterns": ["a"],
                    "ecological_cycles": ["a"],
                    "environmental_adaptations": ["a"],
                },
            },
            "form_2_civilization_layer": {
                "biology_and_behavior": {
                    "species_morphology": ["a"],
                    "species_behavior": ["a"],
                },
                "society_and_infrastructure": {
                    "architecture_patterns": ["a"],
                    "transportation_patterns": ["a"],
                    "technology_patterns": ["a"],
                    "government_patterns": ["a"],
                    "economic_patterns": ["a"],
                    "military_patterns": ["a"],
                },
                "culture_and_history": {
                    "religion_and_belief": ["a"],
                    "cultural_patterns": ["a"],
                    "language_patterns": ["a"],
                    "art_patterns": ["a"],
                    "daily_life_patterns": ["a"],
                    "historical_patterns": ["a"],
                    "diplomatic_patterns": ["a"],
                },
            },
        }

        result = compute_quality_score(blueprint, schema_record)

        self.assertEqual(result["total"], 100)
        self.assertTrue(result["passed_threshold"])

    def test_zero_view_zero_schema(self):
        blueprint = {
            "multi_view_references": {},
            "pre_built_prompts": {"full_character": "x" * 200},
        }
        schema_record = None

        result = compute_quality_score(blueprint, schema_record)

        score_b = result["breakdown"]["ip_cleanliness"]
        score_c = result["breakdown"]["prompt_depth"]

        self.assertEqual(result["breakdown"]["view_completeness"], 0)
        self.assertEqual(result["breakdown"]["schema_completeness"], 0)
        self.assertEqual(result["total"], score_b + score_c)

    def test_ip_cleaned_but_found(self):
        blueprint = {"multi_view_references": {}, "pre_built_prompts": {}}
        schema_record = {
            "provenance_and_metadata": {
                "ip_filter_status": "cleaned",
                "original_ip_detected": ["Pikachu"],
            }
        }

        result = compute_quality_score(blueprint, schema_record)

        self.assertEqual(result["breakdown"]["ip_cleanliness"], 10)

    def test_ip_unknown_status_failsafe(self):
        blueprint = {"multi_view_references": {}, "pre_built_prompts": {}}
        schema_record = {
            "provenance_and_metadata": {
                "ip_filter_status": "some_garbage_value",
                "original_ip_detected": [],
            }
        }

        result = compute_quality_score(blueprint, schema_record)

        self.assertEqual(result["breakdown"]["ip_cleanliness"], 5)

    def test_prompt_depth_bands(self):
        def score_for_length(n):
            blueprint = {
                "multi_view_references": {},
                "pre_built_prompts": {"full_character": "x" * n},
            }
            return compute_quality_score(blueprint, None)["breakdown"]["prompt_depth"]

        self.assertEqual(score_for_length(149), 0)
        self.assertEqual(score_for_length(150), 10)
        self.assertEqual(score_for_length(199), 10)
        self.assertEqual(score_for_length(200), 20)

    def test_never_raises_on_empty_blueprint(self):
        result = compute_quality_score({}, None)

        self.assertIsInstance(result["total"], int)
        self.assertGreaterEqual(result["total"], 0)
        self.assertLessEqual(result["total"], 100)


if __name__ == "__main__":
    unittest.main()
