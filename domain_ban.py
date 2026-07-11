"""
DOMAIN BAN - Single Source Of Truth cho trạng thái banned/failures của domain
===============================================================================
Trước đây T0 (search) và T2 (scrape) mỗi bên tự đọc/ghi blackbook.json với
logic ban riêng lẻ, lệch nhau (nhánh reddit ở T2 không bao giờ ban dù fail
bao nhiêu lần), và MỘT KHI đã ban thì VĨNH VIỄN không có cơ chế gỡ. Hệ quả:
một lần rate-limit tạm thời của IP GitHub Actions cũng đủ loại vĩnh viễn một
nguồn tốt (vd. orionsarm.com, worldanvil.com — vốn ít traffic nên dễ bị nhầm
là bot) ra khỏi pipeline, trừ khi sửa tay blackbook.json.

Module này tập trung toàn bộ logic vào 1 nơi, dùng chung cho T0 và T2:
- Ban có hạn (cooldown), tự động cho thử lại sau BAN_COOLDOWN_DAYS.
- Cùng 1 ngưỡng/cùng 1 hành vi cho mọi loại scraper (HTTP, Playwright, Reddit).
"""
from datetime import datetime, timezone, timedelta

BAN_COOLDOWN_DAYS = 7        # Sau 7 ngày, domain tự động được thử lại
BAN_THRESHOLD_FAILURES = 3   # Số lần fail liên tiếp trước khi ban tạm thời

# =============================================================================
# [CẬP NHẬT — Repo 1 Visual-First] ACADEMIC_DOMAIN_BLACKLIST
# =============================================================================
# Domain học thuật/khoa học bị HẠ ĐIỂM (không ban vĩnh viễn) ở t1_classify.py
# (Gate 1) và tránh ưu tiên ở t0_search.py — Repo 1 giờ ưu tiên nguồn giàu
# tín hiệu thị giác (concept art, worldbuilding wiki) thay vì nguồn khoa học
# khách quan như bản cũ.
ACADEMIC_DOMAIN_BLACKLIST = {
    "nasa.gov", "esa.int", "nature.com", "science.org", "arxiv.org",
    "researchgate.net", "academia.edu", "scholar.google.com",
    "sciencedirect.com", "ncbi.nlm.nih.gov", "springer.com", "wiley.com",
    "jstor.org", "pubmed.ncbi.nlm.nih.gov", "cell.com", "pnas.org",
    "ieee.org", "acm.org", "frontiersin.org", "mdpi.com", "tandfonline.com",
}

ACADEMIC_DOMAIN_SUFFIXES = (".edu", ".ac.uk", ".ac.jp")


def _is_domain_or_subdomain(netloc: str, banned_domain: str) -> bool:
    """True nếu netloc CHÍNH XÁC là banned_domain, hoặc là bất kỳ subdomain
    cấp nào của nó (vd. banned_domain='esa.int' -> match 'esa.int',
    'm.esa.int', 'sciences.esa.int', 'a.b.esa.int'...).
    So khớp không phân biệt hoa/thường.
    """
    netloc = (netloc or "").lower().strip()
    banned_domain = (banned_domain or "").lower().strip()
    if not netloc or not banned_domain:
        return False
    return netloc == banned_domain or netloc.endswith("." + banned_domain)


def is_domain_or_subdomain_in(domain: str, blacklist) -> bool:
    """True nếu `domain` khớp CHÍNH XÁC hoặc là subdomain của bất kỳ entry
    nào trong `blacklist` (set/list các domain gốc, vd banned_domains,
    ACADEMIC_DOMAIN_BLACKLIST). Dùng thay cho phép so sánh `in` (exact-match)
    ở mọi nơi trong pipeline kiểm tra domain bị cấm.
    """
    domain = (domain or "").lower().strip()
    if not domain:
        return False
    return any(_is_domain_or_subdomain(domain, banned) for banned in blacklist)


def is_academic_domain(domain: str) -> bool:
    """True nếu domain thuộc danh sách học thuật/khoa học (blacklist chính
    xác hoặc hậu tố .edu/.ac.*). Dùng bởi t0_search.py và t1_classify.py."""
    domain = (domain or "").lower()
    if is_domain_or_subdomain_in(domain, ACADEMIC_DOMAIN_BLACKLIST):
        return True
    return any(domain.endswith(suffix) for suffix in ACADEMIC_DOMAIN_SUFFIXES)


def is_banned(blackbook: dict, domain: str) -> bool:
    """True nếu domain đang bị ban VÀ vẫn còn trong thời gian cooldown."""
    entry = blackbook.get(domain)
    if not entry or entry.get("status") != "banned":
        return False

    banned_until = entry.get("banned_until")
    if not banned_until:
        # Bản ghi cũ từ trước khi có cooldown (không có banned_until) -> coi
        # như đã hết hạn, cho thử lại thay vì ban vĩnh viễn mãi mãi.
        return False

    try:
        expiry = datetime.fromisoformat(banned_until)
    except ValueError:
        return False

    return datetime.now(timezone.utc) < expiry


def record_failure(blackbook: dict, domain: str) -> bool:
    """
    Tăng bộ đếm fail cho domain. Trả về True nếu domain vừa bị ban ở lần gọi
    này (vừa chạm ngưỡng BAN_THRESHOLD_FAILURES).
    """
    entry = blackbook.setdefault(domain, {"failures": 0, "status": "active", "skill": "HTTP"})
    entry["failures"] = entry.get("failures", 0) + 1

    if entry["failures"] >= BAN_THRESHOLD_FAILURES:
        entry["status"] = "banned"
        entry["banned_until"] = (
            datetime.now(timezone.utc) + timedelta(days=BAN_COOLDOWN_DAYS)
        ).isoformat()
        return True
    return False


def record_success(blackbook: dict, domain: str):
    """Cào/tìm thành công -> reset hoàn toàn trạng thái domain về active."""
    entry = blackbook.setdefault(domain, {"failures": 0, "status": "active", "skill": "HTTP"})
    entry["failures"] = 0
    entry["status"] = "active"
    entry.pop("banned_until", None)


# =============================================================================
# [MỚI — AdaptiveRouter] Adapter label cache trong blackbook
# =============================================================================

def label_adapter(blackbook: dict, domain: str, adapter_name: str, ttl_days: int = 7) -> None:
    """Ghi nhãn adapter thành công cho domain vào blackbook.

    - Cập nhật field 'skill' thành tên adapter (tier1_http | tier2_reader |
      tier3_browser | tier4_stealth_tls).
    - Set adapter_label_valid_until = now + ttl_days.
    - KHÔNG đụng vào 'status', 'banned_until', 'failures' — tránh xóa trạng thái ban.

    Gọi sau khi fetch_with_router() thành công, thay vì record_success() (router
    gọi record_success() riêng sau đó).
    """
    entry = blackbook.setdefault(
        domain, {"failures": 0, "status": "active", "skill": "HTTP"}
    )
    entry["skill"] = adapter_name
    entry["adapter_label_valid_until"] = (
        datetime.now(timezone.utc) + timedelta(days=ttl_days)
    ).isoformat()


def get_adapter_label(blackbook: dict, domain: str) -> str | None:
    """Trả về tên adapter đã lưu nếu còn hạn, ngược lại trả None.

    None có nghĩa là cần probe lại để chọn adapter — KHÔNG có nghĩa là domain bị ban.
    """
    entry = blackbook.get(domain)
    if not entry:
        return None

    until_str = entry.get("adapter_label_valid_until")
    if not until_str:
        return None

    try:
        expiry = datetime.fromisoformat(until_str)
    except ValueError:
        return None

    if datetime.now(timezone.utc) >= expiry:
        return None

    adapter = entry.get("skill")
    # Chỉ trả về nếu là tên adapter hợp lệ (không trả "HTTP" mặc định cũ)
    valid_adapters = {"tier1_http", "tier2_reader", "tier3_browser", "tier4_stealth_tls"}
    return adapter if adapter in valid_adapters else None
