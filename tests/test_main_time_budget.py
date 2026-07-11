"""Unit test cho main.py::_check_time_and_stop() — [CODER 2 — Budget Theo
Thời Gian, Vấn đề #2].

Chỉ test hàm helper thuần (không chạy full run_pipeline_once() vì hàm đó
cần Mongo/Gemini). Nếu môi trường thiếu dependency runtime của main.py
(httpx, pymongo, google-generativeai, ...) test sẽ tự skip thay vì fail,
để không chặn `python -m unittest discover tests/` trên máy chưa cài đủ
requirements.txt.
"""
import unittest

try:
    import main  # noqa: E402
    _IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - phụ thuộc môi trường CI
    main = None
    _IMPORT_ERROR = e

from core.budget_manager import BudgetManager
from core.logger import PipelineLogger


@unittest.skipIf(main is None, f"main.py không import được trong môi trường này: {_IMPORT_ERROR}")
class TestCheckTimeAndStop(unittest.TestCase):

    def test_returns_false_when_time_budget_not_exhausted(self):
        budget = BudgetManager(max_urls=10, max_gemini_calls=10, max_tokens=1000, max_seconds=60)
        obs = PipelineLogger(run_id="test_run", budget=budget)
        self.assertFalse(main._check_time_and_stop(budget, obs, "T0_SEARCH"))

    def test_returns_true_when_time_budget_exhausted(self):
        budget = BudgetManager(max_urls=10, max_gemini_calls=10, max_tokens=1000, max_seconds=0)
        obs = PipelineLogger(run_id="test_run", budget=budget)
        self.assertTrue(main._check_time_and_stop(budget, obs, "T1_CLASSIFY"))

    def test_logs_graceful_stop_event(self):
        import io
        import sys
        import json

        budget = BudgetManager(max_urls=10, max_gemini_calls=10, max_tokens=1000, max_seconds=0)
        obs = PipelineLogger(run_id="test_run", budget=budget)

        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            result = main._check_time_and_stop(budget, obs, "T2_SCRAPE")
        finally:
            sys.stderr = old_stderr

        self.assertTrue(result)
        lines = [l for l in captured.getvalue().strip().splitlines() if l]
        self.assertTrue(lines, "Kỳ vọng ít nhất 1 dòng JSON log GRACEFUL_STOP")
        parsed = json.loads(lines[-1])
        self.assertEqual(parsed["status"], "GRACEFUL_STOP")
        self.assertEqual(parsed["step"], "T2_SCRAPE")

    def test_works_without_obs(self):
        # obs=None phải không raise (giống pattern các agent khác trong repo).
        budget = BudgetManager(max_urls=10, max_gemini_calls=10, max_tokens=1000, max_seconds=0)
        self.assertTrue(main._check_time_and_stop(budget, None, "SUMMARIZER_DOC"))


if __name__ == "__main__":
    unittest.main()
