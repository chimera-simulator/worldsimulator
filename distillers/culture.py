"""
distillers/culture.py — CultureDistiller (mục 23 tài liệu Architect)
=======================================================================
Văn hóa (ngôn ngữ, nghi lễ, ẩm thực, âm nhạc, lễ hội, luật lệ, phong tục)
là nhóm dữ liệu ÍT-VISUAL NHẤT trong toàn bộ hệ thống — Visual Blueprint
3.0 (character_blueprint / clothing_and_gear / environment_blueprint)
không có bất kỳ sub-key nào mô tả văn hóa (xem PHẦN 2, mục 23 "CULTURE
LIBRARY" trong tài liệu gốc — các trường Culture_ID chỉ LIÊN KẾT tới
hành tinh/chủng loài, không mang nội dung hình ảnh).

Do đó _extract_payload() ở đây gần như LUÔN trả {} (hoặc rất ít field) —
đây là hành vi ĐÚNG THIẾT KẾ, không phải lỗi. required_fields chỉ có
"prompt_keywords" (LIBRARY_REQUIRED_FIELDS["culture"] trong
library_routing.py) sẽ gần như luôn bị thiếu → kích hoạt LLM fallback
(structure_via_llm) đọc từ schema_record.form_2_civilization_layer.
culture_and_history (religion_and_belief, cultural_patterns,
language_patterns, ...) — đây là tầng Gap-Filling Station thật sự tạo
ra nội dung văn hóa, KHÔNG phải _extract_payload() trực tiếp.

⚠️ CẦN SẾP XÁC NHẬN:
1. Cơ chế linking culture_id ↔ planet_id/species_id: hiện KHÔNG có
   trường nào trong Visual Blueprint hay schema_record cung cấp liên
   kết này một cách tường minh — payload chỉ set culture_id nếu
   blueprint có visual_id tương ứng (dùng entity_id của doc làm gợi ý),
   nếu không sẽ để rỗng chờ Sếp quyết định convention linking.
2. required_fields = ["prompt_keywords"] có hợp lý không cho culture —
   văn hóa hiếm khi có prompt hình ảnh trực tiếp (nghi lễ/ẩm thực/luật
   lệ là khái niệm trừu tượng), nên "status=incomplete" có thể là trạng
   thái BÌNH THƯỜNG lâu dài cho phần lớn bản ghi culture, không phải
   dấu hiệu lỗi harvest. Cần review lại baseline này qua dry-run
   (đúng ghi chú mục 89 library_routing.py: "review lại nếu tỉ lệ
   incomplete > 50%").
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class CultureDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "culture"
    # Baseline theo LIBRARY_REQUIRED_FIELDS["culture"] — xem cảnh báo ở
    # docstring trên về việc field này có thể không phù hợp cho culture.
    required_fields: ClassVar[list] = ["prompt_keywords"]

    def _extract_payload(self, blueprint: dict) -> dict:
        payload: dict = {}
        if not blueprint:
            return payload

        # Visual Blueprint không có sub-key văn hóa — mọi field dưới đây
        # chỉ được set nếu (hiếm khi) nguồn harvest nhét thẳng field văn
        # hóa vào environment_blueprint (VD một vài nguồn worldbuilding
        # mô tả lễ hội gắn liền với môi trường). KHÔNG coi đây là nguồn
        # chính thức — nguồn chính thức là Gap-Filling LLM ở base.py.
        environment = blueprint.get("environment_blueprint") or {}

        language_pattern = environment.get("language_pattern") or ""
        if language_pattern:
            payload["language_pattern"] = language_pattern

        ritual_or_ceremony = environment.get("ritual_or_ceremony") or environment.get("ritual") or ""
        if ritual_or_ceremony:
            payload["ritual_or_ceremony"] = ritual_or_ceremony

        cuisine = environment.get("cuisine") or ""
        if cuisine:
            payload["cuisine"] = cuisine

        music = environment.get("music") or ""
        if music:
            payload["music"] = music

        festival = environment.get("festival") or ""
        if festival:
            payload["festival"] = festival

        law_or_custom = environment.get("law_or_custom") or environment.get("custom") or ""
        if law_or_custom:
            payload["law_or_custom"] = law_or_custom

        # culture_id — cơ chế linking planet_id/species_id CHƯA được xác
        # định (xem cảnh báo #1 trong docstring). Best-effort: nếu
        # environment có sẵn field liên kết, dùng nó; nếu không, để rỗng
        # thay vì tự bịa ra ID (đúng nguyên tắc "không tự sinh dữ liệu"
        # mục 60/103 tài liệu gốc).
        culture_id = environment.get("culture_id") or environment.get("planet_id") or ""
        if culture_id:
            payload["culture_id"] = culture_id

        # prompt_keywords (required) — hiếm khi có nguồn trực tiếp cho
        # culture; nếu environment không có field riêng, base.py sẽ tự
        # fallback đọc pre_built_prompts (dành cho nhân vật, thường KHÔNG
        # liên quan tới văn hóa) rồi cuối cùng dựa vào LLM fallback ở
        # bước 5 của base.distill() để điền thật.
        prompt_keywords = environment.get("prompt_keywords") or ""
        if prompt_keywords:
            payload["prompt_keywords"] = prompt_keywords

        return payload
