"""Unit test cho core.budget_manager — không cần MongoDB, không cần Gemini."""
import threading
import unittest

from core.budget_manager import BudgetManager
from core.logger import PipelineLogger


class TestBudgetManager(unittest.TestCase):

    def test_consume_url_within_budget(self):
        b = BudgetManager(max_urls=10, max_gemini_calls=100, max_tokens=100_000)
        for _ in range(10):
            self.assertTrue(b.consume_url())
        self.assertFalse(b.consume_url())

    def test_consume_gemini_call_within_budget(self):
        b = BudgetManager(max_urls=100, max_gemini_calls=3, max_tokens=100_000)
        self.assertTrue(b.consume_gemini_call(1000))
        self.assertTrue(b.consume_gemini_call(1000))
        self.assertTrue(b.consume_gemini_call(1000))
        self.assertFalse(b.consume_gemini_call(1000))  # call thứ 4

    def test_token_budget_exhaustion_stops_gemini(self):
        b = BudgetManager(max_urls=100, max_gemini_calls=100, max_tokens=2500)
        self.assertTrue(b.consume_gemini_call(1000))
        self.assertTrue(b.consume_gemini_call(1000))
        self.assertFalse(b.consume_gemini_call(1000))  # chỉ còn 500

    def test_record_actual_tokens_adjusts_counter(self):
        b = BudgetManager(max_urls=100, max_gemini_calls=100, max_tokens=100_000)
        b.consume_gemini_call(1000)          # ước tính 1000
        b.record_actual_tokens(1500 - 1000)  # thực tế 1500 -> +500
        self.assertEqual(b.snapshot().tokens_used, 1500)

    def test_snapshot_reflects_state(self):
        b = BudgetManager(max_urls=50, max_gemini_calls=10, max_tokens=10_000)
        b.consume_url(5)
        b.consume_gemini_call(2000)
        snap = b.snapshot()
        self.assertEqual(snap.urls_used, 5)
        self.assertEqual(snap.urls_remaining, 45)
        self.assertEqual(snap.gemini_calls_used, 1)
        self.assertEqual(snap.tokens_used, 2000)

    def test_thread_safety(self):
        b = BudgetManager(max_urls=100, max_gemini_calls=1000, max_tokens=1_000_000)
        success_count = [0]
        lock = threading.Lock()

        def worker():
            if b.consume_url():
                with lock:
                    success_count[0] += 1

        threads = [threading.Thread(target=worker) for _ in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(success_count[0], 100)


class TestPipelineLogger(unittest.TestCase):

    def test_event_without_budget(self):
        log = PipelineLogger(run_id="test_run", budget=None)
        log.event(step="T0_SEARCH", agent="t0_search", status="SUCCESS",
                   message="test message")  # không raise là đủ

    def test_event_json_parseable(self):
        import io, sys, json
        b = BudgetManager(max_urls=10, max_gemini_calls=10, max_tokens=10_000)
        log = PipelineLogger(run_id="test_run", budget=b)

        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            log.event(step="T0_SEARCH", agent="t0_search", status="SUCCESS",
                       items_processed=5, message="5 URLs found")
        finally:
            sys.stderr = old_stderr

        parsed = json.loads(captured.getvalue().strip())
        self.assertEqual(parsed["step"], "T0_SEARCH")
        self.assertEqual(parsed["items_processed"], 5)
        self.assertIn("urls_remaining", parsed["budget_remaining"])


if __name__ == "__main__":
    unittest.main()
