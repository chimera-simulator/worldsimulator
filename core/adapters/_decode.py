"""
core/adapters/_decode.py — Giải mã bytes HTML robust, dùng chung cho mọi tier
================================================================================
[FIX mojibake] Nguyên nhân gốc:
- tier1_http.py (httpx) và tier4_stealth_tls.py (curl_cffi) trước đây dùng
  `resp.text` — thuộc tính này tự đoán encoding CHỈ dựa vào header
  Content-Type của HTTP response.
- Rất nhiều trang tiếng Việt không khai báo charset trong HTTP header, mà chỉ
  khai trong thẻ <meta charset="utf-8"> bên trong HTML. Khi đó httpx/curl_cffi
  phải đoán mò và có thể chọn sai (ví dụ Latin-1/Windows-1252) TRƯỚC KHI kịp
  đọc thẻ meta.
- Ở t2_scrape.py, BeautifulSoup(html, "html.parser") nhận vào một chuỗi str
  ĐÃ bị giải mã sai từ trước — lúc này không còn cách nào tự sửa lại được nữa.
  Kết quả: text lưu vào fiction_knowledge bị hỏng kiểu
  "Ä‘áº¥t nÆ°á»›c" thay vì "đất nước".

Giải pháp: các adapter KHÔNG dùng resp.text nữa. Thay vào đó lấy bytes thô
(resp.content) rồi tự giải mã bằng bs4.UnicodeDammit — công cụ này đọc cả
thẻ <meta charset>, BOM, và fallback sang chardet nếu cần, thay vì tin mù
quáng vào HTTP header như .text làm.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def decode_html_bytes(content: bytes, source_hint: str = "") -> str:
    """Giải mã bytes HTML thô -> str, ưu tiên meta charset / BOM / chardet
    thay vì chỉ dựa vào HTTP header (nguồn gốc lỗi mojibake).

    Args:
        content: bytes thô nhận từ response (resp.content). KHÔNG dùng
            resp.text vì thuộc tính đó tự đoán encoding từ header trước khi
            đọc được thẻ <meta charset> trong HTML.
        source_hint: URL hoặc tên nguồn, chỉ dùng để log khi cần debug.

    Returns:
        str đã giải mã đúng. Hàm này không bao giờ raise — fallback cuối
        cùng là utf-8 với errors="replace" để pipeline không bao giờ crash
        chỉ vì encoding lạ.
    """
    if not content:
        return ""

    try:
        from bs4 import UnicodeDammit  # lazy import — đã có sẵn qua beautifulsoup4
    except ImportError:
        logger.warning(
            f"[_decode] Thiếu beautifulsoup4 (UnicodeDammit) — "
            f"fallback utf-8 cho '{source_hint}'."
        )
        return content.decode("utf-8", errors="replace")

    try:
        # is_html=True -> UnicodeDammit sẽ tự tìm và đọc <meta charset="...">
        # hoặc <meta http-equiv="Content-Type" content="...charset=...">
        # bên trong HTML, thay vì chỉ tin vào HTTP header.
        dammit = UnicodeDammit(content, is_html=True)
        if dammit.unicode_markup is not None:
            detected = (dammit.original_encoding or "").lower()
            if detected and detected not in ("utf-8", "utf8"):
                logger.info(
                    f"[_decode] '{source_hint}' phát hiện encoding "
                    f"'{dammit.original_encoding}' -> đã chuẩn hoá về utf-8."
                )
            return dammit.unicode_markup
    except Exception as e:
        logger.warning(f"[_decode] UnicodeDammit lỗi cho '{source_hint}': {e}")

    # Fallback cuối cùng: không bao giờ để pipeline crash vì lỗi encoding.
    return content.decode("utf-8", errors="replace")
