"""
tests/test_t2_5_coder1_scrape_fields.py
========================================
[SPEC_ADDENDUM_2_7 T2.5 — CODER 1] Test phạm vi Coder 1:
- ScrapedDocument thêm working_planet_id/archetype_id.
- scrape_url()/run_scrape_pipeline() nhận + truyền 2 tham số mới.
- Sàn tuyệt đối rất nhẹ ở Gate 2: raw_text rỗng + không ảnh -> None;
  raw_text rỗng nhưng CÓ ảnh -> vẫn qua (Visual-First).
- 2 hằng số mới trong config.py: RAW_TEXT_DEDUP_THRESHOLD, MIN_DOCS_PER_FIELD.

Chỉ test phạm vi Coder 1 (t2_scrape.py + config.py), không đụng main.py /
t2_5_planet_gate.py (thuộc Coder 2/3).

Cách chạy:
    python3 -m unittest tests.test_t2_5_coder1_scrape_fields -v
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.budget_manager import BudgetManager

# t2_scrape.py import httpx ở module level — nếu môi trường CI/local
# thiếu httpx (chưa cài requirements.txt), toàn bộ test ở đây SKIP thay vì
# FAIL, theo đúng pattern đã dùng ở tests/test_main_time_budget.py và
# tests/test_planet_rotation_integration.py.
try:
    import t2_scrape  # noqa: F401
    _T2_SCRAPE_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - phụ thuộc môi trường CI
    _T2_SCRAPE_IMPORT_ERROR = e

_SKIP_REASON = f"t2_scrape.py không import được trong môi trường này: {_T2_SCRAPE_IMPORT_ERROR}"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_blackbook() -> dict:
    return {}


class TestConfigNewConstants(unittest.TestCase):
    def test_raw_text_dedup_threshold_exists_and_default(self):
        import config
        self.assertTrue(hasattr(config, "RAW_TEXT_DEDUP_THRESHOLD"))
        self.assertEqual(config.RAW_TEXT_DEDUP_THRESHOLD, 0.85)

    def test_min_docs_per_field_exists_and_default(self):
        import config
        self.assertTrue(hasattr(config, "MIN_DOCS_PER_FIELD"))
        self.assertEqual(config.MIN_DOCS_PER_FIELD, 2)


@unittest.skipIf(_T2_SCRAPE_IMPORT_ERROR is not None, _SKIP_REASON)
class TestScrapedDocumentNewFields(unittest.TestCase):
    def test_scraped_document_has_new_fields_in_annotations(self):
        from t2_scrape import ScrapedDocument
        annotations = ScrapedDocument.__annotations__
        self.assertIn("working_planet_id", annotations)
        self.assertIn("archetype_id", annotations)


@unittest.skipIf(_T2_SCRAPE_IMPORT_ERROR is not None, _SKIP_REASON)
class TestScrapeUrlNewParams(unittest.TestCase):
    def test_signature_has_new_optional_params(self):
        from t2_scrape import scrape_url
        sig = inspect.signature(scrape_url)
        params = sig.parameters
        self.assertIn("working_planet_id", params)
        self.assertIn("archetype_id", params)
        # phải có default (backward-compat với call cũ chưa truyền)
        self.assertEqual(params["working_planet_id"].default, "")
        self.assertEqual(params["archetype_id"].default, "")

    def test_scrape_url_assigns_new_fields_to_document(self):
        from t2_scrape import scrape_url
        bb = _make_blackbook()
        html = ("<html><body><p>alien visual design concept art</p>"
                "<img src='x.jpg' alt='a'/></body></html>")
        with patch("core.adaptive_router.fetch_with_router",
                   new_callable=AsyncMock, return_value=html):
            item = {"url": "https://artstation.com/art/1",
                    "target_form_field": "species_morphology"}
            b = BudgetManager(max_urls=100, max_gemini_calls=100, max_tokens=100_000)
            result = run(scrape_url(
                None, item, bb, budget=b, obs=None,
                working_planet_id="planet_42", archetype_id="arch_7",
            ))
        self.assertIsNotNone(result)
        self.assertEqual(result["working_planet_id"], "planet_42")
        self.assertEqual(result["archetype_id"], "arch_7")

    def test_scrape_url_defaults_new_fields_when_not_passed(self):
        """Call cũ (chưa truyền working_planet_id/archetype_id) vẫn chạy
        được, field mới mặc định rỗng — không đổi behavior cũ."""
        from t2_scrape import scrape_url
        bb = _make_blackbook()
        html = ("<html><body><p>alien visual design concept art</p>"
                "<img src='x.jpg' alt='a'/></body></html>")
        with patch("core.adaptive_router.fetch_with_router",
                   new_callable=AsyncMock, return_value=html):
            item = {"url": "https://artstation.com/art/1",
                    "target_form_field": "species_morphology"}
            result = run(scrape_url(None, item, bb, budget=None, obs=None))
        self.assertIsNotNone(result)
        self.assertEqual(result["working_planet_id"], "")
        self.assertEqual(result["archetype_id"], "")

    def test_empty_raw_text_and_no_images_returns_none(self):
        """Sàn tuyệt đối MỚI: raw_text rỗng tuyệt đối + không ảnh -> None."""
        from t2_scrape import scrape_url
        bb = _make_blackbook()
        # Không có text hiển thị, không có <img>
        html = "<html><body><script>var x = 1;</script></body></html>"
        with patch("core.adaptive_router.fetch_with_router",
                   new_callable=AsyncMock, return_value=html):
            item = {"url": "https://example.com/empty",
                    "target_form_field": "species_morphology"}
            result = run(scrape_url(None, item, bb, budget=None, obs=None))
        self.assertIsNone(result)

    def test_empty_raw_text_but_has_image_still_passes(self):
        """raw_text rỗng nhưng CÓ ảnh -> KHÔNG bị chặn bởi sàn mới (Visual-First).
        (Vẫn phải qua được Gate 2 density check: density=0 nhưng có ảnh nên
        không bị Gate 2 chặn.)"""
        from t2_scrape import scrape_url
        bb = _make_blackbook()
        html = "<html><body><img src='x.jpg' alt='alien creature concept art'/></body></html>"
        with patch("core.adaptive_router.fetch_with_router",
                   new_callable=AsyncMock, return_value=html):
            item = {"url": "https://example.com/image-only",
                    "target_form_field": "species_morphology"}
            result = run(scrape_url(None, item, bb, budget=None, obs=None))
        self.assertIsNotNone(result)
        self.assertEqual(result["raw_text"], "")
        self.assertEqual(len(result["image_metadata"]), 1)


@unittest.skipIf(_T2_SCRAPE_IMPORT_ERROR is not None, _SKIP_REASON)
class TestRunScrapePipelineNewParams(unittest.TestCase):
    def test_signature_has_new_optional_params(self):
        from t2_scrape import run_scrape_pipeline
        sig = inspect.signature(run_scrape_pipeline)
        params = sig.parameters
        self.assertIn("working_planet_id", params)
        self.assertIn("archetype_id", params)
        self.assertEqual(params["working_planet_id"].default, "")
        self.assertEqual(params["archetype_id"].default, "")

    def test_run_scrape_pipeline_propagates_to_each_document(self):
        from t2_scrape import run_scrape_pipeline
        bb = _make_blackbook()
        html = ("<html><body><p>alien visual design concept art</p>"
                "<img src='x.jpg' alt='a'/></body></html>")
        items = [
            {"url": "https://artstation.com/art/1", "target_form_field": "species_morphology"},
            {"url": "https://artstation.com/art/2", "target_form_field": "species_morphology"},
        ]
        with patch("core.adaptive_router.fetch_with_router",
                   new_callable=AsyncMock, return_value=html):
            docs = run(run_scrape_pipeline(
                items, bb, budget=None, obs=None,
                working_planet_id="planet_99", archetype_id="arch_1",
            ))
        self.assertEqual(len(docs), 2)
        for doc in docs:
            self.assertEqual(doc["working_planet_id"], "planet_99")
            self.assertEqual(doc["archetype_id"], "arch_1")

    def test_run_scrape_pipeline_backward_compat_no_new_params(self):
        """Call cũ (main.py:523 hiện tại chưa truyền 2 tham số mới) vẫn
        chạy được cho tới khi Coder 3 nối dây — không phá vỡ hành vi hiện
        tại."""
        from t2_scrape import run_scrape_pipeline
        bb = _make_blackbook()
        html = ("<html><body><p>alien visual design concept art</p>"
                "<img src='x.jpg' alt='a'/></body></html>")
        items = [{"url": "https://artstation.com/art/1", "target_form_field": "species_morphology"}]
        with patch("core.adaptive_router.fetch_with_router",
                   new_callable=AsyncMock, return_value=html):
            docs = run(run_scrape_pipeline(items, bb, budget=None, obs=None))
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["working_planet_id"], "")
        self.assertEqual(docs[0]["archetype_id"], "")


if __name__ == "__main__":
    unittest.main()
