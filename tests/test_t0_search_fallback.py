"""
tests/test_t0_search_fallback.py — Unit test cho P1-C (Sequential Engine
Fallback) trong t0_search.py, theo mục 4 (ACCEPTANCE CRITERIA) của
SPEC_FIX_P1C_P1D_SearchFallback_DomainBan.md.

Chạy: python3 -m unittest tests.test_t0_search_fallback -v  (từ thư mục repo1/)
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import t0_search
from t0_search import _fetch_with_fallback, MAX_FALLBACK_ENGINES


def _engine(name: str, priority: int) -> dict:
    return {"name": name, "priority": priority, "url_template": "https://{name}.example/?q={{query}}".format(name=name)}


class TestFetchWithFallback(unittest.IsolatedAsyncioTestCase):
    async def test_falls_back_to_second_engine_when_first_is_empty(self):
        """Engine priority 1 trả [], engine priority 2 trả kết quả ->
        _fetch_with_fallback phải trả về kết quả của engine 2."""
        sorted_engines = [_engine("engine1", 1), _engine("engine2", 2)]

        async def fake_fetch(client, engine, query, blackbook):
            if engine["name"] == "engine1":
                return []
            return ["http://example.com/x"]

        with patch.object(t0_search, "_fetch_search_results", side_effect=fake_fetch) as mocked:
            result = await _fetch_with_fallback(None, sorted_engines, "query", {})

        self.assertEqual(result, ["http://example.com/x"])
        self.assertEqual(mocked.call_count, 2)

    async def test_stops_after_max_fallback_engines_and_returns_empty(self):
        """Toàn bộ MAX_FALLBACK_ENGINES engine đầu đều trả [] -> hàm trả [],
        và KHÔNG gọi thêm engine thứ MAX_FALLBACK_ENGINES + 1 dù config có
        khai báo nhiều hơn."""
        sorted_engines = [
            _engine(f"engine{i}", i) for i in range(1, MAX_FALLBACK_ENGINES + 3)
        ]

        fake_fetch = AsyncMock(return_value=[])

        with patch.object(t0_search, "_fetch_search_results", fake_fetch):
            result = await _fetch_with_fallback(None, sorted_engines, "query", {})

        self.assertEqual(result, [])
        self.assertEqual(fake_fetch.call_count, MAX_FALLBACK_ENGINES)

    async def test_first_engine_success_calls_only_once(self):
        """Engine priority 1 trả kết quả ngay -> chỉ gọi đúng 1 lần
        _fetch_search_results, không gọi engine 2 (không tốn quota thừa)."""
        sorted_engines = [_engine("engine1", 1), _engine("engine2", 2)]

        fake_fetch = AsyncMock(return_value=["http://example.com/ok"])

        with patch.object(t0_search, "_fetch_search_results", fake_fetch):
            result = await _fetch_with_fallback(None, sorted_engines, "query", {})

        self.assertEqual(result, ["http://example.com/ok"])
        self.assertEqual(fake_fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
