"""
t0_search.py — Agent 1: Dynamic Query Generator (Visual-First)
=================================================================
[CX]
- KHÔNG hardcode tên field ("terrain_patterns", "architecture_patterns"...)
  trực tiếp trong file này — luôn lấy qua get_form_fields() từ config.py.
- KHÔNG gọi LLM ở đây.
- Domain khoa học/học thuật phải bị hạ priority hoặc drop — dùng lại
  domain_ban.py hiện có, mở rộng danh sách chặn.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import List, Literal, Optional, TypedDict
from urllib.parse import urlparse

import httpx

from config import get_form_fields, MASTER_SCHEMA_2_0
from domain_ban import (
    is_banned,
    is_academic_domain,
    is_domain_or_subdomain_in,
    record_failure,
    record_success,
)
import stealth

logger = logging.getLogger(__name__)

QueryVariant = Literal["Concept", "Design", "Description", "Reference", "Variant"]

VISUAL_RICH_DOMAINS = {
    "artstation.com", "deviantart.com", "pinterest.com", "conceptart.org",
    "fandom.com", "worldanvil.com",
}


class SearchResultItem(TypedDict):
    url: str
    target_form_field: str
    source_type: str  # "visual_rich" | "visual_moderate" (sơ bộ). "text_only"
                       # không còn được T0 sinh ra nữa — academic domain bị
                       # `continue` loại thẳng, xem search_field() (Fix Check
                       # T0 — SPEC_gate6_5_planet_occupation_and_core_fixes).
    ip_heavy_flag: bool
    query_variant: str
    field_already_filled: bool  # [MỚI — BUG #2] True nếu field này KHÔNG nằm
                                 # trong target_fields (tức đã đầy, chỉ search
                                 # vì đang ở full-scan mode)


def generate_queries_for_field(field_name: str) -> List[str]:
    """Sinh đúng 5 query variant cho 1 field (lấy phần cuối của dot-path
    làm từ khóa chính, ví dụ 'form_1_planet_foundation.planet_identity.terrain_patterns'
    -> 'terrain patterns')."""
    keyword = field_name.split(".")[-1].replace("_", " ")
    return [
        f"{keyword} concept art",
        f"{keyword} design",
        f"{keyword} description worldbuilding",
        f"{keyword} reference sheet",
        f"{keyword} variant types",
    ]


_QUERY_VARIANT_ORDER: List[QueryVariant] = [
    "Concept", "Design", "Description", "Reference", "Variant",
]


def _load_search_engines() -> dict:
    try:
        with open("search_engines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Không thể đọc search_engines.json: {e}")
        return {"engines": [], "banned_domains": [], "priority_sources": []}


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


async def _fetch_search_results(
    client: httpx.AsyncClient, engine: dict, query: str, blackbook: dict
) -> List[str]:
    """Gọi 1 search engine, trả về list URL thô. Không raise — lỗi mạng chỉ
    log và trả list rỗng (không được làm crash toàn bộ pipeline)."""
    url = engine["url_template"].format(query=httpx.QueryParams({"q": query}).get("q", query))
    domain = _domain_of(url)

    if domain and is_banned(blackbook, domain):
        logger.info(f"⏭️  Bỏ qua engine '{engine.get('name')}' (domain đang bị ban tạm thời).")
        return []

    try:
        _, headers = stealth.get_stealth_headers()
        resp = await client.get(url, headers=headers, timeout=15.0)
        resp.raise_for_status()
        if domain:
            record_success(blackbook, domain)

        # Trích href thô bằng parser nhẹ (BeautifulSoup ở t2, ở đây chỉ cần
        # regex/text đơn giản để không phụ thuộc DOM parser tại t0).
        from bs4 import BeautifulSoup  # import cục bộ để t0 không bắt buộc phụ thuộc nếu không dùng

        soup = BeautifulSoup(resp.text, "html.parser")
        selector = engine.get("link_selector", "a[href^='http']")
        exclude = engine.get("exclude_domain_in_href", "")
        links = []
        for a in soup.select(selector):
            href = a.get("href")
            if href and href.startswith("http") and (not exclude or exclude not in href):
                links.append(href)
        return links
    except Exception as e:
        logger.warning(f"⚠️ Lỗi search engine '{engine.get('name')}' cho query '{query}': {e}")
        if domain:
            record_failure(blackbook, domain)
        return []


MAX_FALLBACK_ENGINES = 3  # trần số engine thử/query, tránh đốt quota khi tất cả đều fail


async def _fetch_with_fallback(
    client: httpx.AsyncClient,
    sorted_engines: List[dict],
    query: str,
    blackbook: dict,
) -> List[str]:
    """Thử lần lượt các engine theo thứ tự priority tăng dần (engine[0] =
    priority cao nhất). Dừng ngay khi một engine trả về kết quả không rỗng.
    Nếu engine hiện tại rỗng/lỗi (bao gồm cả trường hợp bị ban tạm thời trong
    blackbook), tự động rơi xuống engine kế tiếp. Giới hạn tối đa
    MAX_FALLBACK_ENGINES lần thử để không đốt quota khi toàn bộ engine đều
    down.
    """
    last_engine_name = None
    for engine in sorted_engines[:MAX_FALLBACK_ENGINES]:
        urls = await _fetch_search_results(client, engine, query, blackbook)
        if urls:
            if last_engine_name:
                logger.info(
                    f"✅ Fallback thành công: query '{query}' lấy được kết quả "
                    f"từ engine dự phòng '{engine.get('name')}'."
                )
            return urls
        last_engine_name = engine.get("name")
        logger.warning(
            f"↪️  Engine '{last_engine_name}' rỗng/lỗi cho query '{query}', "
            f"thử engine dự phòng kế tiếp (nếu còn)..."
        )

    logger.error(f"❌ Toàn bộ engine dự phòng đều thất bại cho query '{query}'.")
    return []


async def search_field(
    field_name: str, blackbook: dict, max_results_per_query: int = 5
) -> List[SearchResultItem]:
    """Sinh 5 query cho field_name, gọi các search engine song song
    (asyncio), gắn target_form_field vào từng URL kết quả."""
    engines_cfg = _load_search_engines()
    engines = engines_cfg.get("engines", [])
    banned_domains = set(engines_cfg.get("banned_domains", []))
    priority_sources = set(engines_cfg.get("priority_sources", []))

    if not engines:
        logger.error("❌ Không có search engine nào được cấu hình (search_engines.json rỗng).")
        return []

    queries = generate_queries_for_field(field_name)
    results: List[SearchResultItem] = []

    sorted_engines = sorted(engines, key=lambda e: e.get("priority", 99))

    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = []
        task_meta = []
        for variant, query in zip(_QUERY_VARIANT_ORDER, queries):
            tasks.append(_fetch_with_fallback(client, sorted_engines, query, blackbook))
            task_meta.append(variant)

        raw_results = await asyncio.gather(*tasks, return_exceptions=False)

    for variant, urls in zip(task_meta, raw_results):
        for url in urls[:max_results_per_query]:
            domain = _domain_of(url)
            if is_domain_or_subdomain_in(domain, banned_domains):
                continue

            # MỚI — loại bỏ NGAY academic domain tại T0, không đưa vào
            # results để downgrade ở T1 nữa. Khác với banned_domains (ban
            # tạm thời do lỗi mạng, có cooldown) — đây là loại VĨNH VIỄN
            # theo bản chất nguồn (khoa học khách quan, không phải lỗi kỹ
            # thuật), nên dùng `continue` giống banned_domains, không qua
            # is_visual_rich nữa vì academic domain không bao giờ nên được
            # coi là visual_rich dù nằm trong VISUAL_RICH_DOMAINS do nhầm.
            if is_academic_domain(domain):
                logger.info(
                    f"🚫 [T0] Loại academic domain '{domain}' ngay tại search "
                    f"(field='{field_name}'), không đưa qua T1 downgrade nữa."
                )
                continue

            is_visual_rich = domain in VISUAL_RICH_DOMAINS or domain in priority_sources
            source_type = "visual_rich" if is_visual_rich else "visual_moderate"
            # LƯU Ý: nhánh "text_only" (dành riêng cho academic) không còn
            # cần thiết vì academic đã bị continue ở trên — mọi URL còn lại
            # tới đây chắc chắn KHÔNG academic.

            results.append(
                SearchResultItem(
                    url=url,
                    target_form_field=field_name,
                    source_type=source_type,
                    ip_heavy_flag=False,  # t1_classify.py sẽ tinh chỉnh chính xác hơn
                    query_variant=variant,
                    field_already_filled=False,  # patch lại ở run_search_pipeline() (mục 2.5 SPEC)
                )
            )

    return results


async def run_search_pipeline(
    blackbook: dict,
    budget=None,   # BudgetManager | None
    obs=None,      # PipelineLogger | None
    target_fields: Optional[List[str]] = None,   # [MỚI — Progressive Gap Filling]
) -> List[SearchResultItem]:
    """
    1. Duyệt toàn bộ field trong MASTER_SCHEMA_2_0 (qua get_form_fields) —
       trừ khi `target_fields` được truyền vào, khi đó chỉ duyệt field
       đang pending (Gap-Aware Mode, xem SPEC_PROGRESSIVE_GAP_FILLING_T0).
    2. Với mỗi field, sinh 5 query, gọi search engine, gắn target_form_field.
    3. Trả về kết quả ĐÃ loại academic domain (Fix Check T0 —
       SPEC_gate6_5_planet_occupation_and_core_fixes). banned_domains
       (tạm thời, có cooldown) vẫn lọc như cũ; academic domain giờ bị
       loại VĨNH VIỄN ngay tại đây, không còn chờ T1 hạ điểm.

    [SPEC_FIX_P1 — Vấn đề 1] `blackbook` giờ được TRUYỀN VÀO (dependency
    injection) thay vì tự load/save "blackbook.json" bên trong hàm này.
    Hàm chỉ MUTATE IN-PLACE dict `blackbook` (qua search_field ->
    _fetch_search_results -> record_success/record_failure). Việc
    load/save file JSON là trách nhiệm DUY NHẤT của main.py
    (load_blackbook/save_blackbook), để tránh race giữa T0 và T2 khi mỗi
    bên tự đọc/ghi file riêng.

    [MỚI] `budget` (BudgetManager | None): trừ quota URL cho mỗi kết quả
    thêm vào `results`. Khi cạn, dừng thu thập ngay và trả về những gì đã
    có (không raise, không crash pipeline).

    [MỚI — Progressive Gap Filling] `target_fields` (List[str] | None):
    nếu được truyền và không rỗng, CHỈ search các field trong danh sách
    này (Gap-Aware Mode) thay vì toàn bộ 29 field (Full-Scan Mode). Field
    "rác" (không còn tồn tại trong schema hiện hành) sẽ bị lọc bỏ; nếu
    toàn bộ target_fields đều rác, fallback về Full-Scan Mode.
    """
    full_field_set = (
        get_form_fields("form_1_planet_foundation")
        + get_form_fields("form_2_civilization_layer")
    )

    if not full_field_set:
        logger.error("❌ [T0] get_form_fields() trả về rỗng — kiểm tra MASTER_SCHEMA_2_0 trong config.py.")
        return []

    if target_fields:
        # [Gap-Aware Mode] Chỉ lặp qua field đang pending — KHÔNG gọi
        # get_form_fields() cho full set. Lọc chéo với full_field_set để
        # loại field "rác" (field name không tồn tại trong schema hiện
        # hành, ví dụ do DB cũ từ version schema trước) — tránh sinh
        # query vô nghĩa cho field đã bị xoá khỏi MASTER_SCHEMA_2_0.
        valid_target_fields = [f for f in target_fields if f in full_field_set]
        skipped_unknown = set(target_fields) - set(valid_target_fields)
        if skipped_unknown:
            logger.warning(
                f"⚠️ [T0] Bỏ qua {len(skipped_unknown)} field không còn "
                f"tồn tại trong schema hiện hành: {sorted(skipped_unknown)}"
            )

        if valid_target_fields:
            all_fields = valid_target_fields
            logger.info(
                f"🎯 [T0] Gap-Aware Mode — chỉ tìm {len(all_fields)} "
                f"field đang thiếu / {len(full_field_set)} field tổng."
            )
        else:
            # Toàn bộ target_fields đều "rác" -> không còn field hợp lệ
            # nào để search -> fallback full-scan thay vì trả [] im lặng.
            logger.warning(
                "⚠️ [T0] target_fields được truyền vào nhưng không field "
                "nào hợp lệ sau khi đối chiếu schema — fallback full-scan."
            )
            all_fields = full_field_set
    else:
        # Fallback logic cũ — target_fields=None hoặc rỗng.
        all_fields = full_field_set
        logger.info(f"🔎 [T0] Full-Scan Mode — tìm toàn bộ {len(all_fields)} field.")

    results: List[SearchResultItem] = []
    for field in all_fields:
        try:
            field_results = await search_field(field, blackbook)
        except Exception as e:
            logger.error(f"❌ [T0] Lỗi khi search field '{field}': {e}")
            continue

        # [MỚI — BUG #2] Patch cờ field_already_filled: chỉ có ý nghĩa khi
        # đang ở Gap-Aware Mode (target_fields không rỗng); ở Full-Scan Mode
        # không có khái niệm "đã đầy" nên luôn để False.
        is_gap_field = bool(target_fields) and field in (target_fields or [])
        for item in field_results:
            item["field_already_filled"] = (not is_gap_field) if target_fields else False

        # [MỚI] Trừ quota URL cho từng kết quả của field này.
        for item in field_results:
            if budget is not None and not budget.consume_url():
                if obs:
                    obs.budget_exhausted(resource="url", agent="t0_search")
                logger.warning("⚠️ [T0] URL budget exhausted — dừng thu thập.")
                logger.info(f"✅ [T0] Hoàn thành sớm — {len(results)} URL / dừng giữa {len(all_fields)} field.")
                return results
            results.append(item)

        # Anti-ban: nghỉ ngẫu nhiên giữa các field, giữ convention delay hiện có.
        await asyncio.sleep(random.uniform(1.0, 3.0))

    logger.info(
        f"✅ [T0] Hoàn thành search pipeline — {len(results)} URL hợp lệ "
        f"/ {len(all_fields)} field (mode="
        f"{'gap_aware' if target_fields else 'full_scan'})."
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_search_pipeline({}))
