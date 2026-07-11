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
from domain_ban import is_academic_domain, is_domain_or_subdomain_in
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

# =============================================================================
# [MỚI — CODER 3 — Vấn đề #1: Scope/Blueprint Filtering] Gate 1.5
# =============================================================================
# Tín hiệu xác nhận nội dung thuộc phạm vi worldbuilding/sci-fi/fantasy
WORLDBUILDING_SCOPE_SIGNALS: set[str] = {
    "worldbuilding", "world-building", "world building",
    "concept art", "concept design", "character design",
    "sci-fi", "science fiction", "speculative fiction",
    "fantasy", "alien", "extraterrestrial",
    "species", "civilization", "planet", "lore",
    "fandom", "wiki", "universe", "fictional",
    "game design", "rpg", "roleplay",
    "artstation", "deviantart", "worldanvil", "pinterest",
}

WORLDBUILDING_SCOPE_PENALTY = 0.8  # Trừ điểm thay vì drop (để không quá strict)

# Domain whitelist: đây là nguồn worldbuilding/concept art nổi tiếng
SCOPE_DOMAINS = {
    "artstation.com", "deviantart.com", "worldanvil.com",
    "fandom.com", "pinterest.com", "conceptart.org",
    "imgur.com",  # thường là concept art share
}


def is_in_worldbuilding_scope(url: str, source_type: str, domain: str) -> bool:
    """Heuristic nhanh: URL/domain có thuộc phạm vi worldbuilding không.

    Kiểm tra domain whitelist trước (nhanh nhất), sau đó URL path.
    Không fetch nội dung ở đây — đó là việc của T2.
    """
    if is_domain_or_subdomain_in(domain, SCOPE_DOMAINS):
        return True

    # URL path check: có chứa tín hiệu worldbuilding không?
    url_lower = url.lower()
    return any(signal in url_lower for signal in WORLDBUILDING_SCOPE_SIGNALS)


def score_source(
    item: SearchResultItem,
    has_images: bool,
    is_academic_domain: bool,
    in_worldbuilding_scope: bool,  # [CODER 3]
) -> float:
    """Tính điểm 1 nguồn dựa trên source_type sơ bộ (từ t0) + tín hiệu ảnh
    thực tế (nếu đã biết) + penalty domain học thuật + penalty ngoài phạm vi
    worldbuilding (Gate 1.5)."""
    base_score = SCORE_BY_SOURCE_TYPE.get(item["source_type"], 1.0)

    if has_images:
        base_score += 0.5

    if is_academic_domain:
        base_score -= ACADEMIC_PENALTY

    if not in_worldbuilding_scope:           # [CODER 3]
        base_score -= WORLDBUILDING_SCOPE_PENALTY

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
    1. Với mỗi item -> tính score qua score_source (bao gồm Gate 1.5 —
       penalty nếu ngoài phạm vi worldbuilding).
    2. Gắn ip_heavy_flag = True nếu domain thuộc danh sách IP-heavy.
    3. Sort DESC theo score.
    4. GATE 1: drop item có score < threshold -> log reject_reason.
    5. Trả list đã sort + đã lọc, mỗi item có thêm field "score" và
       "in_worldbuilding_scope" (debug field — không persist sang DB).
    """
    scored: List[dict] = []

    for item in items:
        domain = _domain_of(item["url"])
        is_academic = is_academic_domain(domain)
        has_images = item["source_type"] == "visual_rich"
        in_scope = is_in_worldbuilding_scope(item["url"], item["source_type"], domain)  # [CODER 3]

        score = score_source(
            item,
            has_images=has_images,
            is_academic_domain=is_academic,
            in_worldbuilding_scope=in_scope,
        )
        ip_heavy = domain in IP_HEAVY_DOMAINS

        scored_item = dict(item)
        scored_item["score"] = score
        scored_item["ip_heavy_flag"] = ip_heavy
        scored_item["in_worldbuilding_scope"] = in_scope  # [CODER 3] để log/debug
        scored.append(scored_item)

    scored.sort(key=lambda x: x["score"], reverse=True)

    passed = [s for s in scored if s["score"] >= threshold]
    dropped = len(scored) - len(passed)
    out_of_scope_dropped = sum(
        1 for s in scored if not s.get("in_worldbuilding_scope") and s["score"] < threshold
    )

    if dropped:
        logger.info(
            f"🚫 [T1 Gate 1] Đã drop {dropped}/{len(scored)} URL "
            f"(score < {threshold}), reject_reason='low_visual_score'."
        )

    if out_of_scope_dropped:
        logger.info(
            f"🎯 [T1 Gate 1.5] Đã drop {out_of_scope_dropped} URL ngoài phạm vi worldbuilding "
            f"(score < {threshold} sau penalty -{WORLDBUILDING_SCOPE_PENALTY})."
        )

    logger.info(f"✅ [T1] Xếp hạng xong — {len(passed)} URL qua Gate 1.")
    return passed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
