"""
distillers/character_blueprint.py — CharacterBlueprintDistiller (mục 26)
============================================================================
Khác biệt cốt lõi với SpeciesDistiller: SpeciesDistiller trích PROMPT
FRAGMENT (câu mô tả tự do) để LLM/Repo 4 dùng trực tiếp trong prompt.
CharacterBlueprintDistiller trích ID THAM CHIẾU từng bộ phận (mục 26 —
"Character Blueprint Library... mỗi Blueprint mô tả đầy đủ DNA hình ảnh
của một nhân vật... Prompt hình ảnh sau này chỉ việc GHÉP CÁC ID thay
vì để AI sáng tạo lại khuôn mặt ở mỗi tập") — mục đích là để Repo 4
LẮP RÁP (assembly), không "nghĩ lại" (regenerate) từng bộ phận.

Nguồn: blueprint.character_blueprint (physical_attributes, facial_features,
hair_and_head, limbs, additional_features) + blueprint.clothing_and_gear
(cho clothes_id/accessory_id) + blueprint.consistency_lock (đã được
base.distill() copy nguyên vào lib_entity.consistency_lock — KHÔNG lặp
lại ở đây, _extract_payload() chỉ lo phần payload).

⚠️ VẤN ĐỀ ID CHƯA CÓ NGUỒN ỔN ĐỊNH:
Visual Blueprint 3.0 mẫu (mục 28.5 tài liệu gốc) không lưu ID rời cho
từng bộ phận (head_id, hair_id, eye_id...) — chỉ có prompt_fragment mô
tả tự do. _extract_payload() KHÔNG được truyền entity_id/visual_id (chữ
ký cố định `_extract_payload(self, blueprint: dict)` theo đúng convention
BaseLibraryDistiller — xem distillers/base.py, entity_id chỉ được tính ở
tầng distill() và không truyền xuống payload extraction để giữ tách biệt
trách nhiệm).　Do đó, để không tự bịa ID (vi phạm nguyên tắc "Repo 1
không tự sáng tạo" §60/103 tài liệu gốc), chiến lược tạm thời là:
  - Nếu nguồn harvest đã có sẵn field "*_id" (VD "head_id"), dùng thẳng.
  - Nếu KHÔNG có, suy ra một ID tạm ổn định bằng convention
    f"{PART}_{slug(prompt_fragment)}" (deterministic theo nội dung, không
    random) — ID này CHƯA gắn với entity_id thật của nhân vật, chỉ đóng
    vai trò placeholder nhất quán cho tới khi Sếp quyết định cơ chế sinh
    ID chính thức (VD f"{entity_id}_HEAD" như gợi ý trong SPEC — cần
    entity_id được bơm vào từ tầng gọi cao hơn, ngoài phạm vi
    _extract_payload() hiện tại).
  - Nếu blueprint hoàn toàn không có dữ liệu cho 1 bộ phận → None
    (KHÔNG bịa, KHÔNG crash).
"""
from __future__ import annotations

import hashlib
import re
from typing import ClassVar, Optional

from distillers.base import BaseLibraryDistiller


def _slug(text: str, length: int = 8) -> str:
    """Tạo suffix ngắn, ổn định (deterministic) từ 1 chuỗi mô tả, dùng
    làm phần đuôi của ID tạm khi nguồn không có ID rời sẵn. KHÔNG dùng
    random — cùng input luôn ra cùng output (idempotent, giống tinh
    thần generate_entity_id() trong t4_5_library_distill.py)."""
    if not text:
        return "unknown"
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:length]


class CharacterBlueprintDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "character_blueprint"
    # Bám đúng LIBRARY_REQUIRED_FIELDS["character_blueprint"] trong
    # library_routing.py — baseline tối thiểu, chưa có đặc tả field bắt
    # buộc riêng (ID từng bộ phận đều best-effort, không bắt buộc).
    required_fields: ClassVar[list] = ["prompt_keywords"]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}
        if not blueprint:
            return payload

        character = blueprint.get("character_blueprint") or {}
        physical = character.get("physical_attributes") or {}
        facial = character.get("facial_features") or {}
        hair_and_head = character.get("hair_and_head") or {}
        limbs = character.get("limbs") or {}
        additional = character.get("additional_features") or {}
        clothing = blueprint.get("clothing_and_gear") or {}

        skin = physical.get("skin") or {}
        glow = physical.get("glow_effects") or {}

        def part_id(prefix: str, node: Optional[dict], explicit_key: str = "id") -> Optional[str]:
            """Lấy ID rời có sẵn nếu có, nếu không suy ra ID tạm ổn định
            từ prompt_fragment của node đó. Trả None nếu node rỗng hoàn
            toàn (không có gì để suy luận) — an toàn, không crash."""
            if not isinstance(node, dict) or not node:
                return None
            explicit = node.get(explicit_key) or node.get(f"{prefix.lower()}_id")
            if explicit:
                return str(explicit)
            frag = node.get("prompt_fragment") or ""
            if not frag:
                return None
            return f"{prefix}_{_slug(frag)}"

        # head_id — không có node "head" riêng trong mẫu Visual Blueprint
        # 3.0 (facial_features.face_shape là gần nhất) — dùng face_shape
        # làm nguồn suy ID head tạm thời.
        head_id = part_id("HEAD", facial.get("face_shape"))
        if head_id:
            payload["head_id"] = head_id

        # hair_id — từ hair_and_head.alternative (mẫu Visual Blueprint
        # dùng "alternative" cho trường hợp loài không có tóc theo nghĩa
        # thông thường, VD sensory tendrils) hoặc field "hair" trực tiếp
        # nếu nguồn khác có cấu trúc chuẩn hơn.
        hair_node = hair_and_head.get("alternative") or hair_and_head
        hair_id = part_id("HAIR", hair_node if isinstance(hair_node, dict) else None)
        if hair_id:
            payload["hair_id"] = hair_id

        # eye_id — facial_features.eyes (mẫu có thể "present": false, vẫn
        # có prompt_fragment mô tả "no eyes" — vẫn tạo ID hợp lệ vì đó
        # cũng là một đặc điểm nhận dạng cố định của loài).
        eye_id = part_id("EYE", facial.get("eyes"))
        if eye_id:
            payload["eye_id"] = eye_id

        # nose_id — không có trường "nose" riêng trong mẫu (loài không
        # có mũi theo nghĩa người) — thử field trực tiếp nếu có, nếu
        # không None (KHÔNG bịa ra mũi cho loài không có).
        nose_id = part_id("NOSE", facial.get("nose"))
        if nose_id:
            payload["nose_id"] = nose_id

        # mouth_id — facial_features.mouth
        mouth_id = part_id("MOUTH", facial.get("mouth"))
        if mouth_id:
            payload["mouth_id"] = mouth_id

        # ear_id — không có trong mẫu (thay bằng sensory_organs cho loài
        # phi nhân) — fallback sensory_organs nếu ear không tồn tại.
        ear_id = part_id("EAR", facial.get("ear")) or part_id(
            "EAR", facial.get("sensory_organs")
        )
        if ear_id:
            payload["ear_id"] = ear_id

        # horn_id — additional_features.horns
        horn_id = part_id("HORN", additional.get("horns"))
        if horn_id:
            payload["horn_id"] = horn_id

        # tail_id — additional_features.tail (không có trong mẫu cụ thể,
        # nhưng field được đặc tả trong SPEC — giữ lookup an toàn)
        tail_id = part_id("TAIL", additional.get("tail"))
        if tail_id:
            payload["tail_id"] = tail_id

        # body_id — physical_attributes.body_structure
        body_id = part_id("BODY", physical.get("body_structure"))
        if body_id:
            payload["body_id"] = body_id

        # skin_id — physical_attributes.skin (khác skin_color của
        # SpeciesDistiller: ở đây là ID tham chiếu, không phải giá trị
        # màu/prompt mô tả trực tiếp).
        skin_id = part_id("SKIN", skin)
        if skin_id:
            payload["skin_id"] = skin_id

        # clothes_id — từ clothing_and_gear.armor (mẫu Visual Blueprint
        # 3.0 dùng "armor" làm trang phục chính; nếu nguồn khác có field
        # "clothing"/"outfit" thì thử thêm để tương thích ngược).
        clothes_node = clothing.get("armor") or clothing.get("clothing") or clothing.get("outfit")
        clothes_id = part_id("CLOTHES", clothes_node if isinstance(clothes_node, dict) else None)
        if clothes_id:
            payload["clothes_id"] = clothes_id

        # accessory_id — clothing_and_gear.accessories là 1 LIST trong
        # mẫu (không phải dict đơn) — lấy phần tử đầu tiên làm accessory
        # chính; nếu list rỗng/không tồn tại → None.
        accessories = clothing.get("accessories") or []
        accessory_id = None
        if isinstance(accessories, list) and accessories:
            first = accessories[0]
            if isinstance(first, dict):
                accessory_id = part_id("ACCESSORY", first)
        elif isinstance(accessories, dict):
            accessory_id = part_id("ACCESSORY", accessories)
        if accessory_id:
            payload["accessory_id"] = accessory_id

        # color_palette_id — suy từ skin.base_color kết hợp
        # glow_effects.color (2 màu chủ đạo neo giữ bảng màu nhân vật),
        # theo đúng gợi ý SPEC "từ skin.base_color/glow_effects.color".
        base_color = skin.get("base_color") or ""
        glow_color = glow.get("color") or ""
        if base_color or glow_color:
            palette_seed = f"{base_color}_{glow_color}".strip("_")
            payload["color_palette_id"] = f"PALETTE_{_slug(palette_seed)}"

        # prompt_keywords (required) — không set tường minh ở đây; base.py
        # sẽ tự fallback đọc blueprint["pre_built_prompts"]["full_character"]
        # (đây LÀ prompt hợp lệ cho character_blueprint, khác với
        # technology/culture ở trên vốn không liên quan tới nhân vật).

        return payload
