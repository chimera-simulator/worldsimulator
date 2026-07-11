"""
tests/test_t1_classify.py — Unit test cho Gate 1.5 (Scope/Blueprint Filtering)
trong t1_classify.py, theo mục 6A (Definition of Done — Coder 3) của
SPEC_HARVEST_CYCLE_FIXES_v2_3CODERS.md.

Chạy: python3 -m unittest tests.test_t1_classify -v  (từ thư mục repo1/)
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from t1_classify import (
    score_source,
    classify_and_rank,
    is_in_worldbuilding_scope,
    WORLDBUILDING_SCOPE_PENALTY,
)
from config import VISUAL_SCORE_THRESHOLD


def _item(url: str, source_type: str = "visual_moderate", field: str = "form_1_planet_foundation.planet_identity.terrain_patterns"):
    return {
        "url": url,
        "target_form_field": field,
        "source_type": source_type,
        "ip_heavy_flag": False,
        "query_variant": "Concept",
        "field_already_filled": False,
    }


class TestIsInWorldbuildingScope(unittest.TestCase):
    def test_scope_domain_whitelist_matches(self):
        self.assertTrue(
            is_in_worldbuilding_scope(
                "https://www.artstation.com/artwork/xyz", "visual_rich", "artstation.com"
            )
        )

    def test_scope_domain_subdomain_matches(self):
        self.assertTrue(
            is_in_worldbuilding_scope(
                "https://sub.fandom.com/wiki/Foo", "visual_moderate", "sub.fandom.com"
            )
        )

    def test_url_signal_matches(self):
        self.assertTrue(
            is_in_worldbuilding_scope(
                "https://example.com/sci-fi-worldbuilding-guide", "visual_moderate", "example.com"
            )
        )

    def test_no_signal_and_unknown_domain_out_of_scope(self):
        self.assertFalse(
            is_in_worldbuilding_scope(
                "https://randomblog.example/some-post", "visual_moderate", "randomblog.example"
            )
        )


class TestScoreSource(unittest.TestCase):
    def test_score_penalized_when_out_of_scope(self):
        """Score phải giảm đúng WORLDBUILDING_SCOPE_PENALTY khi
        in_worldbuilding_scope=False, so với cùng item khi in_scope=True."""
        item = _item("https://example.com/random-page", source_type="visual_moderate")

        score_in_scope = score_source(
            item, has_images=False, is_academic_domain=False, in_worldbuilding_scope=True
        )
        score_out_of_scope = score_source(
            item, has_images=False, is_academic_domain=False, in_worldbuilding_scope=False
        )

        self.assertAlmostEqual(score_in_scope - score_out_of_scope, WORLDBUILDING_SCOPE_PENALTY)

    def test_does_not_drop_below_zero(self):
        item = _item("https://example.com/random-page", source_type="text_only")
        score = score_source(
            item, has_images=False, is_academic_domain=True, in_worldbuilding_scope=False
        )
        self.assertGreaterEqual(score, 0.0)


class TestClassifyAndRank(unittest.TestCase):
    def test_score_reduced_when_not_in_scope(self):
        """URL rõ ràng KHÔNG có tín hiệu worldbuilding (visual_moderate, domain
        lạ, path không match signal nào) phải nhận score thấp hơn URL tương tự
        NHƯNG có tín hiệu worldbuilding rõ ràng trong path."""
        out_of_scope_item = _item("https://randomblog.example/generic-page", source_type="visual_moderate")
        in_scope_item = _item("https://randomblog.example/sci-fi-worldbuilding-concept-art", source_type="visual_moderate")

        result = classify_and_rank([out_of_scope_item, in_scope_item], threshold=0.0)

        by_url = {r["url"]: r for r in result}
        self.assertFalse(by_url[out_of_scope_item["url"]]["in_worldbuilding_scope"])
        self.assertTrue(by_url[in_scope_item["url"]]["in_worldbuilding_scope"])
        self.assertLess(
            by_url[out_of_scope_item["url"]]["score"],
            by_url[in_scope_item["url"]]["score"],
        )

    def test_visual_rich_out_of_scope_can_still_pass_threshold(self):
        """source_type='visual_rich' (base score 3.0) + in_scope=False (penalty
        -0.8) vẫn phải >= VISUAL_SCORE_THRESHOLD mặc định (1.5) -> bị trừ điểm
        nhưng KHÔNG bị drop, đúng nguyên tắc 'trừ điểm thay vì drop cứng'."""
        item = _item("https://randomblog.example/generic-page", source_type="visual_rich")

        result = classify_and_rank([item], threshold=VISUAL_SCORE_THRESHOLD)

        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["in_worldbuilding_scope"])
        self.assertGreaterEqual(result[0]["score"], VISUAL_SCORE_THRESHOLD)

    def test_out_of_scope_dropped_when_score_below_threshold(self):
        """visual_moderate (base 2.0) + out-of-scope penalty (-0.8) = 1.2,
        dưới threshold mặc định 1.5 -> phải bị drop khỏi kết quả cuối."""
        item = _item("https://randomblog.example/generic-page", source_type="visual_moderate")

        result = classify_and_rank([item], threshold=VISUAL_SCORE_THRESHOLD)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
