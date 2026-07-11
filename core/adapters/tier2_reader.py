"""
core/adapters/tier2_reader.py — Tier 2: Jina Reader (r.jina.ai)
================================================================
Không cần JS render — Jina tự render và trả markdown/text sạch.
Dùng khi tier1 trả HTML rỗng (JS-heavy site) nhưng site không block bot (status 200).
Không cần API key cho public use-case ở rate thấp.
Output: text/markdown hoặc None.

[FIX mojibake — CODER 3] KHÔNG dùng resp.text — thuộc tính này tự đoán
encoding chỉ dựa vào HTTP Content-Type header. Jina Reader trả text/plain
nhưng vẫn có thể encoding sai cho nội dung tiếng Việt.
Thay vào đó: lấy resp.content (bytes) -> decode_html_bytes().
Xem core/adapters/_decode.py để biết chi tiết nguyên nhân lỗi.
"""
from __future__ import annotations
import logging
from typing import Optional
import httpx
from core.adapters._decode import decode_html_bytes  # [FIX CODER 3]

logger = logging.getLogger(__name__)

JINA_BASE = "https://r.jina.ai/"


async def fetch(url: str, obs=None) -> Optional[str]:
    """Đọc URL qua Jina Reader endpoint. Trả nội dung text hoặc None."""
    jina_url = JINA_BASE + url
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                jina_url,
                headers={"Accept": "text/plain", "User-Agent": "Mozilla/5.0"},
                timeout=30.0,
            )
            resp.raise_for_status()
            # [FIX CODER 3] Thay resp.text.strip() -> decode_html_bytes(resp.content)
            text = decode_html_bytes(resp.content, source_hint=jina_url).strip()
            return text if text else None
    except Exception as e:
        logger.warning(f"[tier2_reader] Lỗi Jina fetch '{url}': {e}")
        return None
