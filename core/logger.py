"""
core/logger.py — Structured JSON Logger cho Repo 1
=====================================================
Dùng cùng BudgetManager: mỗi event log kèm budget_remaining snapshot.

Usage:
    from core.budget_manager import BudgetManager
    from core.logger import PipelineLogger

    budget = BudgetManager()
    log = PipelineLogger(run_id="run_...", budget=budget)
    log.event(step="T3_SUMMARIZE", agent="summarizer", status="SUCCESS",
              items_processed=1, tokens_used=950, message="Phase A+B pass")
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Literal, Optional

from core.budget_manager import BudgetManager

StatusType = Literal["SUCCESS", "WARNING", "ERROR", "SKIP", "START", "DONE"]

_raw_logger = logging.getLogger("OBS")


class PipelineLogger:
    """Wrapper quanh stdlib logging — mọi event serialize thành 1 dòng JSON
    ghi ra stderr. Tham số `budget` optional (None => budget_remaining={})."""

    VALID_STEPS = {
        "PIPELINE_START", "PIPELINE_DONE",
        "T0_SEARCH", "T1_CLASSIFY", "T2_SCRAPE",
        "T3_SUMMARIZE", "T4_NORMALIZE", "T5_DEDUP",
        "T5_5_LIBRARY_DISTILL", "T6_UPLOAD",
    }

    def __init__(self, run_id: str, budget: Optional[BudgetManager] = None):
        self.run_id = run_id
        self.budget = budget

    def event(
        self,
        step: str,
        agent: str,
        status: StatusType,
        message: str,
        items_processed: int = 0,
        tokens_used: int = 0,
        episode_id: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        budget_dict: dict = {}
        if self.budget is not None:
            budget_dict = self.budget.snapshot().to_dict()

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "step": step,
            "agent": agent,
            "status": status,
            "episode_id": episode_id,
            "items_processed": items_processed,
            "tokens_used": tokens_used,
            "budget_remaining": budget_dict,
            "message": message,
        }
        if extra:
            record["extra"] = extra

        line = json.dumps(record, ensure_ascii=False)
        print(line, file=sys.stderr)  # GitHub Actions capture stderr tự động

        level = logging.ERROR if status == "ERROR" else logging.INFO
        _raw_logger.log(level, line)

    def budget_exhausted(self, resource: Literal["url", "gemini"], agent: str) -> None:
        """Shortcut cảnh báo hết budget — agent dùng thay vì tự dựng message."""
        msg = (
            f"URL budget exhausted — agent '{agent}' dừng thu thập URL mới."
            if resource == "url"
            else f"Gemini budget exhausted — agent '{agent}' dừng gọi API."
        )
        self.event(
            step="T0_SEARCH" if resource == "url" else "T3_SUMMARIZE",
            agent=agent,
            status="WARNING",
            message=msg,
        )
