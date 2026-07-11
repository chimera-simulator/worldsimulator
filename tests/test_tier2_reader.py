"""
tests/test_tier2_reader.py — Unit test cho fix mojibake trong
core/adapters/tier2_reader.py, theo mục 6B (Definition of Done — Coder 3)
của SPEC_HARVEST_CYCLE_FIXES_v2_3CODERS.md.

Chạy: python3 -m unittest tests.test_tier2_reader -v  (từ thư mục repo1/)
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.adapters import tier2_reader


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestTier2Mojibake(unittest.TestCase):
    def test_tier2_mojibake_bom_utf8(self):
        """Input bytes có UTF-8 BOM + tiếng Việt phải được giải mã đúng
        thành 'đất nước', KHÔNG được trả về resp.text (vốn có thể mojibake)."""
        raw_bytes = "\ufeffđất nước".encode("utf-8")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.content = raw_bytes
            # [Quan trọng] resp.text cố tình để SAI (mojibake giả lập) để
            # xác nhận fetch() KHÔNG dùng resp.text nữa.
            mock_resp.text = "Ä‘áº¥t nÆ°á»›c"
            mock_resp.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)

            result = run(tier2_reader.fetch("https://example.com/page"))

        self.assertIsNotNone(result)
        self.assertIn("đất nước", result)
        self.assertNotIn("Ã", result)  # dấu hiệu điển hình của mojibake

    def test_tier2_mojibake_non_utf8_windows1252(self):
        """Input bytes encode bằng Windows-1252 (không phải UTF-8) vẫn phải
        được decode_html_bytes() xử lý mà không raise và không rỗng."""
        raw_bytes = "café".encode("windows-1252")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.content = raw_bytes
            mock_resp.text = "cafÃ©"  # mojibake giả lập
            mock_resp.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)

            result = run(tier2_reader.fetch("https://example.com/page2"))

        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    def test_tier2_returns_none_on_empty_content(self):
        """Content rỗng sau decode -> fetch() phải trả None (không trả
        chuỗi rỗng)."""
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.content = b""
            mock_resp.text = ""
            mock_resp.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)

            result = run(tier2_reader.fetch("https://example.com/empty"))

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
