"""
Stealth Utilities v2.0 - Async First & Modern Browser Fingerprints
Được thiết kế cho World Simulator Pipeline (GitHub Free Tier).
- 100% Async (không block event loop)
- Rotate User-Agent mới nhất (Chrome 125+, Firefox 127+, Safari 17.5+)
- Full HTTP/2 Headers với Sec-Ch-Ua chuẩn xác
- Hỗ trợ Accept-Encoding: zstd (mới trên Chrome hiện đại)
"""
import asyncio
import random
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. MODERN USER-AGENTS (Cập nhật giữa 2024)
# ==============================================================================
USER_AGENTS = [
    # Chrome 125/126 trên Windows (Phổ biến nhất, ít bị doubt)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome trên MacOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Firefox 127+ trên Windows (Tách biệt hoàn toàn TLS fingerprint)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Safari 17.5 trên MacOS (Rất ít site block Safari Mac)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Edge 125 (Dùng engine Chromium nhưng có Sec-Ch-Ua riêng)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

# ==============================================================================
# 2. BASE HEADERS (HTTP/2 Client Hints chuẩn xác)
# ==============================================================================
_BASE_CHROME_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    # Thêm 'zstd' - Chrome 125+ đã báo hỗ trợ decoding này
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Viewport-Width": "1920", # Giả lập màn hình full HD
}

_BASE_FIREFOX_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

_BASE_SAFARI_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# Mapping Sec-Ch-Ua chính xác theo Version (Tránh bị Cloudflare flag là giả mạo)
_CHROME_SEC_CHUA_MAP = {
    "126.0.0.0": '"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="99"',
    "125.0.0.0": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
}

_EDGE_SEC_CHUA_MAP = {
    "125.0.0.0": '"Chromium";v="125", "Microsoft Edge";v="125", "Not-A.Brand";v="99"',
}


# ==============================================================================
# 3. CORE FUNCTIONS
# ==============================================================================
def get_random_ua() -> str:
    """Lấy 1 User-Agent ngẫu nhiên từ pool hiện đại."""
    return random.choice(USER_AGENTS)

def get_stealth_headers() -> Tuple[str, Dict[str, str]]:
    """
    Trả về bộ headers ngụy trang hoàn toàn đồng bộ với User-Agent.
    Returns:
        Tuple[user_agent_string, headers_dict]
    """
    ua = get_random_ua()
    
    if "Firefox" in ua:
        headers = _BASE_FIREFOX_HEADERS.copy()
    elif "Safari" in ua and "Chrome" not in ua:
        headers = _BASE_SAFARI_HEADERS.copy()
    else:
        headers = _BASE_CHROME_HEADERS.copy()
        
        # Cập nhật Sec-Ch-Ua khớp tuyệt đối với version
        sec_ch_ua = None
        if "Edg/" in ua:
            for ver, sec_str in _EDGE_SEC_CHUA_MAP.items():
                if ver in ua:
                    sec_ch_ua = sec_str
                    break
        else:
            for ver, sec_str in _CHROME_SEC_CHUA_MAP.items():
                if ver in ua:
                    sec_ch_ua = sec_str
                    break
        
        if sec_ch_ua:
            headers["Sec-Ch-Ua"] = sec_ch_ua
            
        # Cập nhật Platform hint cho Mac/Windows
        if "Macintosh" in ua:
            headers["Sec-Ch-Ua-Platform"] = '"macOS"'
        else:
            headers["Sec-Ch-Ua-Platform"] = '"Windows"'

    headers["User-Agent"] = ua
    return ua, headers


# ==============================================================================
# 4. ASYNC DELAY FUNCTIONS (Quan trọng nhất cho t0/t2)
# ==============================================================================
async def async_human_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """
    Async Delay giả lập con người đọc page.
    Được dùng SAU khi request thành công (giữa các trang).
    Giảm xuống 2-5s vì đã có rate limit của Budget Manager.
    """
    delay = random.uniform(min_sec, max_sec)
    logger.debug(f"   ⏳ Async human delay: {delay:.1f}s")
    await asyncio.sleep(delay)

async def async_keyword_break(min_sec: float = 5.0, max_sec: float = 12.0):
    """
    Async Delay giữa các từ khóa tìm kiếm (tại T0).
    Giúp tránh trigger 'Automated Search' của Google/Bing/DDG.
    """
    delay = random.uniform(min_sec, max_sec)
    logger.info(f"   ☕ Nghỉ giữa keyword (async): {delay:.1f}s...")
    await asyncio.sleep(delay)

async def async_domain_cooldown(min_sec: float = 10.0, max_sec: float = 20.0):
    """
    Async Delay khi một domain trả về 429 (Rate Limit) hoặc bị t0 đánh dấu fail.
    """
    delay = random.uniform(min_sec, max_sec)
    logger.warning(f"   🛡️ Domain cooldown (async): {delay:.1f}s...")
    await asyncio.sleep(delay)


# ==============================================================================
# 5. BACKWARD COMPATIBILITY (Chỉ dùng nếu gọi sync, KHÔNG DÙNG TRONG MAIN LOOP)
# ==============================================================================
def human_delay(min_sec: float = 8.0, max_sec: float = 15.0):
    """[DEPRECATED] Chỉ dùng trong script test thủ công. KHÔNG dùng trong pipeline."""
    delay = random.uniform(min_sec, max_sec)
    logger.warning(f"   ⚠️ SYNC BLOCKING DELAY: {delay:.1f}s (Đổi sang async_human_delay!)")
    import time
    time.sleep(delay)

def keyword_break(min_sec: float = 30.0, max_sec: float = 60.0):
    """[DEPRECATED] Chỉ dùng trong script test thủ công."""
    delay = random.uniform(min_sec, max_sec)
    logger.warning(f"   ⚠️ SYNC BLOCKING KEYWORD BREAK: {delay:.1f}s")
    import time
    time.sleep(delay)
