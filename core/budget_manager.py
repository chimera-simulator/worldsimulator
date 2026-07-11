"""
core/budget_manager.py — Resource Budget Manager cho Repo 1
=============================================================
- 1 instance duy nhất / chu kỳ, main.py khởi tạo và truyền xuống từng
  agent (dependency injection).
- Thread-safe (Lock).
- Không bao giờ raise exception — consume_*() trả False khi hết budget.
- Giới hạn đọc từ env var, fallback về hằng số an toàn Free Tier.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class BudgetSnapshot:
    """Trạng thái budget tại một thời điểm — dùng để ghi vào PipelineLogger."""
    urls_used: int
    urls_max: int
    gemini_calls_used: int
    gemini_calls_max: int
    tokens_used: int
    tokens_max: int
    elapsed_seconds: float
    browser_calls_used: int = 0
    browser_calls_max: int = 0

    @property
    def urls_remaining(self) -> int:
        return max(0, self.urls_max - self.urls_used)

    @property
    def gemini_remaining(self) -> int:
        return max(0, self.gemini_calls_max - self.gemini_calls_used)

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.tokens_max - self.tokens_used)

    def to_dict(self) -> dict:
        return {
            "urls_used": self.urls_used,
            "urls_max": self.urls_max,
            "urls_remaining": self.urls_remaining,
            "gemini_calls_used": self.gemini_calls_used,
            "gemini_calls_max": self.gemini_calls_max,
            "gemini_calls_remaining": self.gemini_remaining,
            "tokens_used": self.tokens_used,
            "tokens_max": self.tokens_max,
            "tokens_remaining": self.tokens_remaining,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "browser_calls_used": self.browser_calls_used,
            "browser_calls_max": self.browser_calls_max,
        }


class BudgetManager:
    """
    Quản lý 3 loại tài nguyên cho một chu kỳ Repo 1:
      - max_urls        : tổng URL được phép scrape (t0 + t2 gộp lại)
      - max_gemini_calls: tổng lần gọi Gemini (Phase A + Phase B, tính cả retry)
      - max_tokens      : tổng token ước tính tiêu thụ

    Đọc từ env var (override từ CI/CD), fallback về default Free Tier.
    """

    # 7 keys * ~15 RPM = ~105 call/phút. Chu kỳ ≤30 phút → cap 300 call.
    # 300 call * ~1000 token/call ước tính = 300,000 token/chu kỳ.
    DEFAULT_MAX_URLS = 150
    DEFAULT_MAX_GEMINI_CALLS = 300
    DEFAULT_MAX_TOKENS = 300_000
    DEFAULT_MAX_BROWSER_CALLS = 15  # Playwright ~3-8s/lần, trần thấp tránh vượt 30 phút

    def __init__(
        self,
        max_urls: Optional[int] = None,
        max_gemini_calls: Optional[int] = None,
        max_tokens: Optional[int] = None,
        max_browser_calls: Optional[int] = None,   # [MỚI]
    ):
        self.max_urls = max_urls if max_urls is not None else int(
            os.getenv("BUDGET_MAX_URLS", str(self.DEFAULT_MAX_URLS))
        )
        self.max_gemini_calls = max_gemini_calls if max_gemini_calls is not None else int(
            os.getenv("BUDGET_MAX_GEMINI_CALLS", str(self.DEFAULT_MAX_GEMINI_CALLS))
        )
        self.max_tokens = max_tokens if max_tokens is not None else int(
            os.getenv("BUDGET_MAX_TOKENS", str(self.DEFAULT_MAX_TOKENS))
        )
        # [FIX] "max_browser_calls or ..." coi 0 là falsy -> im lặng rơi về
        # default 15 dù caller cố tình truyền 0 (budget cạn kiệt). Dùng
        # "is not None" để 0 được tôn trọng đúng nghĩa.
        self.max_browser_calls = max_browser_calls if max_browser_calls is not None else int(
            os.getenv("BUDGET_MAX_BROWSER_CALLS", str(self.DEFAULT_MAX_BROWSER_CALLS))
        )

        self._urls_used: int = 0
        self._gemini_calls_used: int = 0
        self._tokens_used: int = 0
        self._browser_calls_used: int = 0          # [MỚI]

        self._lock = threading.Lock()
        self._start_time = time.monotonic()

    # ------------------------------------------------------------------
    def consume_url(self, count: int = 1) -> bool:
        """Gọi TRƯỚC khi thêm URL vào queue scrape (t0) hoặc TRƯỚC khi build
        task fetch (t2). True nếu còn đủ, False nếu cạn."""
        with self._lock:
            if self._urls_used + count > self.max_urls:
                return False
            self._urls_used += count
            return True

    def consume_gemini_call(self, estimated_tokens: int = 1000) -> bool:
        """Gọi TRƯỚC mỗi lần thực sự bắn request tới Gemini (bên trong
        `_call_gemini()`, không phải ở `run_summarizer()`). Kiểm tra đồng
        thời cả call-count và token budget. Atomic: nếu 1 trong 2 điều
        kiện fail thì không trừ gì cả (all-or-nothing)."""
        with self._lock:
            if self._gemini_calls_used + 1 > self.max_gemini_calls:
                return False
            if self._tokens_used + estimated_tokens > self.max_tokens:
                return False
            self._gemini_calls_used += 1
            self._tokens_used += estimated_tokens
            return True

    def consume_browser_call(self, count: int = 1) -> bool:
        """Gọi TRƯỚC khi dùng tier3_browser (Playwright). True nếu còn budget."""
        with self._lock:
            if self._browser_calls_used + count > self.max_browser_calls:
                return False
            self._browser_calls_used += count
            return True

    def record_actual_tokens(self, delta_tokens: int) -> None:
        """Điều chỉnh counter khi có usage metadata thật từ Gemini API.
        `delta_tokens` = actual_tokens - estimated_tokens đã cộng trước đó
        trong consume_gemini_call() (có thể âm nếu ước tính dư, dương nếu
        ước tính thiếu). Không bao giờ để tokens_used < 0."""
        with self._lock:
            self._tokens_used = max(0, self._tokens_used + delta_tokens)

    def snapshot(self) -> BudgetSnapshot:
        with self._lock:
            return BudgetSnapshot(
                urls_used=self._urls_used,
                urls_max=self.max_urls,
                gemini_calls_used=self._gemini_calls_used,
                gemini_calls_max=self.max_gemini_calls,
                tokens_used=self._tokens_used,
                tokens_max=self.max_tokens,
                elapsed_seconds=time.monotonic() - self._start_time,
                browser_calls_used=self._browser_calls_used,   # [MỚI]
                browser_calls_max=self.max_browser_calls,      # [MỚI]
            )

    def is_url_budget_exhausted(self) -> bool:
        with self._lock:
            return self._urls_used >= self.max_urls

    def is_gemini_budget_exhausted(self) -> bool:
        with self._lock:
            return (
                self._gemini_calls_used >= self.max_gemini_calls
                or self._tokens_used >= self.max_tokens
            )
