"""
tests/test_t3_normalize_check_g.py — Integration test cho Check G
(Global Rule Library) trong t3_normalize.py, theo §9
SPEC_GLOBAL_RULE_LIBRARY_v1_0.md.

Chạy: python3 -m unittest tests.test_t3_normalize_check_g -v  (từ repo1/)
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from t3_normalize import run_gate_5


def _make_combined_output() -> dict:
    """Blueprint tối thiểu hợp lệ để qua Check A/B/C/F/D/E mà không cần
    Global Rule Library — dùng chung cho mọi test case bên dưới."""
    return {
        "visual_blueprint": {
            "visual_id": "vid_test_001",
            "multi_view_references": {
                "front_view": "a front view image",
                "side_view": "a side view image",
                "back_view": None,
                "close_up_face": None,
                "environment_context": None,
            },
            "pre_built_prompts": {
                "full_character": "x" * 200,  # trong range min/max mặc định
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
            "character": "mc_female",
            "gear": "heavy armor equipped",
        },
        "schema_record": None,
    }


class TestBackwardCompatibility(unittest.TestCase):
    def test_run_gate_5_without_rules_behaves_like_before(self):
        """run_gate_5(c) không truyền rules — hành vi giống hệt trước khi
        có Check G (regression test tương thích ngược)."""
        combined = _make_combined_output()
        result, report = run_gate_5(combined)
        self.assertIsNone(result.get("reject_reason"))
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report.get("rule_hits"), [])

    def test_run_gate_5_with_cfg_no_rules(self):
        import config as cfg

        combined = _make_combined_output()
        result, report = run_gate_5(combined, cfg)
        self.assertIsNone(result.get("reject_reason"))
        self.assertEqual(report["status"], "PASS")


class TestCheckGReject(unittest.TestCase):
    def test_error_rule_match_rejects(self):
        combined = _make_combined_output()
        rules = [
            {
                "rule_id": "RULE-MC-001",
                "rule_type": "forbidden_term_combo",
                "severity": "ERROR",
                "condition": {"terms": ["mc_female", "heavy armor"]},
                "message": "MC nữ không được mặc giáp hạng nặng.",
            }
        ]
        result, report = run_gate_5(combined, rules=rules)
        self.assertEqual(result["reject_reason"], "global_rule_violated:RULE-MC-001")
        self.assertEqual(report["status"], "REJECTED")


class TestCheckGWarningFlagOnly(unittest.TestCase):
    def test_warning_rule_match_does_not_reject(self):
        combined = _make_combined_output()
        rules = [
            {
                "rule_id": "RULE-ENV-001",
                "rule_type": "forbidden_term_combo",
                "severity": "WARNING",
                "condition": {"terms": ["mc_female", "heavy armor"]},
                "message": "Cảnh báo phối hợp.",
            }
        ]
        result, report = run_gate_5(combined, rules=rules)
        self.assertIsNone(result.get("reject_reason"))
        self.assertIn(report["status"], ("PASS", "PASS_WITH_FLAG"))
        self.assertEqual(len(report["rule_hits"]), 1)
        self.assertEqual(report["rule_hits"][0]["rule_id"], "RULE-ENV-001")


class TestCheckGEmptyRulesSkipped(unittest.TestCase):
    def test_empty_rules_list_behaves_like_none(self):
        combined = _make_combined_output()
        result_none, report_none = run_gate_5(combined, rules=None)
        result_empty, report_empty = run_gate_5(combined, rules=[])
        self.assertEqual(result_none.get("reject_reason"), result_empty.get("reject_reason"))
        self.assertEqual(report_none["status"], report_empty["status"])
        self.assertEqual(report_empty["rule_hits"], [])


class TestCheckGRunsBeforeCheckF(unittest.TestCase):
    def test_reject_happens_before_visual_prompt_builder_called(self):
        """Check G reject phải xảy ra TRƯỚC khi VisualPromptBuilder được
        gọi — verify bằng spy trên check_prompt_assembly_verification."""
        combined = _make_combined_output()
        rules = [
            {
                "rule_id": "RULE-MC-001",
                "rule_type": "forbidden_term_combo",
                "severity": "ERROR",
                "condition": {"terms": ["mc_female", "heavy armor"]},
                "message": "MC nữ không được mặc giáp hạng nặng.",
            }
        ]
        with patch(
            "t3_normalize.check_prompt_assembly_verification"
        ) as mocked_check_f:
            result, report = run_gate_5(combined, rules=rules)
            mocked_check_f.assert_not_called()
        self.assertEqual(report["status"], "REJECTED")
        self.assertTrue(result["reject_reason"].startswith("global_rule_violated:"))


if __name__ == "__main__":
    unittest.main()
