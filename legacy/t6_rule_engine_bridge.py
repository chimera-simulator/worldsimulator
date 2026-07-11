# OUT_OF_SCOPE_REPO1 — không thuộc Design Pattern Harvester (t0..t5+summarizer).
# Giữ nguyên nội dung gốc, chỉ tách khỏi luồng import chính của main.py Repo 1.
# Xem SPEC_KY_THUAT_REPO1_V2.md mục 14 để biết lý do.

"""
t6_rule_engine_bridge.py — INTEGRATION GLUE (Repo 1)
=====================================================
Lớp kết nối do Tổng kỹ sư (Grand System Integrator) viết để nối liền:

    T5 (upload xong 1 keyword) -> T6 (world_forge, sinh Blueprint giả
    tưởng) -> rule_engine (kiểm tra tính nhất quán logic) -> kết thúc
    vòng lặp keyword.

TẠI SAO FILE NÀY TÁCH RIÊNG (không sửa thẳng t6_world_forge.py hay
rule_engine.py):

    t6_world_forge.py sinh Blueprint theo schema trong `schemas/` —
    tiếng Việt, mô tả hình tượng, dùng cho Repo 3/4 render nội dung.

    rule_engine.py kiểm tra tính nhất quán dựa trên MỘT bộ dataclass
    HOÀN TOÀN KHÁC (Planet/Species/Character/Environment định nghĩa
    ngay trong rule_engine.py), dùng vocabulary tiếng Anh có kiểm soát
    (climate/atmosphere/tech_level phải khớp đúng 1 danh sách cố định).

    Đây là 2 mảnh do 2 "kỹ sư" khác nhau viết, không hề dùng chung 1
    shape dữ liệu. Việc của Tổng kỹ sư là HÀN 2 mảnh này lại bằng 1 lớp
    chuyển đổi (adapter) — không phải sửa logic nội bộ của 1 trong 2 bên
    (đúng theo nguyên tắc "KHÔNG thay đổi logic bên trong các file của
    Claude 1,2,3,4,5").

GIỚI HẠN ĐÃ BIẾT — khai báo rõ ràng thay vì che giấu bằng dữ liệu giả:

  1. t6_world_forge.py hiện gọi `_call_llm_mock()` (STUB, chưa nối
     Gemini thật). Mọi field không suy luận được thuần Python từ vật lý
     (analyze_physics) sẽ là chuỗi placeholder "<LLM_PENDING:...>".
     Adapter dưới đây CHỈ map các field đã có giá trị THẬT (nhánh
     "planet", suy ra từ physics), phần còn lại dùng default trung tính
     an toàn (không tự kích hoạt lỗi giả của rule_engine). Khi Gemini
     thật thay _call_llm_mock, adapter này vẫn chạy đúng miễn
     `_forge_meta.inferred_physics` giữ nguyên shape.

  2. rule_engine.py chỉ có dataclass kiểm tra ĐẦY ĐỦ cho Planet và
     Species — không có Creature/Flora tương đương. Với target_type
     "species"/"creature"/"flora", build_template() của T6 hiện KHÔNG
     suy luận field sinh học nào từ physics thuần Python (chỉ gán
     "habitat" cho creature/flora) — nghĩa là validate ngay bây giờ chỉ
     là validate placeholder LLM_PENDING. Bridge này SKIP bước
     rule_engine cho các target_type đó và ghi log lý do rõ ràng, thay
     vì tự chế 15+ field sinh học (has_lungs, breathes, diet, body_temp_k...)
     không có căn cứ dữ liệu thật.

  3. Repo 1 hiện chưa có nguồn RuleLibrary (schemas.RuleLibrary) nào
     được persist (không có collection Mongo / file JSON cho việc này)
     — forge_blueprint() được gọi với rule_library=None. Khi Repo 1 có
     nguồn Rule Library thật, truyền vào đây sẽ tự động kích hoạt
     check_rule_conflicts() đã có sẵn bên trong t6_world_forge.py mà
     không cần sửa gì thêm ở bridge này.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .t6_world_forge import forge_blueprint
from .rule_engine import Planet as ValidatorPlanet
from .rule_engine import WorldValidator

logger = logging.getLogger("T6_BRIDGE")

_validator = WorldValidator()

# Chỉ 2 target schema này có adapter thật sang rule_engine hiện tại.
_VALIDATABLE_TARGET_TYPES = {"planet"}

# ---------------------------------------------------------------------------
# BƯỚC A — CHỌN TARGET SCHEMA (planet/species/creature/flora) CHO 1 RULE
# ---------------------------------------------------------------------------
#
# Không có bước phân loại nào upstream (T1-T5) gán sẵn "target schema" cho
# 1 rule khoa học — T1 chỉ gán "label" theo NGUỒN (vd "astronomy_rule_source",
# "biology_rule_source"), không phải theo LOẠI THỰC THỂ giả tưởng nó sẽ nuôi
# dưỡng. Đây là heuristic Python thuần (không LLM, đúng nguyên tắc T0-T5)
# để chọn tạm target_type — 1 bộ phân loại chuyên trách sau này có thể thay
# thế hàm này mà không cần đụng vào phần còn lại của bridge.

_FLORA_HINTS = (
    "plant", "flora", "tree", "forest", "algae", "fungus", "fungi",
    "moss", "photosynthesis", "spore", "leaf", "shrub",
)
_CREATURE_HINTS = (
    "animal", "creature", "predator", "prey", "fauna", "insect",
    "mount", "monster", "bird", "mammal", "reptile", "carnivore",
    "herbivore",
)
_PLANET_LABELS = {"astronomy_rule_source"}


def classify_target_type(rule: dict) -> str:
    """Heuristic Python thuần chọn target_type cho `forge_blueprint()`.

    Ưu tiên:
      1. Nhãn nguồn của T1 (`source_label`/`domain`) nếu chỉ rõ thiên văn
         -> "planet".
      2. Từ khóa sinh vật/thực vật trong summary/key_facts/matched_keywords
         -> "creature" / "flora".
      3. Mặc định "planet" (an toàn nhất: mọi rule khoa học — kể cả sinh
         học — đều ảnh hưởng tới môi trường hành tinh mẹ theo docstring
         t6_world_forge.py: "Species/Creature/Flora... vẫn chỉ là mapping
         trực tiếp" từ physics của hành tinh mẹ).
    """
    label = str(rule.get("source_label") or rule.get("domain") or "").lower()
    if label in _PLANET_LABELS:
        return "planet"

    corpus = " ".join(
        filter(
            None,
            [
                rule.get("summary", ""),
                rule.get("title", ""),
                " ".join(rule.get("matched_keywords", []) or []),
            ],
        )
    ).lower()

    if any(hint in corpus for hint in _FLORA_HINTS):
        return "flora"
    if any(hint in corpus for hint in _CREATURE_HINTS):
        return "creature"
    if "biology" in label:
        return "species"

    return "planet"


# ---------------------------------------------------------------------------
# BƯỚC B — ADAPTER: schemas.Planet (Blueprint dict) -> rule_engine.Planet
# ---------------------------------------------------------------------------

# canonical_tag (gán trong t6_world_forge.analyze_physics) -> nhãn khí quyển
# rule_engine.py chấp nhận (xem OXYGEN_BEARING_ATMOSPHERES / TOXIC_ATMOSPHERES).
_ATMOSPHERE_TAG_MAP = {
    "oxygen_rich": "oxygen_rich",
    "methane_rich": "methane",
    "toxic_sulfuric": "sulfur_dioxide",
    "thin_atmosphere": "low_oxygen",
    "vacuum": "vacuum",
}

# canonical_tag terrain -> (has_water, water_type) — chỉ 2 tag T6 thực sự
# gắn với sự hiện diện của nước; mọi terrain khác mặc định "không có nước
# lỏng" (an toàn: không kích hoạt R-P03/R-P04 sai).
_TERRAIN_WATER_MAP = {
    "frozen_ocean": (True, "ice"),
    "hydrothermal_vent": (True, "liquid"),
}

# (ngưỡng dưới °C, climate, biome) — Tổng kỹ sư tự suy ra trực tiếp từ số
# liệu độ C thô (không tái dùng nhãn tiếng Việt của t6_world_forge, vì
# rule_engine cần vocabulary tiếng Anh cố định, xem BIOME_CLIMATE_RULES).
_CLIMATE_THRESHOLDS = [
    (35.0, "desert", "desert"),
    (15.0, "temperate", "temperate_forest"),
    (0.0, "cold", "taiga"),
    (-30.0, "arctic", "arctic_tundra"),
    (float("-inf"), "frozen", "frozen_wasteland"),
]


def _parse_gravity_g(raw: Optional[str]) -> float:
    """'1.5g' -> 1.5. Mặc định 1.0g (trung tính) nếu thiếu/không parse được."""
    if not raw:
        return 1.0
    digits = "".join(ch for ch in str(raw) if ch.isdigit() or ch == ".")
    try:
        return float(digits) if digits else 1.0
    except ValueError:
        return 1.0


def _parse_avg_temp_c(raw: Optional[str]) -> Optional[float]:
    """'~-40C trung binh' -> -40.0."""
    if not raw:
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit() or ch in "-.")
    # digits có thể chứa nhiều dấu '-' nếu chuỗi lẫn ký tự khác; lấy phần
    # số hợp lệ đầu tiên bằng cách thử parse trực tiếp, fallback None.
    try:
        return float(digits)
    except ValueError:
        return None


def _climate_and_biome_for(avg_c: Optional[float]) -> tuple[str, str]:
    if avg_c is None:
        return "temperate", "temperate_forest"
    for threshold, climate, biome in _CLIMATE_THRESHOLDS:
        if avg_c >= threshold:
            return climate, biome
    return "temperate", "temperate_forest"  # unreachable, giữ để an toàn kiểu


def blueprint_to_validator_planet(blueprint: dict) -> ValidatorPlanet:
    """Chuyển 1 Blueprint Planet (output của `forge_blueprint`) sang
    `rule_engine.Planet` — chỉ dùng phần dữ liệu THẬT (physics đã suy luận
    ở T6 Bước 2), phần còn lại (chưa được LLM thật lấp) nhận default
    trung tính, không tự bịa dữ liệu sinh học/địa lý.
    """
    meta = blueprint.get("_forge_meta", {})
    physics = meta.get("inferred_physics", {}) or {}
    tags: dict[str, str] = physics.get("_tags", {}) or {}

    gravity = _parse_gravity_g(physics.get("gravity"))
    avg_temp_c = _parse_avg_temp_c(physics.get("temperature_range"))
    climate, biome = _climate_and_biome_for(avg_temp_c)

    if avg_temp_c is None:
        # Không suy luận được nhiệt độ thật -> dùng dải ôn hòa trung tính,
        # tránh việc rule_engine so sánh nhiệt độ với 0.0 mặc định của Python
        # (sẽ báo lỗi "nước lỏng không thể tồn tại" một cách giả tạo).
        temp_min_k, temp_max_k = 288.15, 298.15  # 15°C .. 25°C
    else:
        temp_min_k = temp_max_k = avg_temp_c + 273.15

    atmosphere_tag = tags.get("atmosphere")
    atmosphere = _ATMOSPHERE_TAG_MAP.get(atmosphere_tag, "earth_like")

    terrain_tag = tags.get("terrain")
    has_water, water_type = _TERRAIN_WATER_MAP.get(terrain_tag, (False, "none"))

    tech_level = blueprint.get("technology_level") or "primitive"
    if tech_level not in (
        "primitive", "ancient", "medieval", "industrial",
        "modern", "advanced", "stellar", "transcendent",
    ):
        tech_level = "primitive"

    def _clean_str(value: Any, default: str) -> str:
        if isinstance(value, str) and not value.startswith("<LLM_PENDING"):
            return value
        return default

    planet_id = str(
        blueprint.get("planet_id")
        or meta.get("source_content_hash")
        or "unknown_planet"
    )

    return ValidatorPlanet(
        planet_id=planet_id,
        name=_clean_str(blueprint.get("name"), planet_id),
        atmosphere=atmosphere,
        climate=climate,
        temperature_min_k=temp_min_k,
        temperature_max_k=temp_max_k,
        gravity=gravity,
        has_water=has_water,
        water_type=water_type,
        biomes=[biome],
        moon_count=int(physics.get("moon_count") or 0),
        has_magnetic_field=True,
        radiation_level="low",
        sky_color=_clean_str(blueprint.get("sky_color"), "unknown"),
        soil_color=_clean_str(blueprint.get("soil_color"), "unknown"),
        tech_level=tech_level,
        extra={"_source_forge_meta": meta},
    )


# ---------------------------------------------------------------------------
# BƯỚC C — ORCHESTRATOR: gọi từ main.py sau khi run_t5() hoàn thành
# ---------------------------------------------------------------------------

def forge_and_validate_uploaded_rules(
    uploaded_rules: list[dict], stats: dict
) -> None:
    """Xử lý các rule vừa upload (T5) qua T6 (world_forge) rồi qua
    rule_engine để kiểm tra tính nhất quán, trước khi main.py kết thúc 1
    vòng lặp keyword.

    Không raise — lỗi ở 1 rule không được chặn các rule còn lại hay làm
    sập vòng lặp keyword chính (đúng tinh thần "1 lỗi không chặn cả batch"
    đã áp dụng ở T5Upload.upload_rules).
    """
    stats.setdefault("blueprints_forged", 0)
    stats.setdefault("blueprints_validation_errors", 0)
    stats.setdefault("blueprints_validation_warnings", 0)
    stats.setdefault("blueprints_validation_skipped", 0)

    if not uploaded_rules:
        return

    logger.info("=" * 80)
    logger.info("🌍 T6 → rule_engine: Forge Blueprint & Validate")
    logger.info("=" * 80)

    for rule in uploaded_rules:
        target_type = classify_target_type(rule)
        try:
            blueprint = forge_blueprint(rule, target_type=target_type)
        except Exception as e:
            logger.warning(
                f"⚠️ T6 forge_blueprint lỗi cho rule "
                f"{rule.get('content_hash')}: {e}"
            )
            continue

        stats["blueprints_forged"] += 1

        if target_type not in _VALIDATABLE_TARGET_TYPES:
            stats["blueprints_validation_skipped"] += 1
            logger.info(
                f"   ⚪ Bỏ qua rule_engine cho target_type='{target_type}' "
                f"(content_hash={rule.get('content_hash')}): chưa có adapter "
                "dữ liệu sinh học thật cho Species/Creature/Flora ở mock-LLM "
                "stage hiện tại (xem giới hạn #2 trong docstring module)."
            )
            continue

        try:
            validator_planet = blueprint_to_validator_planet(blueprint)
            result = _validator.check_planet_internal_consistency(validator_planet)
        except Exception as e:
            logger.warning(
                f"⚠️ rule_engine validate lỗi cho rule "
                f"{rule.get('content_hash')}: {e}"
            )
            continue

        stats["blueprints_validation_errors"] += len(result.errors)
        stats["blueprints_validation_warnings"] += len(result.warnings)

        if result.is_valid:
            logger.info(
                f"   ✅ Blueprint '{validator_planet.name}' hợp lệ "
                f"({len(result.warnings)} cảnh báo)."
            )
        else:
            logger.warning(
                f"   ❌ Blueprint '{validator_planet.name}' KHÔNG hợp lệ: "
                f"{len(result.errors)} lỗi, {len(result.warnings)} cảnh báo."
            )
            for err in result.errors:
                logger.warning(f"      {err}")
