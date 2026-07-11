"""
builders/visual_prompt_builder.py
====================================
Class thuần Python để tự động ghép prompt từ Visual Blueprint 3.0.

[CX] Class này KHÔNG được gọi LLM. Toàn bộ là string assembly thuần Python
trên dữ liệu đã có sẵn trong blueprint. Phải được import và tái sử dụng bởi
cả `t3_normalize.py` (để validate) và bất kỳ module Repo 4 nào cần build
prompt — không được duplicate logic này ở nơi khác.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class VisualPromptBuilder:
    """Ghép prompt hình ảnh từ một Visual Blueprint 3.0 (dict thô hoặc đã
    validate bằng Pydantic + `.model_dump()`)."""

    def __init__(self, blueprint: dict) -> None:
        self.blueprint = blueprint
        self.validate_blueprint()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_blueprint(self) -> None:
        rules = self.blueprint.get("validation_rules", {}) or {}
        required = rules.get("required_fields", []) or []
        for field in required:
            if not self._get_nested_field(field):
                raise ValueError(f"Missing required field: {field}")

    def _get_nested_field(self, field_path: str) -> Optional[Any]:
        """Lấy giá trị từ nested dict bằng dot notation. Trả None nếu
        không tồn tại hoặc falsy ở bất kỳ bước nào trên đường đi."""
        keys = field_path.split(".")
        value: Any = self.blueprint
        for key in keys:
            if not isinstance(value, dict):
                return None
            value = value.get(key, {})
        return value if value else None

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------
    def build_prompt(
        self,
        view_type: str = "full_character",
        custom_pose: Optional[str] = None,
        custom_emotion: Optional[str] = None,
        override_environment: Optional[dict] = None,
    ) -> Tuple[str, str]:
        """Trả về (positive_prompt, negative_prompt)."""
        pre_built = self.blueprint.get("pre_built_prompts", {}) or {}

        if view_type in pre_built:
            base_prompt = pre_built[view_type]
        else:
            base_prompt = self._assemble_prompt_from_fragments()

        if custom_pose:
            base_prompt += f", {custom_pose}"
        if custom_emotion:
            base_prompt += f", {custom_emotion}"
        if override_environment:
            fragment = override_environment.get("prompt_fragment", "")
            if fragment:
                base_prompt += f", {fragment}"

        multi_view = self.blueprint.get("multi_view_references", {}) or {}
        # [SPEC_FIX_P1] multi_view_references giờ LUÔN có đủ 5 key cố định
        # (front_view/side_view/back_view/close_up_face/environment_context),
        # giá trị = None nếu view đó chưa có — khác với trước đây (key vắng
        # mặt hoàn toàn nếu thiếu). Phải check truthy value, không chỉ check
        # `in`, nếu không sẽ gọi .get() trên None và crash.
        view_entry = multi_view.get(view_type)
        if view_entry:
            suffix = view_entry.get("prompt_suffix", "")
            if suffix:
                base_prompt += f", {suffix}"

        negative_prompt = pre_built.get("negative_prompt", "")

        self._validate_prompt_length(base_prompt)

        return base_prompt, negative_prompt

    def _assemble_prompt_from_fragments(self) -> str:
        rules = self.blueprint.get("prompt_assembly_rules", {}) or {}
        priority_order = rules.get("order_priority", []) or []
        separator = rules.get("separator", ", ")
        weight_format = rules.get("weight_format", "({text}:{weight})")
        conditional = rules.get("conditional_inclusion", {}) or {}

        fragments = []
        for field_path in priority_order:
            if field_path in conditional:
                if not self._check_condition(conditional[field_path]):
                    continue

            field_data = self._get_nested_field(field_path)
            if isinstance(field_data, dict) and "prompt_fragment" in field_data:
                fragment = field_data["prompt_fragment"]
                weight = field_data.get("weight", 1.0)
                if weight != 1.0:
                    fragment = weight_format.format(text=fragment, weight=weight)
                fragments.append(fragment)

        return separator.join(fragments)

    def _check_condition(self, condition: str) -> bool:
        """Parse chuỗi dạng 'if enabled == true' -> so sánh với
        _get_nested_field tương ứng."""
        if "==" not in condition:
            return True

        field, value = condition.split("==", 1)
        field = field.strip().removeprefix("if ").strip()
        value = value.strip().lower()

        field_data = self._get_nested_field(field)

        if value == "true":
            return field_data is True
        if value == "false":
            return field_data is False
        return str(field_data) == value

    def _validate_prompt_length(self, prompt: str) -> None:
        rules = self.blueprint.get("validation_rules", {}) or {}
        min_len = rules.get("min_prompt_length", 150)
        max_len = rules.get("max_prompt_length", 700)

        if len(prompt) < min_len:
            raise ValueError(f"Prompt too short: {len(prompt)} < {min_len}")
        if len(prompt) > max_len:
            raise ValueError(f"Prompt too long: {len(prompt)} > {max_len}")

    def generate_image_request(self, view_type: str = "full_character", **kwargs) -> dict:
        positive_prompt, negative_prompt = self.build_prompt(view_type, **kwargs)
        metadata = self.blueprint.get("prompt_metadata", {}) or {}

        resolution = metadata.get("resolution", "1024x1536")
        try:
            width_str, height_str = resolution.lower().split("x")
            width, height = int(width_str), int(height_str)
        except (ValueError, AttributeError):
            width, height = 1024, 1536

        return {
            "prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": metadata.get("base_seed") if metadata.get("seed_lock", False) else None,
            "steps": 30,
            "cfg_scale": 7.5,
            "sampler": "DPM++ 2M Karras",
        }
