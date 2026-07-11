"""
core/adapters/tier3_browser.py — Tier 3: Playwright (Chromium headless)
========================================================================
Đắt nhất (3-8s/call). Chỉ dùng sau khi tier4 thất bại hoặc site cần DOM interaction.
BudgetManager.consume_browser_call() phải được gọi TRƯỚC khi gọi module này
(kiểm tra trong adaptive_router.py, không phải ở đây).
Output: HTML thô hoặc None.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# asyncio.Semaphore để giới hạn concurrent Playwright (tránh OOM trên runner 7GB)
import asyncio
_BROWSER_SEMAPHORE = asyncio.Semaphore(2)  # Tối đa 2 tab Chromium cùng lúc


async def fetch(url: str, obs=None) -> Optional[str]:
    """Launch Chromium headless, load URL, trả innerHTML. None nếu fail."""
    try:
        from playwright.async_api import async_playwright  # lazy import
    except ImportError:
        logger.error("[tier3_browser] playwright chưa cài — pip install playwright")
        return None

    async with _BROWSER_SEMAPHORE:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                # User-Agent giả lập Chrome thật
                await page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/126.0.0.0 Safari/537.36"
                })
                await page.goto(url, timeout=30_000, wait_until="networkidle")
                html = await page.content()
                await browser.close()
                return html if html else None
        except Exception as e:
            logger.warning(f"[tier3_browser] Lỗi Playwright '{url}': {e}")
            return None
