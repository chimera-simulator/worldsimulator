# Repo 1 — Visual-First Design Pattern Harvester (`visual_first_v2`)

Pipeline tự động thu thập, chọn lọc và chuẩn hóa dữ liệu tham khảo hình ảnh
(concept art, thiết kế nhân vật, kiến trúc, sinh vật, công nghệ...) từ web,
qua các bước **T0 → T5**, ghi kết quả vào MongoDB để phục vụ hệ thống world
simulator downstream.

```
T0 search  →  T1 classify  →  T2 scrape (AdaptiveRouter)  →  Summarizer (Gemini)
   →  T3 normalize (Gate 5 + Global Rule Library)  →  T4 deduplicate
   →  T4.5 library distill  →  T5 upload (MongoDB)
```

---

## 1. Cài đặt

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Chỉ cần nếu dùng tier3_browser (Playwright) — không bắt buộc để chạy test
python -m playwright install --with-deps chromium
```

Yêu cầu: Python 3.11+.

## 2. Biến môi trường

| Biến | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|
| `MONGODB_URI` | Có (production) | `""` | Connection string MongoDB (Repo 1 chỉ đọc/ghi qua `mongo_shared.get_shared_db()`, không tự tạo client mới ở nơi khác). |
| `MONGODB_DB_NAME` | Không | `world_simulator` | Tên database. |
| `GEMINI_MODEL_NO_1..7` | Có (production) | — | API key Gemini, xoay vòng round-robin qua tối đa 7 key để né rate-limit free tier (đọc trong `config.py::load_gemini_api_keys()`). |
| `GEMINI_MODEL_NAME` | Không | `gemini-2.5-flash` | Model Gemini dùng cho Phase A/B extraction. |
| `BUDGET_MAX_URLS` | Không | `150` | Trần tổng URL được scrape / chu kỳ. |
| `BUDGET_MAX_GEMINI_CALLS` | Không | `300` | Trần tổng lượt gọi Gemini / chu kỳ. |
| `BUDGET_MAX_TOKENS` | Không | `300000` | Trần tổng token ước tính / chu kỳ. |
| `BUDGET_MAX_BROWSER_CALLS` | Không | `15` | Trần số lần dùng `tier3_browser` (Playwright) / chu kỳ — mỗi lần tốn 3-8s nên phải giới hạn thấp để không vượt timeout 30 phút của GitHub Actions. |
| `BLACKBOOK_PATH` | Không | `blackbook.json` | File state round-robin/dedup/domain-ban/adapter-label, load/save đúng 1 lần mỗi chu kỳ (chỉ `main.py` được đụng vào). |

## 3. Chạy pipeline

```bash
python main.py
```

`main.py` là **entrypoint duy nhất** — nó load `blackbook.json` một lần, chạy
tuần tự T0 → T5, rồi ghi lại `blackbook.json` trong khối `finally` (không mất
tiến độ nếu pipeline lỗi giữa chừng).

Trên GitHub Actions, workflow `.github/workflows/harvest.yml` chạy 1 chu kỳ
mỗi ngày (cron) hoặc thủ công (`workflow_dispatch`), tự cài Playwright
Chromium, restore/save `blackbook.json` qua `actions/cache`.

## 4. AdaptiveRouter (T2 — fetch HTML)

Thay vì gọi thẳng `httpx` cho mọi URL, `t2_scrape.py::scrape_url()` gọi
`core.adaptive_router.fetch_with_router()`, tự chọn 1 trong 4 "tier" theo độ
khó của site:

| Tier | Công cụ | Khi nào dùng | Chi phí |
|---|---|---|---|
| `tier1_http` | `httpx` + stealth headers | Probe trả `200` | Rẻ nhất |
| `tier2_reader` | Jina Reader (`r.jina.ai`) | Sau `tier1_http` nếu HTML rỗng (site JS-heavy) | Rẻ |
| `tier4_stealth_tls` | `curl_cffi` (TLS fingerprint giả Chrome) | Probe trả `403`/`503` (WAF/Cloudflare) | Trung bình |
| `tier3_browser` | Playwright Chromium headless | Sau khi `tier4_stealth_tls` fail | Đắt nhất — có `BudgetManager.consume_browser_call()` chặn trước, và `asyncio.Semaphore(2)` giới hạn 2 tab song song |

Domain nào từng fetch thành công bằng 1 adapter sẽ được "nhớ" trong
`blackbook.json` (`skill` + `adapter_label_valid_until`, TTL 7 ngày) để lần
sau **bỏ qua bước probe**, gọi thẳng adapter đó — chỉ probe lại nếu cache
miss hoặc hết hạn. Domain bị ban (3 lần fail liên tiếp) bị `fetch_with_router()`
chặn ngay từ đầu, không tốn request nào.

## 5. Chạy test

```bash
# Toàn bộ AdaptiveRouter (offline, không cần Mongo/Playwright/curl_cffi thật)
python3 -m unittest tests.test_adaptive_router_spec -v   # 38/38 pass

# Regression
python3 -m unittest tests.test_domain_ban_subdomain -v   # 12/12 pass
python3 -m unittest tests.test_budget_manager -v          # 8/8 pass

# Các bộ test khác trong CI
python3 -m unittest tests.test_rule_library -v            # xem mục 6 — hiện đang FAIL
python3 -m unittest tests.test_t3_normalize_check_g -v
```

CI (`.github/workflows/ci.yml`) chạy lint cú pháp (`flake8` mức E9/F63/F7/F82),
import smoke test toàn bộ module `core.*`, rồi chạy
`tests.test_rule_library` + `tests.test_t3_normalize_check_g`.

---

## 6. ~~⚠️ Lỗi~~ ✅ Đã fix: `tests.test_rule_library` (contract `load_active_rules()`)

**Đã xử lý theo Phương án A** (giữ tuple, sửa các nơi gọi) — giữ lại cờ
`rule_check_skipped` vì đây là tính năng có chủ đích, giúp phân biệt "0 rule
active hợp lệ" (Mongo OK, collection rỗng) với "load lỗi/fail-open" (Mongo
offline hoặc query lỗi) — 2 trường hợp trước đây bị lẫn vào nhau khi hàm chỉ
trả `[]`.

Các thay đổi:

- `main.py` (~dòng 312): unpack đúng tuple
  `active_rules, rule_check_skipped = load_active_rules(db)`. Khi
  `rule_check_skipped=True`, log WARNING rõ ràng + ghi `obs.event(...)` để
  Gate 5 chạy fail-open không còn là "hộp đen" (trước đây `len(active_rules)`
  luôn ra `2` — độ dài tuple — do nhận nhầm kiểu dữ liệu, và `run_gate_5()`
  nhận nguyên tuple thay vì list rule dict).
- `tests/test_rule_library.py`: 2 test cũ (`test_none_db_returns_empty_fail_open`,
  `test_failing_db_returns_empty_fail_open`) sửa lại để unpack tuple và assert
  đúng cả `rules == []` lẫn `rule_check_skipped is True`. Thêm 2 test mới
  (`test_success_returns_rules_and_skipped_false`,
  `test_success_empty_collection_not_treated_as_skipped`) để khóa chặt hành
  vi "collection rỗng nhưng Mongo OK" KHÔNG bị coi là fail-open.
- `rule_library.py`: **không đổi** — hàm `load_active_rules()` vốn đã đúng
  thiết kế tuple `(rules, rule_check_skipped)`, lỗi chỉ nằm ở phía gọi.

Kết quả: `python3 -m unittest tests.test_rule_library -v` → **9/9 pass**
(7 test cũ + 2 test mới), không ảnh hưởng AdaptiveRouter/BudgetManager/domain_ban
(67/67 test liên quan vẫn xanh).

---

## 7. Cấu trúc thư mục chính

```
core/
  adaptive_router.py       # Router chọn tier fetch (SPEC2)
  budget_manager.py        # Giới hạn URL/Gemini call/token/browser call
  adapters/
    tier1_http.py / tier2_reader.py / tier3_browser.py / tier4_stealth_tls.py
  anti_detect.py            # Extension point (placeholder)
  logger.py                 # PipelineLogger (JSON structured log)
domain_ban.py                # Ban tạm thời domain lỗi liên tục + cache adapter label
rule_library.py              # Global Rule Library / Gate 5 Check G (xem mục 6)
t0_search.py .. t5_upload.py # Các bước pipeline T0-T5
tests/                       # unittest, chạy offline (mock/stub)
.github/workflows/
  ci.yml       # Lint + import smoke test + unit test trên mọi PR
  harvest.yml  # Chạy 1 chu kỳ harvest thật (cron / thủ công)
```
