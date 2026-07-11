"""
core/adapters/tier4_stealth_tls.py — Tier 4: curl_cffi (TLS fingerprint impersonation)
========================================================================================
Vượt qua Cloudflare / WAF dựa trên TLS/JA3 fingerprint matching Chrome thật.
Rẻ hơn Playwright (~0.5-2s/call, không cần headless browser).
Được thử TRƯỚC tier3 khi probe trả 403/503.
Output: HTML thô hoặc None.

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
from core.adapters._decode import decode_html_bytes

logger = logging.getLogger(__name__)


async def fetch(url: str, obs=None) -> Optional[str]:
    """Fetch bằng curl_cffi với TLS impersonation Chrome 120."""
    try:
        from curl_cffi.requests import AsyncSession  # lazy import
    except ImportError:
        logger.error("[tier4_stealth_tls] curl_cffi chưa cài — pip install curl_cffi")
        return None

    try:
        async with AsyncSession(impersonate="chrome120") as session:
            resp = await session.get(url, timeout=25)
            if resp.status_code < 400:
                return decode_html_bytes(resp.content, source_hint=url)
            logger.warning(f"[tier4_stealth_tls] Status {resp.status_code} cho '{url}'")
            return None
    except Exception as e:
        logger.warning(f"[tier4_stealth_tls] Lỗi curl_cffi '{url}': {e}")
        return None
