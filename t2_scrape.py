"""
t2_scrape.py — Agent 3: DOM Cleaning + Image Metadata Extraction (Gate 2)
============================================================================
[CX]
- Gate 2 nằm chính xác ở file này, ngay sau khi scrape xong, TRƯỚC khi bất
  kỳ dữ liệu nào được gửi sang summarizer.py — mục đích là không lãng phí
  token Gemini.
- Content filter dùng VISUAL_KEYWORD_FILTER, KHÔNG còn dùng
  SCIENCE_ONTOLOGY_KEYWORDS (biến này đã bị xóa ở config.py).
- Không parse/gọi LLM ở đây — chỉ rule-based text/DOM processing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Tuple, TypedDict
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from config import VISUAL_KEYWORD_FILTER, VISUAL_KEYWORD_DENSITY_THRESHOLD
from domain_ban import is_banned, record_failure, record_success
import stealth
import core.adaptive_router  # [FIX] import module (không phải from-import) để
# test có thể patch("core.adaptive_router.fetch_with_router") và scrape_url()
# thấy được bản mock tại thời điểm gọi.

logger = logging.getLogger(__name__)

# Class/id blacklist cho DOM cleaning
_JUNK_SELECTORS = [
    "script", "style", "nav", "footer", "header", "aside", "iframe",
    "[class*='ads']", "[id*='ads']", "[class*='sponsored']",
    "[class*='cookie']", "[class*='popup']", "[class*='banner']",
]


class ImageMetadata(TypedDict):
    alt_text: str
    dimensions: Optional[Tuple[int, int]]
    image_url: str
    context_paragraph: str


class ScrapedDocument(TypedDict):
    raw_text: str
    image_metadata: List[ImageMetadata]
    target_form_field: str
    source_domain: str
    working_planet_id: str   # MỚI [SPEC_ADDENDUM_2_7 — Coder 1]
    archetype_id: str        # MỚI [SPEC_ADDENDUM_2_7 — Coder 1]


def clean_dom(html: str) -> BeautifulSoup:
    """Parse HTML, loại bỏ script/ads/nav/footer/sponsored-content."""
    soup = BeautifulSoup(html, "html.parser")
    for selector in _JUNK_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()
    return soup


def extract_image_metadata(soup: BeautifulSoup) -> List[ImageMetadata]:
    """Tìm toàn bộ <img> -> alt, src, width/height nếu có, và text đoạn
    cha gần nhất (context)."""
    results: List[ImageMetadata] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue

        alt = img.get("alt", "") or ""

        dimensions: Optional[Tuple[int, int]] = None
        try:
            width = int(img.get("width", 0) or 0)
            height = int(img.get("height", 0) or 0)
            if width and height:
                dimensions = (width, height)
        except (ValueError, TypeError):
            dimensions = None

        parent = img.find_parent(["p", "figure", "div"])
        context_paragraph = parent.get_text(strip=True)[:500] if parent else ""

        results.append(
            ImageMetadata(
                alt_text=alt,
                dimensions=dimensions,
                image_url=src,
                context_paragraph=context_paragraph,
            )
        )
    return results


def compute_visual_keyword_density(text: str) -> float:
    """Đếm số lần xuất hiện các từ trong VISUAL_KEYWORD_FILTER / tổng số
    từ trong đoạn -> trả tỷ lệ."""
    if not text:
        return 0.0

    lowered = text.lower()
    words = lowered.split()
    total_words = len(words) or 1

    hit_count = sum(lowered.count(keyword) for keyword in VISUAL_KEYWORD_FILTER)
    return hit_count / total_words


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


async def scrape_url(
    client: Optional[httpx.AsyncClient],   # Giữ để backward-compat; có thể None
    item: dict,
    blackbook: dict,
    budget=None,   # BudgetManager | None  ← đã có trong run_scrape_pipeline
    obs=None,      # PipelineLogger | None ← đã có trong run_scrape_pipeline
    working_planet_id: str = "",   # MỚI [SPEC_ADDENDUM_2_7 — Coder 1]
    archetype_id: str = "",        # MỚI [SPEC_ADDENDUM_2_7 — Coder 1]
) -> Optional[ScrapedDocument]:
    """
    1. Fetch HTML (stealth headers để tránh bot detection).
    2. soup = clean_dom(html).
    3. raw_text = soup.get_text().
    4. image_metadata = extract_image_metadata(soup).
    5. SÀN TUYỆT ĐỐI (T2.5 addendum): raw_text rỗng tuyệt đối VÀ
       image_metadata rỗng -> return None (reject_reason='empty_content'),
       chạy TRƯỚC check density hiện có.
    6. density = compute_visual_keyword_density(raw_text).
    7. GATE 2: nếu density < threshold VÀ không có ảnh -> return None.
    8. Return ScrapedDocument (gồm working_planet_id/archetype_id gán từ
       tham số truyền vào).
    """
    url = item["url"]
    domain = _domain_of(url)

    if domain and is_banned(blackbook, domain):
        logger.info(f"⏭️ [T2] Bỏ qua '{url}' (domain đang bị ban tạm thời).")
        return None

    # [MỚI] fetch qua AdaptiveRouter thay vì httpx trực tiếp
    html = await core.adaptive_router.fetch_with_router(
        url=url,
        domain=domain,
        blackbook=blackbook,
        budget=budget,
        obs=obs,
    )
    if html is None:
        # router đã gọi record_failure() nội bộ nếu cần
        return None

    try:
        soup = clean_dom(html)
        raw_text = soup.get_text(separator=" ", strip=True)
        image_metadata = extract_image_metadata(soup)

        # [MỚI — SPEC_ADDENDUM_2_7 T2.5] Sàn tuyệt đối rất nhẹ, TRƯỚC check
        # density hiện có: raw_text rỗng tuyệt đối VÀ image_metadata rỗng ->
        # drop ngay. KHÔNG chặn raw_text rỗng nhưng CÓ ảnh (triết lý
        # Visual-First — ảnh vẫn có giá trị dù không có text).
        if not raw_text.strip() and not image_metadata:
            logger.info(
                f"🚫 [T2 Gate 2] Drop '{url}' — reject_reason='empty_content'."
            )
            return None

        density = compute_visual_keyword_density(raw_text)

        if density < VISUAL_KEYWORD_DENSITY_THRESHOLD and len(image_metadata) == 0:
            logger.info(
                f"🚫 [T2 Gate 2] Drop '{url}' — reject_reason='low_visual_density' "
                f"(density={density:.4f}, images=0)."
            )
            return None

        return ScrapedDocument(
            raw_text=raw_text,
            image_metadata=image_metadata,
            target_form_field=item.get("target_form_field", ""),
            source_domain=domain,
            working_planet_id=working_planet_id,
            archetype_id=archetype_id,
        )
    except Exception as e:
        logger.error(f"❌ [T2] Lỗi xử lý DOM cho '{url}': {e}")
        return None


async def run_scrape_pipeline(
    items: List[dict],
    blackbook: dict,
    budget=None,   # BudgetManager | None
    obs=None,      # PipelineLogger | None
    working_planet_id: str = "",   # MỚI [SPEC_ADDENDUM_2_7 — Coder 1]
    archetype_id: str = "",        # MỚI [SPEC_ADDENDUM_2_7 — Coder 1]
) -> List[ScrapedDocument]:
    """Scrape song song (asyncio) toàn bộ URL đã qua Gate 1.

    [MỚI] `budget` (BudgetManager | None): vì `asyncio.gather()` chạy TẤT
    CẢ task cùng lúc, không thể "dừng giữa chừng" như vòng `for` tuần tự.
    Phải lọc `items` xuống danh sách được phép TRƯỚC KHI tạo `tasks`.

    [MỚI — SPEC_ADDENDUM_2_7 T2.5] `working_planet_id`/`archetype_id`:
    truyền xuống mỗi lời gọi `scrape_url()` để gán vào từng
    `ScrapedDocument` (dùng bởi t2_5_planet_gate.py ở bước sau).
    """
    documents: List[ScrapedDocument] = []

    # [MỚI] Lọc items xuống mức budget cho phép TRƯỚC khi build task —
    # vì asyncio.gather() chạy song song, không thể chặn giữa chừng.
    allowed_items = items
    if budget is not None:
        allowed_items = []
        for item in items:
            if not budget.consume_url():
                if obs:
                    obs.budget_exhausted(resource="url", agent="t2_scrape")
                logger.warning(
                    f"⚠️ [T2] URL budget exhausted — chỉ scrape {len(allowed_items)}/{len(items)} URL."
                )
                break
            allowed_items.append(item)

    tasks = [
        scrape_url(
            None, item, blackbook, budget=budget, obs=obs,
            working_planet_id=working_planet_id, archetype_id=archetype_id,
        )
        for item in allowed_items
    ]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for doc in results:
        if doc is not None:
            documents.append(doc)

    logger.info(f"✅ [T2] Scrape hoàn thành — {len(documents)}/{len(allowed_items)} document qua Gate 2.")
    return documents


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
