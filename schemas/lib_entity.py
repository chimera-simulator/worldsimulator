"""
schemas/lib_entity.py — Pydantic model cho collection `lib_entities`
======================================================================
Theo đúng convention của `schemas/visual_blueprint_3_0.py`:
- Comment tiếng Việt giải thích lý do thiết kế.
- `payload: Dict` tự do cho phần biến thiên theo `library_type` — KHÔNG
  liệt kê phẳng 10 bộ field riêng trong cùng 1 model vì Pydantic không
  thể có nhiều tập field khác nhau theo discriminator mà vẫn giữ clean
  additionalProperties-free behavior.
- KHÔNG raise cứng ở construction time — mọi validate nghiệp vụ
  (LIBRARY_REQUIRED_FIELDS) nằm ở Gate 6.5 (t4_5_library_distill.py),
  đúng nguyên tắc phân tách: Schema = kiểu dữ liệu, Gate = quyết định
  nghiệp vụ.

Khi ghi vào MongoDB, t4_5_library_distill.py FLATTEN `payload` ra cùng
cấp với `library_type`/`entity_id` trước khi dict() — document Mongo sẽ
có cấu trúc phẳng đúng như ví dụ mục 5 tài liệu Architect, trong khi
in-memory vẫn dùng `payload: Dict` để giữ Pydantic clean.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# LƯU Ý: "rule" KHÔNG nằm trong LibraryType — rule_library.py + collection
# world_rule_library đã tồn tại riêng (Global Rule Library), Gate 6.5
# KHÔNG được ghi đè hay ghi trùng vào đó (xem SPEC_GATE_6_5 mục 10).
LibraryType = Literal[
    "species",
    "creature",
    "flora",
    "architecture",
    "costume",
    "technology",
    "culture",
    "occupation",
    "visual_style",
    "character_blueprint",
]

# "complete" = tất cả required fields đã có giá trị.
# "incomplete" = vẫn còn field thiếu — vẫn ghi vào lib_entities để track
# pending fields; Repo 3/4 lọc bỏ khi đọc. Khác với Gate 6 hiện tại của
# fiction_knowledge (reject cứng), Gate 6.5 cho phép ghi incomplete theo
# triết lý gap_filling_status §28.4: không ép hoàn thiện ngay.
LibEntityStatus = Literal["complete", "incomplete"]


class SourceProvenance(BaseModel):
    """Truy vết nguồn gốc của lib_record về tới visual_blueprint_collection
    và fiction_knowledge — bắt buộc để debug (§105 Observability) và để
    lần harvest sau có thể merge/update thay vì tạo bản ghi trùng."""

    visual_blueprint_ref: Optional[str] = None
    schema_record_refs: List[str] = Field(default_factory=list)
    distilled_by: str = "t4_5_library_distill"
    distilled_at: str = ""
    llm_structuring_used: bool = False
    ip_filter_status: str = "unverified"


class LibConsistencyLock(BaseModel):
    """Copy nguyên từ Visual Blueprint 3.0 — KHÔNG tính lại ở đây để
    tránh 2 nguồn sự thật lệch nhau (xem mục 5 tài liệu Architect)."""

    locked_fields: List[str] = Field(default_factory=list)
    variable_fields: List[str] = Field(default_factory=list)


class LibEntity(BaseModel):
    """Model chính cho 1 document trong `lib_entities`.

    `payload` gộp toàn bộ field biến thiên theo library_type (physical,
    clothing, style, material, ...). Khi serialize ra Mongo dict, caller
    phải flatten payload ra cùng cấp — xem t4_5_library_distill.py hàm
    _flatten_lib_record().
    """

    library_type: LibraryType
    entity_id: str
    status: LibEntityStatus = "incomplete"

    # Payload chính: Dict tự do, t4_5_library_distill.py chịu trách nhiệm
    # điền đúng field theo LIBRARY_REQUIRED_FIELDS + extract_from_blueprint().
    payload: Dict = Field(default_factory=dict)

    # Field prompt làm sẵn cho Repo 4 — kế thừa trực tiếp từ
    # pre_built_prompts của Visual Blueprint 3.0, đọc thẳng, không cần ghép.
    prompt_keywords: str = ""
    negative_prompt: str = ""

    source_provenance: SourceProvenance = Field(default_factory=SourceProvenance)

    # MỚI — Gap B: bản copy nguyên vẹn schema_record["provenance_and_metadata"]
    # tại thời điểm distill. Kiểu Dict tự do (KHÔNG tái dùng ProvenanceAndMetadata
    # của Master Schema) vì đây là archival copy, không phải validate lại.
    # Luôn là dict (rỗng {} nếu schema_record=None hoặc thiếu key) — KHÔNG bao
    # giờ None/absent, để Repo 3/4 đọc field với shape ổn định.
    origin_provenance: Dict = Field(default_factory=dict)

    consistency_lock: LibConsistencyLock = Field(default_factory=LibConsistencyLock)

    missing_required_fields: List[str] = Field(default_factory=list)
    schema_version: str = "lib_1.0"
