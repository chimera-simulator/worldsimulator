"""
core/adaptive_router.py — AdaptiveRouter: Tiered Adaptive Fetching
===================================================================
Thay thế đoạn fetch đơn tầng trong t2_scrape.py::scrape_url().
Tuân thủ hoàn toàn SPEC_ADAPTIVE_ROUTER_T2.md:
  - 1 blackbook duy nhất (không tạo nguồn chân lý thứ hai)
  - Không tự mở MongoClient
  - BudgetManager/PipelineLogger injection
  - Output: HTML str | None (không đổi contract của scrape_url)
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

import httpx

import stealth
import domain_ban  # noqa: [FIX] import module (không phải from-import từng hàm)
# để test có thể patch domain_ban.<fn> và router thấy được thay đổi tại
# thời điểm gọi (from-import sẽ bind tên cục bộ tại import-time, khiến
# patch("domain_ban.record_failure"/"label_adapter") không có tác dụng).

if TYPE_CHECKING:
    from core.budget_manager import BudgetManager
    from core.logger import PipelineLogger

logger = logging.getLogger(__name__)

# Lazy imports cho các adapter — tránh ImportError khi playwright/curl_cffi chưa cài
from core.adapters import tier1_http, tier2_reader, tier3_browser, tier4_stealth_tls


# ---------------------------------------------------------------------------
# PROBE
# ---------------------------------------------------------------------------

async def _probe(url: str, obs: Optional["PipelineLogger"] = None) -> int:
    """GET nhẹ (HEAD nếu được, GET fallback) để lấy HTTP status code.

    - Timeout ngắn (8s) — chỉ cần status code, không cần body.
    - Log qua obs.event() để xuất hiện trong JSON log (không phải hộp đen).
    - Trả về HTTP status code (int). 999 nếu exception (connection error v.v.).
    """
    try:
        _, headers = stealth.get_stealth_headers()
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, headers=headers, timeout=8.0)
            status = resp.status_code
    except Exception as e:
        logger.debug(f"[probe] Exception cho '{url}': {e}")
        status = 999

    if obs:
        obs.event(
            step="T2_SCRAPE",
            agent="adaptive_router._probe",
            status="SUCCESS" if status < 400 else "WARNING",
            message=f"probe status={status} url={url}",
        )
    return status


# ---------------------------------------------------------------------------
# ROUTING TABLE
# ---------------------------------------------------------------------------

async def _fetch_by_adapter(
    adapter_name: str,
    url: str,
    budget: "BudgetManager",
    obs: Optional["PipelineLogger"],
) -> Optional[str]:
    """Gọi đúng adapter theo tên. Trả HTML hoặc None."""
    if adapter_name == "tier1_http":
        return await tier1_http.fetch(url, obs=obs)
    elif adapter_name == "tier2_reader":
        return await tier2_reader.fetch(url, obs=obs)
    elif adapter_name == "tier4_stealth_tls":
        return await tier4_stealth_tls.fetch(url, obs=obs)
    elif adapter_name == "tier3_browser":
        # Budget check TRƯỚC khi Playwright
        if not budget.consume_browser_call():
            if obs:
                obs.event(
                    step="T2_SCRAPE",
                    agent="adaptive_router",
                    status="WARNING",
                    message=f"browser_call budget exhausted — skip tier3 for '{url}'",
                )
            return None
        return await tier3_browser.fetch(url, obs=obs)
    else:
        logger.error(f"[adaptive_router] Unknown adapter: {adapter_name}")
        return None


def _select_adapter_sequence(probe_status: int) -> list[str]:
    """Quyết định thứ tự adapter dựa trên kết quả probe.

    Bảng §1 SPEC:
      200       → [tier1_http]
      403/503   → [tier4_stealth_tls, tier3_browser]
      khác      → [tier1_http, tier4_stealth_tls, tier3_browser]

    Tier2_reader được dùng khi tier1 trả HTML nhưng content rỗng (JS-heavy).
    Hiện tại: tier2 được xét sau tier1 nếu tier1 trả về empty string.
    """
    if probe_status == 200:
        return ["tier1_http", "tier2_reader"]
    elif probe_status in (403, 503):
        return ["tier4_stealth_tls", "tier3_browser"]
    else:
        # Mọi status khác (301/302 bị miss, 429, 999=connection err, v.v.)
        return ["tier1_http", "tier4_stealth_tls", "tier3_browser"]


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

async def fetch_with_router(
    url: str,
    domain: str,
    blackbook: dict,
    budget: "BudgetManager",
    obs: Optional["PipelineLogger"] = None,
) -> Optional[str]:
    """Fetch URL với tiered adapter routing.

    Thay thế đoạn:
        _, headers = stealth.get_stealth_headers()
        resp = await client.get(url, headers=headers, timeout=20.0)
    trong t2_scrape.py::scrape_url().

    Returns:
        HTML thô (str) hoặc None nếu tất cả tier thất bại / domain bị ban.
    """
    # Guard 1: Domain đang bị ban -> skip toàn bộ, không probe
    if domain and domain_ban.is_banned(blackbook, domain):
        logger.info(f"[router] Skip banned domain '{domain}'")
        if obs:
            obs.event(
                step="T2_SCRAPE",
                agent="adaptive_router",
                status="SKIP",
                message=f"domain banned — skip '{url}'",
            )
        return None

    # Guard 2: Domain có adapter label hợp lệ -> dùng thẳng, không probe
    cached_adapter = domain_ban.get_adapter_label(blackbook, domain) if domain else None
    if cached_adapter:
        logger.debug(f"[router] Using cached adapter '{cached_adapter}' for '{domain}'")
        html = await _fetch_by_adapter(cached_adapter, url, budget, obs)
        if html:
            domain_ban.record_success(blackbook, domain)
            domain_ban.label_adapter(blackbook, domain, cached_adapter, ttl_days=7)
            return html
        # Cache miss (site thay đổi behavior) -> fall through để probe lại
        logger.info(f"[router] Cached adapter '{cached_adapter}' failed for '{domain}' — re-probing")

    # Step 1: Probe để chọn adapter sequence
    probe_status = await _probe(url, obs=obs)
    adapter_sequence = _select_adapter_sequence(probe_status)

    # Step 2: Thử từng adapter theo thứ tự
    for adapter_name in adapter_sequence:
        html = await _fetch_by_adapter(adapter_name, url, budget, obs)
        if html:  # Thành công
            if obs:
                obs.event(
                    step="T2_SCRAPE",
                    agent="adaptive_router",
                    status="SUCCESS",
                    message=f"adapter='{adapter_name}' probe_status={probe_status} url={url}",
                )
            if domain:
                domain_ban.record_success(blackbook, domain)
                domain_ban.label_adapter(blackbook, domain, adapter_name, ttl_days=7)
            return html

    # Mọi tier đều fail
    logger.warning(f"[router] Tất cả adapter thất bại cho '{url}' (probe={probe_status})")
    if obs:
        obs.event(
            step="T2_SCRAPE",
            agent="adaptive_router",
            status="ERROR",
            message=f"all adapters failed probe_status={probe_status} url={url}",
        )
    if domain:
        domain_ban.record_failure(blackbook, domain)
    return None
