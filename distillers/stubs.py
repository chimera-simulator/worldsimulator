"""
distillers/stubs.py — Stub Distillers (chứng minh kiến trúc mở rộng)
=======================================================================
2 class rỗng, chỉ để chứng minh: thêm 1 library_type mới = thêm 1 file +
1 dòng register() trong distillers/registry.py, KHÔNG cần sửa
t4_5_library_distill.py hay DistillerRegistry.

CreatureDistiller: "creature" ĐÃ là 1 LibraryType hợp lệ (khác species dù
cùng đọc character_blueprint — xem LIBRARY_REQUIRED_FIELDS["creature"] =
["prompt_keywords"], không bắt buộc skin_color như species vì creature có
thể phi sinh học/không có màu da rõ ràng). Stub này CHƯA điền logic thật
— khi Sếp duyệt, _extract_payload() sẽ tái dùng phần lớn logic của
SpeciesDistiller (character_blueprint) cộng thêm xử lý additional_features
đặc thù creature (chimera parts, non-standard anatomy).

PlanetDistiller: đăng ký dưới "planet_environment" nhưng KHÔNG kích hoạt
được qua route_library_type() hiện tại (xem ghi chú trong registry.py) —
thuần tuý minh hoạ kiến trúc, chờ quyết định bổ sung library_type.
"""
from __future__ import annotations

from typing import ClassVar

from distillers.base import BaseLibraryDistiller


class CreatureDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "creature"
    required_fields: ClassVar[list] = ["prompt_keywords"]

    def _extract_payload(self, blueprint: dict) -> dict:
        # TODO(Sếp duyệt): điền logic thật — dự kiến tái dùng phần lớn
        # SpeciesDistiller._extract_payload() (character_blueprint) +
        # xử lý riêng additional_features cho creature phi tiêu chuẩn.
        pass
        return {}


class PlanetDistiller(BaseLibraryDistiller):
    library_type: ClassVar[str] = "planet_environment"
    required_fields: ClassVar[list] = ["prompt_keywords"]

    def _extract_payload(self, blueprint: dict) -> dict:
        # TODO(Sếp duyệt): chưa có library_type "planet" trong LibraryType
        # Literal (schemas/lib_entity.py) lẫn library_routing.py — stub này
        # không thể chạy thật cho tới khi bổ sung 2 chỗ đó.
        pass
        return {}
