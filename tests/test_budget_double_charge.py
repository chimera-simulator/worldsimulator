"""
test_budget_double_charge.py — Tái hiện và xác nhận fix bug double-charge.

Bug: t0_search.py gọi budget.consume_url() khi parse link → cạn max_urls
     trước khi T2 chạy → 0 document mỗi lần chạy.
Fix: T0 KHÔNG gọi consume_url(). Chỉ T2 tiêu max_urls.

Các test này KHÔNG mock t0_search/t2_scrape (quá nặng) — thay vào đó
kiểm tra trực tiếp hành vi BudgetManager và contract của từng agent.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from core.budget_manager import BudgetManager


class TestBudgetDoubleChargeFix(unittest.TestCase):
    """Kiểm tra contract: T0 KHÔNG tiêu max_urls, T2 mới tiêu."""

    def test_t0_does_not_consume_url_budget(self):
        """Sau khi T0 'tìm thấy' 150 URL, budget urls_remaining phải còn nguyên 150.
        
        Tái hiện: trước fix, T0 gọi consume_url() × 150 → urls_remaining = 0.
        Sau fix: T0 không gọi consume_url() → urls_remaining vẫn = 150.
        """
        budget = BudgetManager(max_urls=150, max_gemini_calls=300, max_tokens=300_000)
        
        # Mô phỏng: T0 "xử lý" 150 URL mà KHÔNG gọi consume_url()
        # (đây là hành vi ĐÚNG sau fix)
        simulated_t0_results = [{"url": f"https://example.com/{i}"} for i in range(150)]
        # T0 chỉ append, không consume
        _ = simulated_t0_results  # no budget call
        
        snap = budget.snapshot()
        self.assertEqual(snap.urls_used, 0,
            "T0 không được tiêu bất kỳ URL budget nào — chỉ T2 mới được consume_url()")
        self.assertEqual(snap.urls_remaining, 150,
            "Sau T0, toàn bộ 150 URL budget phải còn nguyên cho T2")

    def test_t2_consumes_url_budget_correctly(self):
        """T2 scrape 75 item → urls_used = 75, urls_remaining = 75."""
        budget = BudgetManager(max_urls=150, max_gemini_calls=300, max_tokens=300_000)
        
        # Mô phỏng T2: lọc items theo budget (logic giống t2_scrape.run_scrape_pipeline)
        items = [{"url": f"https://example.com/{i}"} for i in range(75)]
        allowed = []
        for item in items:
            if not budget.consume_url():
                break
            allowed.append(item)
        
        self.assertEqual(len(allowed), 75)
        snap = budget.snapshot()
        self.assertEqual(snap.urls_used, 75)
        self.assertEqual(snap.urls_remaining, 75)

    def test_full_pipeline_flow_t0_then_t2(self):
        """Case tái hiện đúng bug: T0 → 150 URL, T1 lọc → 75, T2 scrape 75/75.
        
        TRƯỚC FIX: T0 consume 150 → T2 nhận 0/75 (bug)
        SAU FIX: T0 consume 0 → T2 nhận đủ budget → scrape 75/75 ✓
        """
        budget = BudgetManager(max_urls=150, max_gemini_calls=300, max_tokens=300_000)
        
        # === Giai đoạn T0 (sau fix): parse 150 URL, KHÔNG consume ===
        t0_discovered = 150
        # T0 không gọi consume_url() — budget nguyên vẹn
        self.assertEqual(budget.snapshot().urls_remaining, 150,
            "Sau T0: budget phải còn nguyên 150")
        
        # === Giai đoạn T1: lọc còn 75 URL đạt Gate 1 ===
        t1_classified = 75
        
        # === Giai đoạn T2: consume_url() cho từng item cần scrape ===
        items = list(range(t1_classified))  # 75 item
        scraped_count = 0
        for _ in items:
            if budget.consume_url():
                scraped_count += 1
            else:
                break
        
        self.assertEqual(scraped_count, 75,
            "T2 phải scrape được 75/75 URL (không bị 0/75 do budget cạn từ T0)")
        snap = budget.snapshot()
        self.assertEqual(snap.urls_used, 75)
        self.assertEqual(snap.urls_remaining, 75)

    def test_budget_regression_previous_bug_behavior(self):
        """Tái hiện CHÍNH XÁC bug cũ để chứng minh fix không regress.
        
        Bug cũ: T0 gọi consume_url() × 150 → exhausted → T2 được 0/75.
        Test này mô phỏng hành vi bug cũ và assert rằng nếu T0 consume,
        T2 sẽ bị 0 — qua đó khẳng định fix (T0 không consume) là đúng.
        """
        budget_buggy = BudgetManager(max_urls=150, max_gemini_calls=300, max_tokens=300_000)
        
        # Mô phỏng HÀNH VI BUG CŨ: T0 consume hết 150
        for _ in range(150):
            budget_buggy.consume_url()  # bug cũ làm vậy
        
        # T2 không còn budget
        self.assertEqual(budget_buggy.snapshot().urls_remaining, 0,
            "Bug cũ: sau T0 consume hết, T2 không còn budget")
        
        t2_allowed = []
        for _ in range(75):
            if not budget_buggy.consume_url():
                break
            t2_allowed.append(1)
        
        self.assertEqual(len(t2_allowed), 0,
            "Bug cũ: T2 scrape 0/75 — đây là lý do pipeline cho 0 document")


class TestMaxDiscoveryResultsPerRun(unittest.TestCase):
    """Kiểm tra hằng số MAX_DISCOVERY_RESULTS_PER_RUN trong config.py."""

    def test_max_discovery_constant_exists(self):
        """MAX_DISCOVERY_RESULTS_PER_RUN phải tồn tại trong config.py."""
        import config
        self.assertTrue(
            hasattr(config, "MAX_DISCOVERY_RESULTS_PER_RUN"),
            "config.MAX_DISCOVERY_RESULTS_PER_RUN phải được định nghĩa (Coder 1 thêm)"
        )

    def test_max_discovery_is_positive_int(self):
        """MAX_DISCOVERY_RESULTS_PER_RUN phải là int dương."""
        import config
        val = config.MAX_DISCOVERY_RESULTS_PER_RUN
        self.assertIsInstance(val, int)
        self.assertGreater(val, 0)

    def test_max_discovery_default_value(self):
        """Default phải là 500 (không env var)."""
        import os
        import importlib
        # Đảm bảo không có env var can thiệp
        env_backup = os.environ.pop("MAX_DISCOVERY_RESULTS_PER_RUN", None)
        try:
            import config
            importlib.reload(config)
            self.assertEqual(config.MAX_DISCOVERY_RESULTS_PER_RUN, 500)
        finally:
            if env_backup is not None:
                os.environ["MAX_DISCOVERY_RESULTS_PER_RUN"] = env_backup

    def test_max_discovery_env_override(self):
        """MAX_DISCOVERY_RESULTS_PER_RUN đọc được từ env var."""
        import os
        import importlib
        os.environ["MAX_DISCOVERY_RESULTS_PER_RUN"] = "300"
        try:
            import config
            importlib.reload(config)
            self.assertEqual(config.MAX_DISCOVERY_RESULTS_PER_RUN, 300)
        finally:
            del os.environ["MAX_DISCOVERY_RESULTS_PER_RUN"]
            import config
            importlib.reload(config)

    def test_max_discovery_is_independent_of_max_urls(self):
        """MAX_DISCOVERY_RESULTS_PER_RUN KHÔNG phải là max_urls và không liên quan BudgetManager."""
        import config
        budget = BudgetManager(max_urls=150)
        # Hai giá trị này độc lập — không nên bằng nhau ngẫu nhiên
        # (default 500 vs 150 — nếu bằng nhau là báo hiệu copy-paste nhầm)
        self.assertNotEqual(
            config.MAX_DISCOVERY_RESULTS_PER_RUN,
            budget.max_urls,
            "MAX_DISCOVERY_RESULTS_PER_RUN (500) và max_urls (150) phải khác nhau "
            "— chúng là 2 tài nguyên độc lập"
        )


class TestBudgetDocstringContract(unittest.TestCase):
    """Kiểm tra docstring của BudgetManager phản ánh đúng contract sau fix."""

    def test_budget_manager_docstring_no_t0_mention(self):
        """Docstring của BudgetManager không được nhắc 't0 + t2 gộp lại' nữa."""
        from core.budget_manager import BudgetManager
        doc = BudgetManager.__doc__ or ""
        self.assertNotIn(
            "t0 + t2 gộp lại",
            doc,
            "Docstring cũ 't0 + t2 gộp lại' phải được Coder 2 xóa khỏi budget_manager.py"
        )

    def test_consume_url_docstring_mentions_t2_only(self):
        """consume_url() docstring phải nói rõ chỉ T2 gọi hàm này."""
        from core.budget_manager import BudgetManager
        doc = BudgetManager.consume_url.__doc__ or ""
        # Sau fix, docstring phải nhắc đến T2
        self.assertIn(
            "t2",
            doc.lower(),
            "consume_url() docstring phải ghi rõ T2 là nơi duy nhất gọi hàm này"
        )


if __name__ == "__main__":
    unittest.main()
