"""
schemas/visual_blueprint_3_0.py — Pydantic model cho Visual Blueprint 3.0
============================================================================
`character_blueprint`, `clothing_and_gear`, `prompt_assembly_rules` để dạng
Dict tự do (không ép full sub-model) vì cấu trúc nội bộ thay đổi theo
`entity_type` — nhưng required_fields trong `validation_rules` PHẢI được
check ở t3_normalize.py bằng dot-path lookup, không dựa vào Pydantic tự
validate phần này.

[CẬP NHẬT — SPEC_FIX_P1_ARCHITECTURE, Vấn đề 2]
Trước đây file này có `model_validator(mode="after")` RAISE ValueError nếu
`multi_view_references` thiếu "front_view"/"side_view" -> object bị reject
ngay tại construction time, mâu thuẫn với Gate 5 / Check B ở t3_normalize.py
(vốn chỉ ĐÁNH CỜ thiếu view, không reject cứng, theo triết lý Visual-First:
cho vào DB trước, điền dần sau — mục 28.4 tài liệu gốc).

Nguyên tắc phân tách trách nhiệm (bắt buộc tuân thủ):
- Schema ở file này CHỈ đảm bảo đúng KIỂU DỮ LIỆU (type/shape).
- Quyết định NGHIỆP VỤ (thiếu view có chấp nhận được không) thuộc về Gate 5
  (t3_normalize.py) — nơi DUY NHẤT được quyết định điều này.
- Do đó: đã XOÁ model_validator raise cứng, `front_view`/`side_view` (và các
  view khác) chuyển thành Optional — không còn required ở schema-level.
- Thêm 2 field cờ `needs_more_views` / `missing_view_fields` để Gate 5 mang
  thông tin xuống hạ lưu thay vì raise exception.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PromptFragment(BaseModel):
    prompt_fragment: str
    negative_fragment: Optional[str] = None
    weight: float = 1.0
    required: bool = False


class PromptMetadata(BaseModel):
    style_preset: str
    quality_tags: str
    resolution: str
    aspect_ratio: str
    seed_lock: bool = True
    base_seed: int


class ViewReference(BaseModel):
    """Trước đây tên là `MultiViewEntry`. Đổi tên theo spec fix để rõ nghĩa
    hơn: đây là 1 tham chiếu view đơn lẻ (front/side/back/...), không phải
    toàn bộ tập multi-view."""
    image_url: str = ""
    prompt_suffix: str = ""
    weight_modifier: float = 1.0


class MultiViewReferences(BaseModel):
    """[CẬP NHẬT — Vấn đề 2] Chuyển từ `Dict[str, MultiViewEntry]` tự do
    sang model có field tường minh, mỗi view là Optional — KHÔNG còn
    model_validator raise cứng ở đây. Việc "thiếu view có chấp nhận được
    không" là quyết định NGHIỆP VỤ, thuộc về Gate 5 (t3_normalize.py),
    không phải quyết định SCHEMA."""
    front_view: Optional[ViewReference] = None
    side_view: Optional[ViewReference] = None
    back_view: Optional[ViewReference] = None
    close_up_face: Optional[ViewReference] = None
    environment_context: Optional[ViewReference] = None


class ConsistencyLock(BaseModel):
    locked: bool = False
    locked_fields: List[str] = Field(default_factory=list)
    variable_fields: List[str] = Field(default_factory=list)


class ValidationRules(BaseModel):
    required_fields: List[str] = Field(default_factory=list)
    min_prompt_length: int = 150
    max_prompt_length: int = 700
    forbidden_combinations: List[List[str]] = Field(default_factory=list)


class GapFillingStatus(BaseModel):
    biology_completed: bool = False
    culture_completed: bool = False
    pending_fields: List[str] = Field(default_factory=list)


class BlueprintMetadata(BaseModel):
    created_at: str = ""
    last_updated: str = ""
    source_provenance: List[dict] = Field(default_factory=list)
    gap_filling_status: GapFillingStatus = Field(default_factory=GapFillingStatus)


class VisualBlueprint30(BaseModel):
    visual_id: str
    entity_type: Literal[
        "species", "creature", "architecture", "planet_environment",
        "flora", "costume", "technology", "culture",
        "character_blueprint", "visual_style"
    ]
    version: Literal["3.0"] = "3.0"
    prompt_metadata: PromptMetadata
    character_blueprint: Dict = Field(default_factory=dict)
    clothing_and_gear: Dict = Field(default_factory=dict)
    multi_view_references: MultiViewReferences = Field(default_factory=MultiViewReferences)
    environment_blueprint: Optional[Dict] = None
    prompt_assembly_rules: Dict = Field(default_factory=dict)
    pre_built_prompts: Dict[str, str] = Field(default_factory=dict)
    consistency_lock: ConsistencyLock = Field(default_factory=ConsistencyLock)
    validation_rules: ValidationRules = Field(default_factory=ValidationRules)
    metadata: BlueprintMetadata = Field(default_factory=BlueprintMetadata)

    # [CẬP NHẬT — Vấn đề 2] Field cờ do Gate 5 (t3_normalize.py) set SAU khi
    # validate — mặc định False/rỗng khi mới tạo object. KHÔNG có logic nào
    # trong file này được phép tự set 2 field này; đây thuần là chỗ chứa dữ
    # liệu (data holder) để mang quyết định nghiệp vụ của Gate 5 xuống hạ lưu
    # (t4_deduplicate.py, t5_upload.py, Repo 4).
    needs_more_views: bool = False
    missing_view_fields: List[str] = Field(default_factory=list)

    # ĐÃ XOÁ: model_validator(mode="after") raise ValueError khi thiếu
    # front_view/side_view. Lý do xoá: xem docstring đầu file + Vấn đề 2
    # trong SPEC_FIX_P1_ARCHITECTURE.md. Mọi hard-reject nghiệp vụ dời hết
    # về Gate 5 (t3_normalize.py).
