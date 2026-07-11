"""
t1_classify.py — Agent 2: Ranking & Filtering (Gate 1)
=========================================================
[CX]
- Gate 1 nằm chính xác ở file này. Input: list URL thô từ t0. Output: list
  đã rank + đã drop dưới threshold.
- ip_heavy_flag chỉ là cảnh báo (flag), KHÔNG drop item ở bước này —
  quyết định drop/strip IP thuộc về summarizer.py (Phase A) và Gate 4.
- Không gọi LLM để classify — chỉ dùng heuristic/domain whitelist +
  có/không có ảnh (rule-based).
"""
from __future__ import annotations

import logging
from typing import List
from urllib.parse import urlparse

from config import VisualSourcePriority, VISUAL_SCORE_THRESHOLD
from domain_ban import is_academic_domain
from t0_search import SearchResultItem

logger = logging.getLogger(__name__)

# Danh sách wiki/fandom nổi tiếng gắn với IP thương mại lớn -> chỉ dùng để
# CẢNH BÁO (ip_heavy_flag), không loại ở Gate 1.
IP_HEAVY_DOMAINS = {
    "marvel.fandom.com", "starwars.fandom.com", "disney.fandom.com",
    "nintendo.fandom.com", "dc.fandom.com", "pixar.fandom.com",
    "harrypotter.fandom.com", "pokemon.fandom.com",
}

SCORE_BY_SOURCE_TYPE = {
    "visual_rich": 3.0,
    "visual_moderate": 2.0,
    "text_only": 1.0,
}

ACADEMIC_PENALTY = 1.2


def score_source(item: SearchResultItem, has_images: bool, is_academic_domain: bool) -> float:
    """Tính điểm 1 nguồn dựa trên source_type sơ bộ (từ t0) + tín hiệu ảnh
    thực tế (nếu đã biết) + penalty domain học thuật."""
    base_score = SCORE_BY_SOURCE_TYPE.get(item["source_type"], 1.0)

    if has_images:
        base_score += 0.5

    if is_academic_domain:
        base_score -= ACADEMIC_PENALTY

    return max(base_score, 0.0)


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def classify_and_rank(
    items: List[SearchResultItem],
    threshold: float = VISUAL_SCORE_THRESHOLD,
) -> List[dict]:
    """
    1. Với mỗi item -> tính score qua score_source.
    2. Gắn ip_heavy_flag = True nếu domain thuộc danh sách IP-heavy.
    3. Sort DESC theo score.
    4. GATE 1: drop item có score < threshold -> log reject_reason.
    5. Trả list đã sort + đã lọc, mỗi item có thêm field "score".
    """
    scored: List[dict] = []

    for item in items:
        domain = _domain_of(item["url"])
        is_academic = is_academic_domain(domain)
        has_images = item["source_type"] == "visual_rich"

        score = score_source(item, has_images=has_images, is_academic_domain=is_academic)
        ip_heavy = domain in IP_HEAVY_DOMAINS

        scored_item = dict(item)
        scored_item["score"] = score
        scored_item["ip_heavy_flag"] = ip_heavy
        scored.append(scored_item)

    scored.sort(key=lambda x: x["score"], reverse=True)

    passed = [s for s in scored if s["score"] >= threshold]
    dropped = len(scored) - len(passed)

    if dropped:
        logger.info(
            f"🚫 [T1 Gate 1] Đã drop {dropped}/{len(scored)} URL "
            f"(score < {threshold}), reject_reason='low_visual_score'."
        )

    logger.info(f"✅ [T1] Xếp hạng xong — {len(passed)} URL qua Gate 1.")
    return passed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
