"""
core/adapters/tier1_http.py — Tier 1: httpx + stealth headers
==============================================================
Adapter rẻ nhất. Di chuyển từ t2_scrape.py::scrape_url() phần fetch thông thường.
Output: HTML thô (str) hoặc None nếu fail.

[FIX mojibake] KHÔNG dùng resp.text — thuộc tính này tự đoán encoding chỉ
dựa vào HTTP Content-Type header, mà rất nhiều trang tiếng Việt không khai
báo charset ở header (chỉ khai trong <meta charset> bên trong HTML). Thay
vào đó lấy resp.content (bytes thô) rồi giải mã qua decode_html_bytes(),
hàm này đọc cả thẻ meta/BOM/chardet. Xem core/adapters/_decode.py để biết
chi tiết nguyên nhân lỗi.
"""
from __future__ import annotations
import logging
from typing import Optional
import httpx
import stealth
from core.adapters._decode import decode_html_bytes

logger = logging.getLogger(__name__)


async def fetch(url: str, obs=None) -> Optional[str]:
    """Fetch URL bằng httpx + stealth headers. Trả HTML thô hoặc None."""
    try:
        _, headers = stealth.get_stealth_headers()
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, headers=headers, timeout=20.0)
            resp.raise_for_status()
            return decode_html_bytes(resp.content, source_hint=url)
    except Exception as e:
        logger.warning(f"[tier1_http] Lỗi fetch '{url}': {e}")
        return None
