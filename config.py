"""
Config — Layer 0 (Nguồn khai báo Schema) — Repo 1 Visual-First Harvester
=========================================================================
File này CHỈ chứa data/constants tĩnh. KHÔNG import pymongo hay
google-generativeai ở đây (đó là việc của mongo_shared.py / summarizer.py).

Đây là file DUY NHẤT được phép chứa định nghĩa schema thô dạng dict.
Mọi agent khác (t0..t5, summarizer, builders) chỉ được IMPORT từ đây,
không copy-paste lại cấu trúc.
"""
from __future__ import annotations

import enum
import os
from typing import List, Literal, TypedDict


# =============================================================================
# MASTER SCHEMA 2.0 — khớp chính xác PHẦN 28.3 của World Simulator Pipeline doc
# =============================================================================
MASTER_SCHEMA_2_0: dict = {
    "schema_version": "2.0",
    "document_type": "worldbuilding_design_pattern",
    "form_1_planet_foundation": {
        "planet_identity": {
            "planet_type": "",
            "core_material": "",
            "physical_appearance": [],
            "terrain_patterns": [],
            "climate_patterns": [],
            "energy_sources": [],
            "natural_resources": [],
            "planetary_hazards": [],
            "planetary_phenomena": [],
        },
        "ecosystem_foundation": {
            "dominant_ecosystem": [],
            "dominant_life_material": "",
            "food_chain_patterns": [],
            "ecological_cycles": [],
            "environmental_adaptations": [],
        },
    },
    "form_2_civilization_layer": {
        "biology_and_behavior": {
            "species_morphology": [],
            "species_behavior": [],
        },
        "society_and_infrastructure": {
            "architecture_patterns": [],
            "transportation_patterns": [],
            "technology_patterns": [],
            "government_patterns": [],
            "economic_patterns": [],
            "military_patterns": [],
        },
        "culture_and_history": {
            "religion_and_belief": [],
            "cultural_patterns": [],
            "language_patterns": [],
            "art_patterns": [],
            "daily_life_patterns": [],
            "historical_patterns": [],
            "diplomatic_patterns": [],
        },
    },
    "provenance_and_metadata": {
        "target_form_field": "",
        "search_strategy_used": "",
        "extracted_from_domain": "",
        "ip_filter_status": "unverified",
        "original_ip_detected": [],
        "quality_gate_passed": False,
        "timestamp": "",
    },
}


# =============================================================================
# VISUAL BLUEPRINT 3.0 — khung mẫu rỗng, dùng làm base khi khởi tạo blueprint
# mới trong summarizer.py (Phase A). Copy khung rỗng từ §28.5.
# =============================================================================
VISUAL_BLUEPRINT_3_0_TEMPLATE: dict = {
    "visual_id": "",
    "entity_type": "",
    "version": "3.0",
    "prompt_metadata": {
        "style_preset": "",
        "quality_tags": "",
        "resolution": "",
        "aspect_ratio": "",
        "seed_lock": True,
        "base_seed": 0,
    },
    "character_blueprint": {},
    "clothing_and_gear": {},
    "multi_view_references": {},
    "environment_blueprint": None,
    "prompt_assembly_rules": {
        "order_priority": [],
        "separator": ", ",
        "weight_format": "({text}:{weight})",
        "negative_separator": ", ",
        "always_include": [],
        "conditional_inclusion": {},
    },
    "pre_built_prompts": {},
    "consistency_lock": {
        "locked": False,
        "locked_fields": [],
        "variable_fields": [],
    },
    "validation_rules": {
        "required_fields": [],
        "min_prompt_length": 150,
        "max_prompt_length": 700,
        "forbidden_combinations": [],
    },
    "metadata": {
        "created_at": "",
        "last_updated": "",
        "source_provenance": [],
        "gap_filling_status": {
            "biology_completed": False,
            "culture_completed": False,
            "pending_fields": [],
        },
    },
}


# =============================================================================
# VISUAL KEYWORD FILTER — thay thế hoàn toàn SCIENCE_ONTOLOGY_KEYWORDS.
# Biến SCIENCE_ONTOLOGY_KEYWORDS đã bị XÓA khỏi file này (không giữ alias).
# =============================================================================
VISUAL_KEYWORD_FILTER: List[str] = [
    "texture", "morphology", "surface", "structure", "glowing", "layout",
    "silhouette", "pattern", "material", "pigmentation", "translucent",
    "bioluminescent", "iridescent", "geometry", "shape", "form factor",
    "coloration", "camouflage", "ornamentation", "carapace", "plating",
    "musculature", "skeletal structure", "appendage", "proportion",
    "concept art", "character design", "creature design", "environment art",
    "reference sheet", "turnaround", "front view", "side view", "close-up",
    "architecture style", "facade", "ornament", "roofline", "spire",
    "foliage", "canopy", "bark texture", "petal", "coloring", "hue",
]


class VisualSourcePriority(enum.IntEnum):
    """Dùng bởi t1_classify.py để sort/threshold."""
    VISUAL_RICH = 3
    VISUAL_MODERATE = 2
    TEXT_ONLY = 1


# =============================================================================
# MONGO TARGET COLLECTIONS — KHÔNG còn key "world_rules" cũ (deprecated khỏi
# phạm vi Repo 1 theo nguyên tắc toàn cục §0).
#
# "world_rule_library" là collection MỚI, khác tên và khác bản chất so với
# "world_rules" cũ đã xoá: đây là collection data-driven cho Global Rule
# Library (Check G / Gate 5), có schema riêng với "rule_type"/"severity"/
# "active" (xem rule_library.py) — KHÔNG phải hồi sinh code "world_rules" cũ.
# =============================================================================
MONGO_TARGET_COLLECTIONS: dict = {
    "fiction_knowledge": "fiction_knowledge",
    "visual_blueprint_collection": "visual_blueprint_collection",
    "world_rule_library": "world_rule_library",
    "lib_entities": "lib_entities",                     # [MỚI — Gate 6.5] Library Layer cho §16-27
}


QueryVariant = Literal["Concept", "Design", "Description", "Reference", "Variant"]


class SourceType(TypedDict, total=False):
    pass


def _flatten_leaf_fields(node: dict, prefix: str = "") -> List[str]:
    """Duyệt đệ quy 1 sub-dict của MASTER_SCHEMA_2_0, trả list dot-path
    của các field lá (leaf = giá trị không phải dict lồng thêm)."""
    leaves: List[str] = []
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            leaves.extend(_flatten_leaf_fields(value, path))
        else:
            leaves.append(path)
    return leaves


def get_form_fields(
    form_name: Literal["form_1_planet_foundation", "form_2_civilization_layer"]
) -> List[str]:
    """Trả về flatten list tên các field lá (leaf fields) của 1 form trong
    MASTER_SCHEMA_2_0, dạng dot-notation đầy đủ (bao gồm cả prefix form_name),
    ví dụ: "form_1_planet_foundation.planet_identity.terrain_patterns".

    Dùng bởi t0_search.py để lặp sinh query — KHÔNG hardcode tên field ở
    nơi gọi.
    """
    form_node = MASTER_SCHEMA_2_0.get(form_name)
    if not isinstance(form_node, dict):
        return []
    return _flatten_leaf_fields(form_node, prefix=form_name)


# =============================================================================
# GEMINI — round robin API keys (Free Tier). Đọc từ env var
# GEMINI_MODEL_NO_1..GEMINI_MODEL_NO_7.
# =============================================================================
def load_gemini_api_keys() -> List[str]:
    """Đọc tối đa 7 API key Gemini Free Tier từ env var
    GEMINI_MODEL_NO_1..GEMINI_MODEL_NO_7.
    Bỏ qua key rỗng. Trả về list rỗng nếu không có key nào (pipeline vẫn phải
    chạy được để chạy unit test / các bước không dùng LLM)."""
    keys = []
    for i in range(1, 8):
        key = os.getenv(f"GEMINI_MODEL_NO_{i}", "").strip()
        if key:
            keys.append(key)
    return keys


GEMINI_API_KEYS: List[str] = load_gemini_api_keys()
GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

# Ngưỡng dùng bởi t1_classify.py (Gate 1)
VISUAL_SCORE_THRESHOLD: float = float(os.getenv("VISUAL_SCORE_THRESHOLD", "1.5"))

# Ngưỡng mật độ từ khóa thị giác dùng bởi t2_scrape.py (Gate 2)
VISUAL_KEYWORD_DENSITY_THRESHOLD: float = float(
    os.getenv("VISUAL_KEYWORD_DENSITY_THRESHOLD", "0.01")
)

# Ngưỡng similarity dùng bởi t4_deduplicate.py
DEDUP_SIMILARITY_THRESHOLD: float = float(os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.85"))

# =============================================================================
# [CẬP NHẬT — SPEC_FIX_P1_ARCHITECTURE] Vấn đề 1 & 2
# =============================================================================
# Đường dẫn state file dùng chung DUY NHẤT giữa t0_search.py và t2_scrape.py.
# main.py là nơi DUY NHẤT load/save file này (xem load_blackbook/save_blackbook
# trong main.py) — t0/t2 chỉ nhận blackbook qua tham số (dependency injection),
# không tự mở file.
BLACKBOOK_PATH: str = os.getenv("BLACKBOOK_PATH", "blackbook.json")

# Danh sách view tối thiểu bắt buộc để 1 Visual Blueprint được coi là "đầy đủ"
# về mặt hình ảnh — cấu hình được, KHÔNG hardcode trong logic Gate 5.
# Dùng bởi t3_normalize.py (Check B / run_gate_5).
MIN_REQUIRED_VIEWS: list[str] = ["front_view", "side_view"]

MONGODB_URI: str = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "world_simulator")

# =============================================================================
# QUALITY SCORER — dùng bởi core/quality_scorer.py (Gate 5, run_gate_5()).
# Tổng 4 trọng số PHẢI = 100 — có unit test riêng assert việc này
# (tests/test_quality_scorer.py::test_weights_sum_to_100).
# =============================================================================
QUALITY_SCORE_WEIGHTS: dict = {
    "view_completeness": 30,
    "ip_cleanliness": 20,
    "prompt_depth": 20,
    "schema_completeness": 30,
}

# 5 slot view tối đa có thể có — KHÁC MIN_REQUIRED_VIEWS (dòng 251, đó là
# ngưỡng PASS tối thiểu của Check B). Đây là mẫu số đầy đủ để tính điểm,
# phải khớp đúng 5 key cố định của multi_view_references (xem
# schemas/visual_blueprint_3_0.py — ViewReference).
ALL_VIEW_SLOTS: list[str] = [
    "front_view", "side_view", "back_view",
    "close_up_face", "environment_context",
]

IP_CLEANLINESS_SCORE_MAP: dict = {
    "cleaned_no_ip_detected": 20,
    "cleaned_but_ip_found": 10,
    "unverified": 5,
    "failed": 0,
}

# (min, max, điểm) — dải điểm graduated theo độ dài pre_built_prompts.full_character
# SAU KHI Check D (t3_normalize.py, dòng ~296-312) đã tự truncate nếu quá dài.
PROMPT_DEPTH_BANDS: list[tuple[int, int, int]] = [
    (0, 150, 0),
    (150, 200, 10),
    (200, 10**9, 20),
]

QUALITY_SCORE_PASS_THRESHOLD: int = 60

