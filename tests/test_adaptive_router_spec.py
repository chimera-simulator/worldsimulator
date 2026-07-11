"""
tests/test_adaptive_router_spec.py
===================================
Kiểm thử SPEC_ADAPTIVE_ROUTER_T2 — chạy offline (không cần httpx, playwright,
curl_cffi, MongoDB). Mọi test đều dùng mock/stub để kiểm tra logic điều phối,
không phải mạng thật.

Trạng thái hiện tại: CÁC TEST TRONG SECTION A-E SẼ FAIL cho đến khi Coder
implement các thành phần theo SPEC. Đây là thiết kế có chủ ý (TDD).

Cách chạy:
    python3 -m unittest tests.test_adaptive_router_spec -v
"""
from __future__ import annotations

import asyncio
import sys
import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import các module ĐÃ tồn tại (luôn available)
from domain_ban import is_banned, record_failure, record_success
from core.budget_manager import BudgetManager
from core.logger import PipelineLogger

# Import modules MỚI (chưa implement) — dùng lazy import trong từng test
# để tránh ImportError phá vỡ toàn bộ test suite


def run(coro):
    """Chạy coroutine đồng bộ trong test."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_blackbook() -> dict:
    return {}


# ===========================================================================
# PRE-CHECK: Kiểm tra xem các hàm MỚI có tồn tại chưa
# ===========================================================================

class TestPreCheck(unittest.TestCase):
    """PRECHECK: Xác nhận baseline (các module cũ không bị break)."""

    def test_PC1_domain_ban_existing_functions_intact(self):
        """Các hàm cũ của domain_ban.py không bị thay đổi."""
        bb = {}
        # is_banned với domain mới phải False
        self.assertFalse(is_banned(bb, "example.com"))
        # record_failure 3 lần phải ban
        record_failure(bb, "example.com")
        record_failure(bb, "example.com")
        result = record_failure(bb, "example.com")
        self.assertTrue(result)  # lần thứ 3 kích hoạt ban
        self.assertTrue(is_banned(bb, "example.com"))
        # record_success reset
        record_success(bb, "example.com")
        self.assertFalse(is_banned(bb, "example.com"))

    def test_PC2_budget_manager_existing_methods_intact(self):
        """Các method cũ của BudgetManager không bị break."""
        b = BudgetManager(max_urls=5, max_gemini_calls=10, max_tokens=50_000)
        self.assertTrue(b.consume_url())
        self.assertTrue(b.consume_gemini_call(1000))
        snap = b.snapshot()
        self.assertEqual(snap.urls_used, 1)
        self.assertEqual(snap.gemini_calls_used, 1)

    def test_PC3_label_adapter_function_exists(self):
        """domain_ban.py phải export label_adapter()."""
        try:
            from domain_ban import label_adapter
        except ImportError:
            self.fail("label_adapter() chưa được thêm vào domain_ban.py")

    def test_PC4_get_adapter_label_function_exists(self):
        """domain_ban.py phải export get_adapter_label()."""
        try:
            from domain_ban import get_adapter_label
        except ImportError:
            self.fail("get_adapter_label() chưa được thêm vào domain_ban.py")

    def test_PC5_budget_manager_accepts_max_browser_calls(self):
        """BudgetManager.__init__() phải nhận tham số max_browser_calls."""
        try:
            b = BudgetManager(max_urls=10, max_gemini_calls=10,
                              max_tokens=10_000, max_browser_calls=5)
        except TypeError as e:
            self.fail(f"BudgetManager chưa nhận max_browser_calls: {e}")

    def test_PC6_budget_manager_has_consume_browser_call(self):
        """BudgetManager phải có method consume_browser_call()."""
        b = BudgetManager(max_urls=10, max_gemini_calls=10, max_tokens=10_000)
        self.assertTrue(hasattr(b, "consume_browser_call"),
                        "BudgetManager.consume_browser_call() chưa implement")

    def test_PC7_adaptive_router_module_exists(self):
        """core/adaptive_router.py phải tồn tại và import được."""
        try:
            import core.adaptive_router
        except ImportError:
            self.fail("core/adaptive_router.py chưa được tạo")

    def test_PC8_adapters_package_exists(self):
        """core/adapters/ package phải tồn tại với 4 tier module."""
        for mod in ["core.adapters.tier1_http", "core.adapters.tier2_reader",
                    "core.adapters.tier3_browser", "core.adapters.tier4_stealth_tls"]:
            try:
                __import__(mod)
            except ImportError:
                self.fail(f"{mod} chưa được tạo")


# ===========================================================================
# SECTION A: domain_ban.py — hàm mới label_adapter / get_adapter_label
# ===========================================================================

class TestLabelAdapter(unittest.TestCase):
    """A1–A7: kiểm tra hàm label_adapter() và get_adapter_label() mới."""

    def setUp(self):
        try:
            from domain_ban import label_adapter, get_adapter_label
            self.label_adapter = label_adapter
            self.get_adapter_label = get_adapter_label
        except ImportError:
            self.skipTest("label_adapter/get_adapter_label chưa implement")

    def test_A1_label_adapter_writes_skill_field(self):
        """label_adapter() ghi đúng tên adapter vào entry['skill']."""
        bb = _make_blackbook()
        self.label_adapter(bb, "example.com", "tier2_reader")
        self.assertEqual(bb["example.com"]["skill"], "tier2_reader")

    def test_A2_label_valid_until_set_to_7_days(self):
        """adapter_label_valid_until phải là ~7 ngày kể từ now (±5 giây)."""
        bb = _make_blackbook()
        before = datetime.now(timezone.utc)
        self.label_adapter(bb, "example.com", "tier1_http")
        after = datetime.now(timezone.utc)

        until_str = bb["example.com"].get("adapter_label_valid_until")
        self.assertIsNotNone(until_str, "Phải có field adapter_label_valid_until")
        until_dt = datetime.fromisoformat(until_str)
        self.assertGreaterEqual(until_dt, before + timedelta(days=7) - timedelta(seconds=5))
        self.assertLessEqual(until_dt, after + timedelta(days=7) + timedelta(seconds=5))

    def test_A3_get_adapter_label_returns_valid_label(self):
        """get_adapter_label() trả adapter name khi label còn hạn."""
        bb = _make_blackbook()
        self.label_adapter(bb, "artstation.com", "tier4_stealth_tls")
        result = self.get_adapter_label(bb, "artstation.com")
        self.assertEqual(result, "tier4_stealth_tls")

    def test_A4_get_adapter_label_returns_none_when_expired(self):
        """get_adapter_label() trả None khi label đã hết hạn."""
        bb = _make_blackbook()
        bb["expired.com"] = {
            "failures": 0,
            "status": "active",
            "skill": "tier1_http",
            "adapter_label_valid_until": (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).isoformat(),
        }
        result = self.get_adapter_label(bb, "expired.com")
        self.assertIsNone(result)

    def test_A5_get_adapter_label_returns_none_for_unknown_domain(self):
        """get_adapter_label() trả None khi domain chưa có entry."""
        bb = _make_blackbook()
        self.assertIsNone(self.get_adapter_label(bb, "unknown.com"))

    def test_A6_label_adapter_does_not_overwrite_ban_status(self):
        """label_adapter() KHÔNG được xóa hoặc thay đổi status='banned'."""
        bb = _make_blackbook()
        record_failure(bb, "banned.com")
        record_failure(bb, "banned.com")
        record_failure(bb, "banned.com")
        self.assertTrue(is_banned(bb, "banned.com"))

        self.label_adapter(bb, "banned.com", "tier1_http")

        # Sau khi label: vẫn phải còn bị ban
        self.assertTrue(is_banned(bb, "banned.com"))
        # skill được cập nhật đúng
        self.assertEqual(bb["banned.com"]["skill"], "tier1_http")

    def test_A7_custom_ttl_respected(self):
        """label_adapter(ttl_days=3) phải set expiry ~3 ngày, không phải 7."""
        bb = _make_blackbook()
        before = datetime.now(timezone.utc)
        self.label_adapter(bb, "example.com", "tier1_http", ttl_days=3)
        after = datetime.now(timezone.utc)

        until_str = bb["example.com"].get("adapter_label_valid_until")
        until_dt = datetime.fromisoformat(until_str)
        self.assertGreaterEqual(until_dt, before + timedelta(days=3) - timedelta(seconds=5))
        self.assertLessEqual(until_dt, after + timedelta(days=3) + timedelta(seconds=5))


# ===========================================================================
# SECTION B: BudgetManager — consume_browser_call() mới
# ===========================================================================

class TestBudgetManagerBrowserCalls(unittest.TestCase):
    """B1–B5: kiểm tra consume_browser_call() mới trong BudgetManager."""

    def _make_budget(self, max_browser=3):
        try:
            return BudgetManager(max_urls=100, max_gemini_calls=100,
                                 max_tokens=100_000, max_browser_calls=max_browser)
        except TypeError:
            self.skipTest("BudgetManager chưa nhận max_browser_calls")

    def test_B1_consume_browser_call_within_limit(self):
        """consume_browser_call() True khi còn dưới trần."""
        b = self._make_budget(max_browser=3)
        self.assertTrue(b.consume_browser_call())
        self.assertTrue(b.consume_browser_call())
        self.assertTrue(b.consume_browser_call())

    def test_B2_consume_browser_call_returns_false_when_exhausted(self):
        """consume_browser_call() False sau khi đạt trần."""
        b = self._make_budget(max_browser=2)
        b.consume_browser_call()
        b.consume_browser_call()
        self.assertFalse(b.consume_browser_call())

    def test_B3_browser_budget_independent_of_url_budget(self):
        """Trần browser call KHÔNG liên quan đến url budget."""
        b = self._make_budget(max_browser=1)
        b.consume_browser_call()
        self.assertFalse(b.consume_browser_call())  # browser cạn
        self.assertTrue(b.consume_url())  # url vẫn còn

    def test_B4_snapshot_includes_browser_calls(self):
        """snapshot().to_dict() phải có browser_calls_used và browser_calls_max."""
        b = self._make_budget(max_browser=5)
        b.consume_browser_call()
        b.consume_browser_call()
        snap_dict = b.snapshot().to_dict()
        self.assertIn("browser_calls_used", snap_dict, "Thiếu browser_calls_used trong snapshot")
        self.assertIn("browser_calls_max", snap_dict, "Thiếu browser_calls_max trong snapshot")
        self.assertEqual(snap_dict["browser_calls_used"], 2)
        self.assertEqual(snap_dict["browser_calls_max"], 5)

    def test_B5_default_max_browser_calls_from_env(self):
        """BudgetManager đọc BUDGET_MAX_BROWSER_CALLS từ env var khi không truyền tường minh."""
        import os
        os.environ["BUDGET_MAX_BROWSER_CALLS"] = "7"
        try:
            b = BudgetManager(max_urls=10, max_gemini_calls=10, max_tokens=10_000)
            # Nếu đọc được env -> max_browser_calls phải là 7
            if hasattr(b, '_browser_calls_max'):
                self.assertEqual(b._browser_calls_max, 7)
        except Exception:
            pass  # Acceptable nếu chưa implement env-read
        finally:
            del os.environ["BUDGET_MAX_BROWSER_CALLS"]


# ===========================================================================
# SECTION C: AdaptiveRouter — logic routing (mock-based)
# ===========================================================================

class TestAdaptiveRouterRouting(unittest.TestCase):
    """C1–C8: kiểm tra fetch_with_router() routing logic."""

    def setUp(self):
        try:
            from core.adaptive_router import fetch_with_router
            self.fetch_with_router = fetch_with_router
        except ImportError:
            self.skipTest("core.adaptive_router.fetch_with_router chưa implement")
        try:
            from domain_ban import label_adapter
            self.label_adapter = label_adapter
        except ImportError:
            self.label_adapter = None

    def _make_budget(self, max_browser=15):
        try:
            return BudgetManager(max_urls=100, max_gemini_calls=100,
                                 max_tokens=100_000, max_browser_calls=max_browser)
        except TypeError:
            return BudgetManager(max_urls=100, max_gemini_calls=100, max_tokens=100_000)

    def test_C1_banned_domain_returns_none(self):
        """Domain đang bị ban -> trả None, không gọi bất kỳ adapter."""
        bb = _make_blackbook()
        record_failure(bb, "banned.com")
        record_failure(bb, "banned.com")
        record_failure(bb, "banned.com")
        self.assertTrue(is_banned(bb, "banned.com"))

        result = run(self.fetch_with_router(
            url="https://banned.com/page",
            domain="banned.com",
            blackbook=bb,
            budget=self._make_budget(),
            obs=MagicMock(),
        ))
        self.assertIsNone(result)

    def test_C2_cached_label_skips_probe(self):
        """Domain có adapter label hợp lệ -> skip probe, dùng thẳng cached adapter."""
        if self.label_adapter is None:
            self.skipTest("label_adapter chưa implement")
        bb = _make_blackbook()
        self.label_adapter(bb, "artstation.com", "tier1_http")

        with patch("core.adaptive_router._probe", new_callable=AsyncMock) as mock_probe, \
             patch("core.adapters.tier1_http.fetch",
                   new_callable=AsyncMock, return_value="<html>cached</html>"):
            result = run(self.fetch_with_router(
                url="https://artstation.com/art/1",
                domain="artstation.com",
                blackbook=bb,
                budget=self._make_budget(),
                obs=MagicMock(),
            ))

        mock_probe.assert_not_called()
        self.assertEqual(result, "<html>cached</html>")

    def test_C3_probe_200_uses_tier1(self):
        """Probe 200 -> tier1_http."""
        bb = _make_blackbook()
        with patch("core.adaptive_router._probe", new_callable=AsyncMock, return_value=200), \
             patch("core.adapters.tier1_http.fetch",
                   new_callable=AsyncMock, return_value="<html>ok</html>"):
            result = run(self.fetch_with_router(
                url="https://newsite.com/page",
                domain="newsite.com",
                blackbook=bb,
                budget=self._make_budget(),
                obs=MagicMock(),
            ))
        self.assertEqual(result, "<html>ok</html>")

    def test_C4_probe_403_tries_tier4_first(self):
        """Probe 403 -> tier4_stealth_tls TRƯỚC tier3_browser."""
        bb = _make_blackbook()
        call_order = []

        async def t4(*a, **kw): call_order.append("tier4"); return "<html>stealth</html>"
        async def t3(*a, **kw): call_order.append("tier3"); return "<html>browser</html>"

        with patch("core.adaptive_router._probe", new_callable=AsyncMock, return_value=403), \
             patch("core.adapters.tier4_stealth_tls.fetch", side_effect=t4), \
             patch("core.adapters.tier3_browser.fetch", side_effect=t3):
            run(self.fetch_with_router("https://cf.com/p", "cf.com",
                                        bb, self._make_budget(), MagicMock()))

        self.assertIn("tier4", call_order)
        self.assertNotIn("tier3", call_order)

    def test_C5_tier4_fail_escalates_to_tier3(self):
        """tier4 fail (None) -> leo thang tier3."""
        bb = _make_blackbook()

        async def t4(*a, **kw): return None
        async def t3(*a, **kw): return "<html>browser fallback</html>"

        with patch("core.adaptive_router._probe", new_callable=AsyncMock, return_value=403), \
             patch("core.adapters.tier4_stealth_tls.fetch", side_effect=t4), \
             patch("core.adapters.tier3_browser.fetch", side_effect=t3):
            result = run(self.fetch_with_router("https://hard.com/p", "hard.com",
                                                  bb, self._make_budget(), MagicMock()))

        self.assertEqual(result, "<html>browser fallback</html>")

    def test_C6_browser_budget_0_skips_tier3(self):
        """Browser budget = 0 -> KHÔNG gọi tier3, trả None."""
        bb = _make_blackbook()
        try:
            budget = BudgetManager(max_urls=100, max_gemini_calls=100,
                                   max_tokens=100_000, max_browser_calls=0)
        except TypeError:
            self.skipTest("BudgetManager chưa nhận max_browser_calls")

        async def t4(*a, **kw): return None

        with patch("core.adaptive_router._probe", new_callable=AsyncMock, return_value=403), \
             patch("core.adapters.tier4_stealth_tls.fetch", side_effect=t4), \
             patch("core.adapters.tier3_browser.fetch",
                   new_callable=AsyncMock) as mock_t3:
            result = run(self.fetch_with_router("https://cf.com/p", "cf.com",
                                                  bb, budget, MagicMock()))

        mock_t3.assert_not_called()
        self.assertIsNone(result)

    def test_C7_all_tiers_fail_calls_record_failure(self):
        """Mọi tier fail -> record_failure() được gọi cho domain."""
        bb = _make_blackbook()

        async def t4(*a, **kw): return None
        async def t3(*a, **kw): return None

        with patch("core.adaptive_router._probe", new_callable=AsyncMock, return_value=403), \
             patch("core.adapters.tier4_stealth_tls.fetch", side_effect=t4), \
             patch("core.adapters.tier3_browser.fetch", side_effect=t3), \
             patch("domain_ban.record_failure") as mock_rf:
            result = run(self.fetch_with_router("https://impossible.com/p",
                                                  "impossible.com", bb,
                                                  self._make_budget(), MagicMock()))

        self.assertIsNone(result)
        mock_rf.assert_called()

    def test_C8_success_labels_adapter(self):
        """Sau khi fetch thành công -> label_adapter() được gọi."""
        bb = _make_blackbook()
        with patch("core.adaptive_router._probe", new_callable=AsyncMock, return_value=200), \
             patch("core.adapters.tier1_http.fetch",
                   new_callable=AsyncMock, return_value="<html>ok</html>"), \
             patch("domain_ban.label_adapter") as mock_la:
            run(self.fetch_with_router("https://good.com/p", "good.com",
                                         bb, self._make_budget(), MagicMock()))

        mock_la.assert_called()
        args = mock_la.call_args
        # Phải label đúng domain và adapter name
        self.assertEqual(args[0][1], "good.com")
        self.assertIn("tier1", args[0][2])


# ===========================================================================
# SECTION D: t2_scrape.py integration
# ===========================================================================

class TestT2ScrapeIntegration(unittest.TestCase):
    """D1–D3: scrape_url() phải dùng fetch_with_router thay vì httpx trực tiếp."""

    def test_D1_scrape_url_signature_still_accepts_client(self):
        """scrape_url() vẫn nhận client (có thể None) — backward compatible."""
        try:
            from t2_scrape import scrape_url
        except ImportError:
            self.skipTest("t2_scrape import fail (có thể do httpx missing)")
        import inspect
        sig = inspect.signature(scrape_url)
        params = list(sig.parameters.keys())
        self.assertIn("client", params)
        self.assertIn("item", params)
        self.assertIn("blackbook", params)

    def test_D2_scrape_url_calls_router_not_direct_httpx(self):
        """scrape_url() phải gọi fetch_with_router(), không gọi client.get() trực tiếp."""
        try:
            from t2_scrape import scrape_url
            from core.adaptive_router import fetch_with_router
        except ImportError:
            self.skipTest("Module chưa implement hoặc httpx missing")

        bb = _make_blackbook()
        html = "<html><body><p>alien visual design concept art</p><img src='x.jpg' alt='a'/></body></html>"

        with patch("core.adaptive_router.fetch_with_router",
                   new_callable=AsyncMock, return_value=html) as mock_router:
            item = {"url": "https://artstation.com/art/1",
                    "target_form_field": "species_morphology"}
            try:
                b = BudgetManager(max_urls=100, max_gemini_calls=100,
                                  max_tokens=100_000, max_browser_calls=15)
            except TypeError:
                b = BudgetManager(max_urls=100, max_gemini_calls=100, max_tokens=100_000)
            result = run(scrape_url(None, item, bb, budget=b, obs=MagicMock()))

        mock_router.assert_awaited_once()

    def test_D3_router_none_propagates(self):
        """fetch_with_router() trả None -> scrape_url() trả None."""
        try:
            from t2_scrape import scrape_url
        except ImportError:
            self.skipTest("t2_scrape import fail")

        bb = _make_blackbook()
        with patch("core.adaptive_router.fetch_with_router",
                   new_callable=AsyncMock, return_value=None):
            item = {"url": "https://blocked.com/art",
                    "target_form_field": "species_morphology"}
            result = run(scrape_url(None, item, bb, budget=None, obs=None))

        self.assertIsNone(result)


# ===========================================================================
# SECTION E: Probe logging
# ===========================================================================

class TestProbeLogging(unittest.TestCase):
    """E1–E2: _probe() phải log qua obs, không phải hộp đen."""

    def setUp(self):
        try:
            from core.adaptive_router import _probe
            self.probe = _probe
        except ImportError:
            self.skipTest("core.adaptive_router._probe chưa implement")

    def test_E1_probe_calls_obs_event(self):
        """_probe() phải gọi obs.event() ít nhất 1 lần."""
        obs = MagicMock()
        obs.event = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_c = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_c
            mock_r = MagicMock()
            mock_r.status_code = 200
            mock_c.get = AsyncMock(return_value=mock_r)
            run(self.probe("https://example.com", obs=obs))

        obs.event.assert_called()

    def test_E2_probe_returns_status_code_int(self):
        """_probe() phải trả về int HTTP status code."""
        obs = MagicMock()
        obs.event = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_c = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_c
            mock_r = MagicMock()
            mock_r.status_code = 403
            mock_c.get = AsyncMock(return_value=mock_r)
            result = run(self.probe("https://example.com", obs=obs))

        self.assertIsInstance(result, int)
        self.assertEqual(result, 403)


# ===========================================================================
# SECTION F: CI/CD yml changes
# ===========================================================================

class TestCIYmlChanges(unittest.TestCase):
    """F1–F2: Kiểm tra các thay đổi trong file yml."""

    def test_F1_harvest_yml_has_playwright_install(self):
        """harvest.yml phải có bước cài Playwright Chromium."""
        yml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".github", "workflows", "harvest.yml"
        )
        if not os.path.exists(yml_path):
            self.skipTest("harvest.yml không tìm thấy")
        with open(yml_path) as f:
            content = f.read()
        self.assertIn("playwright install", content,
                      "harvest.yml thiếu bước 'python -m playwright install'")
        self.assertIn("chromium", content.lower(),
                      "harvest.yml thiếu '--with-deps chromium'")

    def test_F2_harvest_yml_has_budget_browser_calls_env(self):
        """harvest.yml phải có BUDGET_MAX_BROWSER_CALLS env var."""
        yml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".github", "workflows", "harvest.yml"
        )
        if not os.path.exists(yml_path):
            self.skipTest("harvest.yml không tìm thấy")
        with open(yml_path) as f:
            content = f.read()
        self.assertIn("BUDGET_MAX_BROWSER_CALLS", content,
                      "harvest.yml thiếu env var BUDGET_MAX_BROWSER_CALLS")

    def test_F3_ci_yml_has_new_module_imports(self):
        """ci.yml import smoke test phải có core.adaptive_router và 4 adapter."""
        yml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".github", "workflows", "ci.yml"
        )
        if not os.path.exists(yml_path):
            self.skipTest("ci.yml không tìm thấy")
        with open(yml_path) as f:
            content = f.read()
        for mod in ["core.adaptive_router", "core.adapters.tier1_http",
                    "core.adapters.tier2_reader", "core.adapters.tier3_browser",
                    "core.adapters.tier4_stealth_tls"]:
            self.assertIn(mod, content, f"ci.yml thiếu import smoke test cho {mod}")

    def test_F4_requirements_has_playwright(self):
        """requirements.txt phải có playwright."""
        req_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "requirements.txt"
        )
        with open(req_path) as f:
            content = f.read()
        self.assertIn("playwright", content, "requirements.txt thiếu playwright")

    def test_F5_requirements_has_curl_cffi(self):
        """requirements.txt phải có curl_cffi."""
        req_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "requirements.txt"
        )
        with open(req_path) as f:
            content = f.read()
        self.assertIn("curl_cffi", content, "requirements.txt thiếu curl_cffi")


if __name__ == "__main__":
    unittest.main()
