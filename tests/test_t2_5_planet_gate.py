"""
tests/test_t2_5_planet_gate.py — Unit test cho t2_5_planet_gate.py
(T2.5 Planet-Scoped Aggregate Gate), theo mục 3 §CODER 2 "Test cần viết"
của SPEC_ADDENDUM_2_7_T2_5_PLANET_GATE_MERGED_v2.md.

Mock toàn bộ input (List[ScrapedDocument] dict thuần), KHÔNG phụ thuộc
MongoDB / blackbook thật / DB nào khác. Chỉ test phạm vi Coder 2
(t2_5_planet_gate.py) — không đụng main.py / t2_scrape.py.

Chạy: python3 -m unittest tests.test_t2_5_planet_gate -v  (từ repo1/)
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from t2_5_planet_gate import NO_ROUTE_FORM_FIELDS, run_planet_gate

# Field dot-path CÓ route thật (verify library_routing.py):
FIELD_ARCHITECTURE = (
    "form_2_civilization_layer.society_and_infrastructure.architecture_patterns"
)
FIELD_TECHNOLOGY = (
    "form_2_civilization_layer.society_and_infrastructure.technology_patterns"
)
FIELD_SPECIES = "form_2_civilization_layer.biology_and_behavior.species_morphology"

# 1 trong 4 field KHÔNG route (verify t2_5_planet_gate.NO_ROUTE_FORM_FIELDS).
FIELD_TRANSPORTATION = (
    "form_2_civilization_layer.society_and_infrastructure.transportation_patterns"
)


def _doc(
    raw_text: str,
    target_form_field: str,
    n_images: int = 0,
    working_planet_id: str = "planet_1",
    archetype_id: str = "arch_1",
    source_domain: str = "example.com",
) -> dict:
    """Tạo 1 ScrapedDocument dict tối thiểu cho test."""
    return {
        "raw_text": raw_text,
        "image_metadata": [
            {
                "alt_text": "x",
                "dimensions": None,
                "image_url": f"https://example.com/{i}.jpg",
                "context_paragraph": "",
            }
            for i in range(n_images)
        ],
        "target_form_field": target_form_field,
        "source_domain": source_domain,
        "working_planet_id": working_planet_id,
        "archetype_id": archetype_id,
    }


class TestNoRouteFieldsConstant(unittest.TestCase):
    def test_exactly_4_no_route_fields_hardcoded(self):
        self.assertEqual(len(NO_ROUTE_FORM_FIELDS), 4)
        self.assertIn(FIELD_TRANSPORTATION, NO_ROUTE_FORM_FIELDS)


class TestDedupeRawText(unittest.TestCase):
    def test_case1_duplicate_pair_same_field_keeps_longer(self):
        """2 doc trùng nội dung cùng field (similarity > threshold) ->
        dedupe còn 1, giữ bản dài hơn, duplicate_dropped == 1."""
        short_text = (
            "alien jungle planet concept art worldbuilding design pattern "
            "description reference variant"
        )
        long_text = short_text + " extra"

        docs = [
            _doc(short_text, FIELD_ARCHITECTURE, n_images=1),
            _doc(long_text, FIELD_ARCHITECTURE, n_images=1),
            # padding để field đủ điều kiện (không ảnh hưởng test dedupe)
            _doc("unrelated architecture design pattern text here", FIELD_ARCHITECTURE),
        ]
        gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})

        self.assertEqual(report["duplicate_dropped"], 1)
        remaining_texts = [d["raw_text"] for d in gated]
        self.assertIn(long_text, remaining_texts)
        self.assertNotIn(short_text, remaining_texts)


class TestFieldSufficiency(unittest.TestCase):
    def test_case2_field_with_route_enough_docs_not_insufficient(self):
        """Field có route, đủ MIN_DOCS_PER_FIELD (=2) sau dedupe -> không
        vào insufficient_fields."""
        docs = [
            _doc("architecture design pattern one totally unique text", FIELD_ARCHITECTURE),
            _doc("architecture design pattern two completely different", FIELD_ARCHITECTURE),
        ]
        gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})

        self.assertNotIn(FIELD_ARCHITECTURE, report["insufficient_fields"])
        self.assertTrue(report["send_to_t3"])
        self.assertEqual(len(gated), 2)

    def test_case3_field_with_route_missing_docs_is_insufficient(self):
        """Field có route, thiếu doc (chỉ 1 < MIN_DOCS_PER_FIELD=2) -> vào
        insufficient_fields."""
        docs = [
            _doc("only one architecture document here", FIELD_ARCHITECTURE),
            # 1 field khác đủ điều kiện để send_to_t3 vẫn True (test cô lập
            # riêng insufficient_fields, không lẫn với test case 5).
            _doc("technology pattern doc number one unique", FIELD_TECHNOLOGY),
            _doc("technology pattern doc number two different", FIELD_TECHNOLOGY),
        ]
        gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})

        self.assertIn(FIELD_ARCHITECTURE, report["insufficient_fields"])
        self.assertNotIn(FIELD_TECHNOLOGY, report["insufficient_fields"])

    def test_case4_no_route_field_zero_docs_not_insufficient(self):
        """Field KHÔNG có route (1 trong 4 field bị loại trừ) -> dù 0 doc
        (không xuất hiện trong batch) vẫn KHÔNG vào insufficient_fields,
        không ảnh hưởng send_to_t3."""
        docs = [
            _doc("technology pattern doc number one unique", FIELD_TECHNOLOGY),
            _doc("technology pattern doc number two different", FIELD_TECHNOLOGY),
        ]
        gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})

        for no_route_field in NO_ROUTE_FORM_FIELDS:
            self.assertNotIn(no_route_field, report["insufficient_fields"])
        self.assertTrue(report["send_to_t3"])

    def test_case4b_no_route_field_present_with_few_docs_not_insufficient(self):
        """Doc THUỘC field không route (dù chỉ 1 doc, dưới MIN_DOCS_PER_FIELD)
        vẫn không bị tính insufficient — và vẫn đi tiếp cùng field đủ điều
        kiện khác."""
        docs = [
            _doc("transportation pattern single doc", FIELD_TRANSPORTATION),
            _doc("technology pattern doc number one unique", FIELD_TECHNOLOGY),
            _doc("technology pattern doc number two different", FIELD_TECHNOLOGY),
        ]
        gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})

        self.assertNotIn(FIELD_TRANSPORTATION, report["insufficient_fields"])
        self.assertTrue(report["send_to_t3"])
        gated_fields = [d["target_form_field"] for d in gated]
        self.assertIn(FIELD_TRANSPORTATION, gated_fields)


class TestSendToT3Decision(unittest.TestCase):
    def test_case5_all_fields_insufficient_rejects_everything(self):
        """Toàn bộ field insufficient -> send_to_t3=False, gated_docs=[]."""
        docs = [
            _doc("only one architecture document", FIELD_ARCHITECTURE),
            _doc("only one technology document", FIELD_TECHNOLOGY),
        ]
        gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})

        self.assertFalse(report["send_to_t3"])
        self.assertEqual(gated, [])
        self.assertTrue(report["retry_triggered"])
        self.assertIn(FIELD_ARCHITECTURE, report["insufficient_fields"])
        self.assertIn(FIELD_TECHNOLOGY, report["insufficient_fields"])

    def test_case6_partial_sufficient_sends_only_qualifying_fields(self):
        """Một phần đủ -> send_to_t3=True, gated_docs chỉ chứa doc thuộc
        field đủ điều kiện (field thiếu bị loại khỏi output)."""
        docs = [
            _doc("only one architecture document", FIELD_ARCHITECTURE),
            _doc("technology pattern doc number one unique", FIELD_TECHNOLOGY),
            _doc("technology pattern doc number two different", FIELD_TECHNOLOGY),
        ]
        gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})

        self.assertTrue(report["send_to_t3"])
        self.assertFalse(report["retry_triggered"])
        gated_fields = {d["target_form_field"] for d in gated}
        self.assertEqual(gated_fields, {FIELD_TECHNOLOGY})
        self.assertEqual(len(gated), 2)
        self.assertIn(FIELD_ARCHITECTURE, report["insufficient_fields"])


class TestSklearnFallback(unittest.TestCase):
    def test_case7_sklearn_unavailable_falls_back_to_jaccard_no_raise(self):
        """sklearn không có sẵn (mock import lỗi) -> compute_prompt_similarity
        dùng fallback Jaccard, run_planet_gate không raise."""
        short_text = (
            "alien jungle planet concept art worldbuilding design pattern "
            "description reference variant"
        )
        long_text = short_text + " extra"
        docs = [
            _doc(short_text, FIELD_ARCHITECTURE, n_images=1),
            _doc(long_text, FIELD_ARCHITECTURE, n_images=1),
            _doc("technology pattern doc number one unique", FIELD_TECHNOLOGY),
            _doc("technology pattern doc number two different", FIELD_TECHNOLOGY),
        ]
        with patch.dict(
            sys.modules,
            {
                "sklearn.feature_extraction.text": None,
                "sklearn.metrics.pairwise": None,
            },
        ):
            try:
                gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})
            except Exception as e:  # pragma: no cover
                self.fail(f"run_planet_gate raised khi sklearn không khả dụng: {e}")

        self.assertEqual(report["duplicate_dropped"], 1)


class TestGateSignature(unittest.TestCase):
    def test_returns_tuple_of_list_and_dict_report_shape(self):
        docs = [_doc("some architecture text here", FIELD_ARCHITECTURE)]
        gated, report = run_planet_gate(docs, "planet_1", "arch_1", blackbook={})

        self.assertIsInstance(gated, list)
        self.assertIsInstance(report, dict)
        for key in ("send_to_t3", "retry_triggered", "duplicate_dropped", "insufficient_fields"):
            self.assertIn(key, report)

    def test_accepts_budget_and_obs_kwargs(self):
        """Chữ ký phải nhận budget=/obs= (kể cả None) mà không lỗi — main.py
        sẽ truyền budget/obs thật khi nối dây (Coder 3)."""
        docs = [_doc("some architecture text here", FIELD_ARCHITECTURE)]
        gated, report = run_planet_gate(
            docs, "planet_1", "arch_1", blackbook={}, budget=None, obs=None,
        )
        self.assertIsInstance(report, dict)


if __name__ == "__main__":
    unittest.main()
