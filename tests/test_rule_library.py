"""
tests/test_rule_library.py — Unit test cho rule_library.py (Global Rule
Library / Check G), theo §9 SPEC_GLOBAL_RULE_LIBRARY_v1_0.md.

Chạy: python3 -m unittest tests.test_rule_library -v  (từ thư mục repo1/)
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rule_library import evaluate_all, evaluate_rule, load_active_rules


class TestEvaluateRule(unittest.TestCase):
    def test_hit_when_all_terms_present_error(self):
        rule = {
            "rule_id": "RULE-MC-001",
            "rule_type": "forbidden_term_combo",
            "severity": "ERROR",
            "condition": {"terms": ["mc_female", "heavy armor"]},
            "message": "vi phạm",
            "suggestion": "sửa",
        }
        blueprint = {"character": "mc_female", "gear": "heavy armor set"}
        hit = evaluate_rule(rule, blueprint)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["rule_id"], "RULE-MC-001")
        self.assertEqual(hit["severity"], "ERROR")

    def test_none_when_missing_one_term(self):
        rule = {
            "rule_id": "RULE-MC-001",
            "rule_type": "forbidden_term_combo",
            "severity": "ERROR",
            "condition": {"terms": ["mc_female", "heavy armor"]},
        }
        blueprint = {"character": "mc_female", "gear": "light armor"}
        self.assertIsNone(evaluate_rule(rule, blueprint))

    def test_none_and_no_raise_for_unsupported_rule_type(self):
        rule = {
            "rule_id": "RULE-FUTURE-001",
            "rule_type": "field_condition",
            "severity": "ERROR",
            "condition": {},
        }
        blueprint = {"anything": "here"}
        self.assertIsNone(evaluate_rule(rule, blueprint))


class TestEvaluateAll(unittest.TestCase):
    def test_does_not_crash_on_malformed_rule(self):
        rules = [
            {"rule_id": "BAD-1", "rule_type": "forbidden_term_combo"},  # missing condition
            {
                "rule_id": "BAD-2",
                "rule_type": "forbidden_term_combo",
                "condition": {"terms": "not_a_list"},  # wrong type
            },
            {
                "rule_id": "GOOD-1",
                "rule_type": "forbidden_term_combo",
                "severity": "WARNING",
                "condition": {"terms": ["desert", "snow"]},
            },
        ]
        blueprint = {"biome": "desert with snow"}
        hits = evaluate_all(rules, blueprint)
        # GOOD-1 phải match (terms is a string, iterated as chars — nhưng
        # không được raise); ít nhất không crash toàn bộ evaluate_all.
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("GOOD-1", rule_ids)

    def test_multiple_hits_returned(self):
        rules = [
            {
                "rule_id": "R1",
                "rule_type": "forbidden_term_combo",
                "severity": "ERROR",
                "condition": {"terms": ["a", "b"]},
            },
            {
                "rule_id": "R2",
                "rule_type": "forbidden_term_combo",
                "severity": "WARNING",
                "condition": {"terms": ["c"]},
            },
        ]
        blueprint = {"x": "a b c"}
        hits = evaluate_all(rules, blueprint)
        self.assertEqual({h["rule_id"] for h in hits}, {"R1", "R2"})


class _FailingCollection:
    def find(self, *_args, **_kwargs):
        raise RuntimeError("mongo query lỗi giả lập")


class _FailingDB:
    def __getitem__(self, _name):
        return _FailingCollection()


class _OkCollection:
    def __init__(self, rules):
        self._rules = rules

    def find(self, *_args, **_kwargs):
        return list(self._rules)


class _OkDB:
    def __init__(self, rules):
        self._rules = rules

    def __getitem__(self, _name):
        return _OkCollection(self._rules)


class TestLoadActiveRules(unittest.TestCase):
    def test_none_db_returns_empty_fail_open(self):
        # [FIX] load_active_rules() trả (rules, rule_check_skipped) — db=None
        # là case fail-open thật sự (không có kết nối Mongo) nên
        # rule_check_skipped phải là True.
        rules, rule_check_skipped = load_active_rules(None)
        self.assertEqual(rules, [])
        self.assertTrue(rule_check_skipped)

    def test_failing_db_returns_empty_fail_open(self):
        # Mongo query lỗi -> cũng là fail-open thật sự -> rule_check_skipped=True.
        rules, rule_check_skipped = load_active_rules(_FailingDB())
        self.assertEqual(rules, [])
        self.assertTrue(rule_check_skipped)

    def test_success_returns_rules_and_skipped_false(self):
        # Mongo OK, có rule active -> rule_check_skipped PHẢI là False,
        # kể cả khi collection rỗng (0 rule active là trạng thái hợp lệ,
        # không phải lỗi/fail-open).
        rules, rule_check_skipped = load_active_rules(_OkDB([{"rule_id": "R1"}]))
        self.assertEqual(rules, [{"rule_id": "R1"}])
        self.assertFalse(rule_check_skipped)

    def test_success_empty_collection_not_treated_as_skipped(self):
        rules, rule_check_skipped = load_active_rules(_OkDB([]))
        self.assertEqual(rules, [])
        self.assertFalse(rule_check_skipped)


if __name__ == "__main__":
    unittest.main()
