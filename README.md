# Repo 1 — Visual-First Design Pattern Harvester (`visual_first_v2` / `rulesworldsimulator`)

Pipeline tự động thu thập, chọn lọc và chuẩn hóa dữ liệu tham khảo hình ảnh
(concept art, thiết kế nhân vật, kiến trúc, sinh vật, trang phục, công nghệ...)
từ web, chuẩn hóa qua các bước **T0 → T5**, rồi ghi vào MongoDB để làm nguồn
"Global Rule Library" / "lib_entities" phục vụ hệ thống World Simulator
(Chimera) downstream.

```
T0 search → T1 classify → T2 scrape (AdaptiveRouter) → Summarizer (Gemini)
  → T3 normalize (Gate 5 + Global Rule Library) → T4 deduplicate
  → T4.5 library distill → T5 upload (MongoDB)
```

---

## 1. Hướng dẫn sử dụng repo trên GitHub

### 1.1. Cài đặt local

```bash
git clone <repo-url> && cd rulesworldsimulator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Chỉ cần nếu muốn chạy thật tier3_browser (Playwright) — không bắt buộc để chạy test
python -m playwright install --with-deps chromium
```

Yêu cầu: Python 3.11+.

### 1.2. Biến môi trường chính

| Biến | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|
| `MONGODB_URI` | Có (production) | `""` | Connection string, chỉ truy cập qua `mongo_shared.get_shared_db()`. |
| `MONGODB_DB_NAME` | Không | `world_simulator` | Tên database. |
| `GEMINI_MODEL_NO_1..7` | Có (production) | — | API key Gemini, xoay vòng round-robin để né rate-limit free tier. |
| `BUDGET_MAX_URLS` / `BUDGET_MAX_GEMINI_CALLS` / `BUDGET_MAX_TOKENS` | Không | 150 / 300 / 300000 | Trần tài nguyên mỗi chu kỳ harvest. |
| `BUDGET_MAX_SECONDS` | Không | 2700 (45 phút) | Trần thời gian chạy — pipeline tự graceful-stop, không cần GitHub hard-kill. |
| `BLACKBOOK_PATH` | Không | `blackbook.json` | File state (round-robin keyword, dedup, domain-ban, adapter cache) — chỉ `main.py` được đọc/ghi. |

### 1.3. Chạy pipeline

```bash
python main.py
```

`main.py` là **entrypoint duy nhất**: load `blackbook.json` một lần, chạy tuần
tự T0 → T5, và luôn ghi lại `blackbook.json` trong khối `finally` (không mất
tiến độ nếu pipeline lỗi giữa chừng).

### 1.4. Chạy trên GitHub Actions

Repo có 3 workflow trong `.github/workflows/`:

- **`ci.yml`** — chạy trên mọi push/PR vào `main`: syntax check, lint mức
  nghiêm trọng (flake8 `E9,F63,F7,F82`), import smoke test toàn bộ module
  core, và unit test gate-blocking (`test_rule_library`,
  `test_t3_normalize_check_g`). Đây là điều kiện bắt buộc trước khi merge.
- **`harvest.yml`** — chạy 1 chu kỳ harvest thật (T0→T5), theo cron 1
  lần/ngày hoặc thủ công (`workflow_dispatch`, có tùy chọn `dry_run` và
  reset `blackbook` cache). Có `concurrency` group để không cho 2 chu kỳ
  chồng nhau.
- **`mongo1_cleanup.yml`** — dọn dẹp/TTL dữ liệu MongoDB định kỳ.

### 1.5. Chạy test cục bộ

```bash
python3 -m unittest tests.test_rule_library -v
python3 -m unittest tests.test_t3_normalize_check_g -v

# Các bộ test khác (không nằm trong CI gating, một số theo TDD nên có thể
# đang fail có chủ đích cho tới khi implement xong theo SPEC)
python3 -m unittest discover -s tests -v
```

### 1.6. Quy trình đóng góp

- Mỗi thay đổi lớn nên đi kèm **tài liệu thiết kế (SPEC)** trước khi code —
  đây là quy ước bắt buộc trong repo (xem mục 2).
- Mỗi coder/track chỉ sửa file trong phạm vi sở hữu của mình (scoped file
  ownership) để tránh xung đột giữa các track chạy song song.
- PR phải qua `ci.yml` xanh mới được merge vào `main`.

---

## 2. Nguyên tắc và biện pháp kỹ thuật sử dụng trong repo

### 2.1. Spec-first / Design-before-code
Các thay đổi kiến trúc lớn (AdaptiveRouter, Global Rule Library, Library
Distiller...) đều bắt đầu bằng tài liệu SPEC mô tả rõ vấn đề, contract hàm,
test case kỳ vọng — rồi mới implement. Nhiều test trong `tests/` được viết
theo kiểu TDD, cố ý fail cho tới khi phần implement tương ứng hoàn tất.

### 2.2. Observability > Complexity
Mọi gate/bước xử lý quan trọng (Gate 5 Check G/D/F, Quality Scorer, budget
manager...) đều log JSON có cấu trúc qua `core/logger.py::PipelineLogger`
và ghi report (`quality_gate_report`, `obs.event(...)`) thay vì "hộp đen" —
ưu tiên dễ debug hơn là tối ưu độ ngắn gọn của code.

### 2.3. Single source of truth cho state
`blackbook.json` (round-robin keyword, dedup cursor, domain-ban, adapter
label cache) chỉ được load/save đúng 1 lần bởi `main.py`, truyền vào các
bước con qua dependency injection và mutate in-place — tránh race condition
giữa các bước tự mở/ghi file riêng lẻ.

### 2.4. Fail-open có kiểm soát cho các phụ thuộc ngoài
Khi MongoDB hoặc rule query lỗi, các gate liên quan (vd. Global Rule Library
ở Gate 5) fail-open (không chặn pipeline) nhưng **luôn gắn cờ riêng biệt**
(`rule_check_skipped`) để phân biệt "0 kết quả hợp lệ" với "lỗi kết nối" —
tránh 2 tình huống khác nhau bị gộp lẫn.

### 2.5. Tiered fetching (AdaptiveRouter) để tiết kiệm chi phí & né chặn
`core/adaptive_router.py` chọn 1 trong 4 tier theo độ khó của từng site thay
vì luôn dùng công cụ đắt nhất:

| Tier | Công cụ | Dùng khi | Chi phí |
|---|---|---|---|
| `tier1_http` | `httpx` + stealth headers | Probe trả 200 | Rẻ nhất |
| `tier2_reader` | Jina Reader | HTML rỗng (site JS-heavy) | Rẻ |
| `tier4_stealth_tls` | `curl_cffi` (giả TLS fingerprint Chrome) | Probe trả 403/503 (WAF) | Trung bình |
| `tier3_browser` | Playwright Chromium headless | Sau khi tier4 fail | Đắt nhất, giới hạn qua `BudgetManager` + `asyncio.Semaphore(2)` |

Adapter thành công với 1 domain được "nhớ" trong `blackbook.json` (TTL 7
ngày) để lần sau bỏ qua bước probe.

### 2.6. Resource budgeting & graceful stop
`core/budget_manager.py` áp trần cho số URL, số lượt gọi Gemini, token ước
tính, số lượt dùng browser mỗi chu kỳ. Pipeline tự dừng "graceful" ở mốc
thời gian nội bộ (mặc định 45 phút) trước khi GitHub Actions hard-kill ở
`timeout-minutes` — đảm bảo không mất state giữa chừng.

### 2.7. Domain ban & self-healing scraping
`domain_ban.py` tạm cấm domain lỗi liên tục (kèm subdomain-matching), tự
gỡ ban sau cooldown; `t0_search.py` có cơ chế fallback tuần tự qua nhiều
search engine nếu engine chính lỗi.

### 2.8. Multi-tier data normalization & dedup
`t3_normalize.py` (Gate 5, gồm Check F/D/G theo đúng thứ tự) chuẩn hóa và
lọc dữ liệu; `t4_deduplicate.py` khử trùng lặp kể cả **cross-visual_id**
(không chỉ trong cùng 1 record); `t4_5_library_distill.py` định tuyến dữ
liệu đã harvest vào các distiller theo loại thực thể
(`CreatureDistiller`, `FloraDistiller`, `CostumeDistiller`...) trước khi ghi
vào collection `lib_entities`.

### 2.9. CI tối giản, chỉ chặn merge trên lỗi nghiêm trọng
`ci.yml` chỉ fail-build trên lỗi cú pháp/import thật sự (flake8
`E9,F63,F7,F82`) và 2 bộ test đã ổn định — các cảnh báo style
(unused import, line-too-long...) và các test TDD chưa hoàn thiện không
chặn merge, tránh làm nghẽn tốc độ phát triển đa-coder song song.

### 2.10. Chạy tiết kiệm hạn mức CI/CD miễn phí
`harvest.yml` không chạy nền liên tục mà chỉ theo cron thưa (1 lần/ngày)
hoặc thủ công, có `concurrency` group chống chạy chồng — để không vượt hạn
mức 2000 phút/tháng của GitHub Actions Free Tier.

---

## 3. Mục đích của repo

Repo này là **"Repo 1"** trong hệ sinh thái nhiều-repo phục vụ dự án
**World Simulator (Chimera)** — một hệ thống mô phỏng thế giới hư cấu kết
hợp ngẫu nhiên có trọng số với LLM để sinh nội dung tường thuật/kịch bản.

Vai trò cụ thể của Repo 1:

- **Thu thập tự động** dữ liệu tham khảo hình ảnh/thiết kế (concept art,
  nhân vật, sinh vật, kiến trúc, trang phục, công nghệ...) từ nhiều nguồn
  web, không cần can thiệp thủ công.
- **Chọn lọc và chuẩn hóa** dữ liệu thô thành các bản ghi có cấu trúc thống
  nhất (theo `schemas/master_schema_2_0.py`, `visual_blueprint_3_0.py`),
  đảm bảo chất lượng qua nhiều lớp gate (Quality Scorer, Global Rule
  Library, dedup).
- **Xây dựng "Global Rule Library" và `lib_entities`** — một kho tri thức
  thiết kế thị giác đã được phân loại theo thực thể (sinh vật, thực vật,
  trang phục...) — làm nguồn tham chiếu nhất quán, tái sử dụng được cho các
  hệ thống sinh nội dung downstream (thay vì mỗi lần LLM tự "bịa" thiết kế
  không nhất quán giữa các lần chạy).
- **Vận hành bền vững trong giới hạn tài nguyên miễn phí**: toàn bộ pipeline
  được thiết kế để chạy định kỳ trên GitHub Actions Free Tier, với budget
  cứng cho request/token/thời gian, tránh vượt hạn mức hoặc bị chặn IP bởi
  các site nguồn.

Nói ngắn gọn: Repo 1 là **"con mắt thu thập dữ liệu hình ảnh"** của toàn bộ
hệ sinh thái Chimera — biến internet công khai thành một thư viện thiết kế
thị giác có cấu trúc, sạch, và đáng tin cậy để các repo khác (sinh video,
mô phỏng thế giới) dùng làm nền tảng nhất quán về mặt hình ảnh.
