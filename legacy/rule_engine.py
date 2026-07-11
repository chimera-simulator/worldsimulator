# OUT_OF_SCOPE_REPO1 — không thuộc Design Pattern Harvester (t0..t5+summarizer).
# Giữ nguyên nội dung gốc, chỉ tách khỏi luồng import chính của main.py Repo 1.
# Xem SPEC_KY_THUAT_REPO1_V2.md mục 14 để biết lý do.

"""
rule_engine.py - World Consistency Validator
=============================================
Phần của hệ thống World Simulator Pipeline.
Kiểm tra tính nhất quán logic giữa Planet, Species, Character, và Environment
dựa trên Rule Library (Mục 27) và các quy tắc khoa học của thế giới giả tưởng.

NGUYÊN TẮC:
- Mọi kiểm tra đều là Python if/else thuần túy.
- Không gọi LLM để phán quyết.
- Mỗi vi phạm trả về ValidationError có mã lỗi, mô tả, và gợi ý sửa.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    ERROR   = "ERROR"    # Vi phạm cứng, phải sửa trước khi tạo phim
    WARNING = "WARNING"  # Không nhất quán nhẹ, nên sửa
    INFO    = "INFO"     # Ghi chú để theo dõi


# Các nhóm khí quyển được coi là "có oxy hô hấp được"
OXYGEN_BEARING_ATMOSPHERES = {
    "oxygen_rich", "earth_like", "nitrogen_oxygen", "mixed_breathable",
    "low_oxygen",   # thở được nhưng khó — WARNING thay vì ERROR
}

# Nhóm khí độc / không thể thở
TOXIC_ATMOSPHERES = {
    "methane", "ammonia", "hydrogen_sulfide", "chlorine", "sulfur_dioxide",
    "carbon_dioxide_heavy", "nitrogen_only", "vacuum", "none",
}

# Nhiệt độ giới hạn
TEMP_ABSOLUTE_MIN_K = 0
TEMP_MAX_LIQUID_WATER_K = 373  # 100°C — trên đây không có nước lỏng ở áp suất thường
TEMP_MIN_LIQUID_WATER_K = 273  # 0°C

# Trọng lực (đơn vị g — 1.0 = trọng lực Trái Đất)
GRAVITY_MIN_ATMOSPHERE_RETENTION = 0.1   # Dưới này khó giữ khí quyển đặc
GRAVITY_EXTREME_HIGH = 3.0               # Trên này sinh vật đứng thẳng rất khó

# Biome không tương thích
BIOME_CLIMATE_RULES: dict[str, set[str]] = {
    "tropical_rainforest": {"cold", "arctic", "desert"},
    "arctic_tundra":       {"tropical", "hot", "arid"},
    "desert":              {"arctic", "cold", "wetland"},
    "deep_ocean":          {"landlocked_only", "desert"},
    "crystal_forest":      {"lava", "extreme_heat"},
}

# Công nghệ tối thiểu cần có để một số đặc điểm tồn tại
TECH_LEVEL_ORDER = [
    "primitive", "ancient", "medieval", "industrial",
    "modern", "advanced", "stellar", "transcendent",
]


# ---------------------------------------------------------------------------
# Data classes — đại diện cho dữ liệu JSON đầu vào
# ---------------------------------------------------------------------------

@dataclass
class Planet:
    planet_id: str
    name: str
    atmosphere: str          # Ví dụ: "oxygen_rich", "methane", "vacuum"
    climate: str             # Ví dụ: "tropical", "arctic", "desert"
    temperature_min_k: float # Nhiệt độ min tính theo Kelvin
    temperature_max_k: float # Nhiệt độ max tính theo Kelvin
    gravity: float           # Đơn vị g (1.0 = Trái Đất)
    has_water: bool
    water_type: str          # "liquid", "ice", "vapor", "none"
    biomes: list[str]        # Danh sách biome, Ví dụ: ["desert", "canyon"]
    moon_count: int
    has_magnetic_field: bool
    radiation_level: str     # "low", "moderate", "high", "extreme"
    sky_color: str           # Ví dụ: "blue", "orange", "red"
    soil_color: str
    tech_level: str          # Trình độ văn minh
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Species:
    species_id: str
    name: str
    # Giải phẫu
    has_lungs: bool
    has_gills: bool
    has_photosynthesis: bool
    skin_type: str             # "scales", "fur", "feathers", "smooth", "chitin"
    eye_count: int
    limb_count: int
    has_horn: bool
    has_tail: bool
    has_wings: bool
    # Sinh học
    is_warm_blooded: bool
    body_temp_k: float         # Nhiệt độ cơ thể bình thường
    min_survivable_temp_k: float
    max_survivable_temp_k: float
    breathes: str              # "oxygen", "methane", "ammonia", "photosynthesis", "none"
    diet: str                  # "herbivore", "carnivore", "omnivore", "lithotroph"
    native_planet_id: str      # ID hành tinh gốc
    # Công nghệ & xã hội
    can_use_technology: bool
    tech_compatibility: list[str]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Character:
    character_id: str
    name: str
    species_id: str
    planet_id: str            # Hành tinh nhân vật đang ở
    native_planet_id: str     # Hành tinh gốc
    clothing_material: str    # "leather", "metal", "fabric", "crystal", "none"
    wears_heavy_armor: bool
    is_mc_female: bool        # True nếu là MC nữ (có rule riêng)
    is_mc: bool
    hair_style: str
    is_mc_male: bool          # True nếu là MC nam
    accessories: list[str]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Environment:
    scene_id: str
    planet_id: str
    biome: str               # Biome của cảnh này
    has_snow: bool
    has_tropical_forest: bool
    has_lava: bool
    lighting: str            # "daylight", "night", "dawn", "underground"
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Kết quả kiểm tra
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    code: str
    severity: Severity
    message: str
    suggestion: str
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"[{self.severity.value}] {self.code}: {self.message} "
            f"→ Gợi ý: {self.suggestion}"
        )


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    infos: list[ValidationError]

    @classmethod
    def empty(cls) -> "ValidationResult":
        return cls(is_valid=True, errors=[], warnings=[], infos=[])

    def add(self, ve: ValidationError) -> None:
        if ve.severity == Severity.ERROR:
            self.errors.append(ve)
            self.is_valid = False
        elif ve.severity == Severity.WARNING:
            self.warnings.append(ve)
        else:
            self.infos.append(ve)

    def merge(self, other: "ValidationResult") -> None:
        for e in other.errors:
            self.add(e)
        for w in other.warnings:
            self.add(w)
        for i in other.infos:
            self.add(i)

    def summary(self) -> str:
        lines = [
            f"Kết quả: {'HỢP LỆ ✓' if self.is_valid else 'KHÔNG HỢP LỆ ✗'}",
            f"  Lỗi nghiêm trọng : {len(self.errors)}",
            f"  Cảnh báo         : {len(self.warnings)}",
            f"  Thông tin        : {len(self.infos)}",
        ]
        if self.errors:
            lines.append("\n── LỖI NGHIÊM TRỌNG ──")
            for e in self.errors:
                lines.append(f"  {e}")
        if self.warnings:
            lines.append("\n── CẢNH BÁO ──")
            for w in self.warnings:
                lines.append(f"  {w}")
        if self.infos:
            lines.append("\n── GHI CHÚ ──")
            for i in self.infos:
                lines.append(f"  {i}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# WorldValidator — class chính
# ---------------------------------------------------------------------------

class WorldValidator:
    """
    Kiểm tra tính nhất quán của các thực thể trong World Simulator.

    Tất cả phương thức check_* trả về ValidationResult.
    Không có trạng thái nội bộ — mỗi lần gọi là độc lập.
    """

    # -----------------------------------------------------------------------
    # 1. Kiểm tra Planet
    # -----------------------------------------------------------------------

    def check_planet_internal_consistency(self, planet: Planet) -> ValidationResult:
        """
        Kiểm tra tính nhất quán nội tại của một Planet.
        Không cần Species hay Character.
        """
        result = ValidationResult.empty()

        # R-P01: Nhiệt độ không được âm tuyệt đối
        if planet.temperature_min_k < TEMP_ABSOLUTE_MIN_K:
            result.add(ValidationError(
                code="R-P01",
                severity=Severity.ERROR,
                message=(
                    f"Planet '{planet.name}': Nhiệt độ min "
                    f"{planet.temperature_min_k}K thấp hơn 0K (âm tuyệt đối)."
                ),
                suggestion="Đặt temperature_min_k >= 0.",
                context={"planet_id": planet.planet_id},
            ))

        # R-P02: min phải <= max
        if planet.temperature_min_k > planet.temperature_max_k:
            result.add(ValidationError(
                code="R-P02",
                severity=Severity.ERROR,
                message=(
                    f"Planet '{planet.name}': temperature_min_k "
                    f"({planet.temperature_min_k}K) > temperature_max_k "
                    f"({planet.temperature_max_k}K)."
                ),
                suggestion="Đảo lại giá trị min/max hoặc sửa dữ liệu.",
                context={"planet_id": planet.planet_id},
            ))

        # R-P03: Nước lỏng không thể tồn tại nếu nhiệt độ ngoài dải
        if planet.has_water and planet.water_type == "liquid":
            if planet.temperature_max_k < TEMP_MIN_LIQUID_WATER_K:
                result.add(ValidationError(
                    code="R-P03",
                    severity=Severity.ERROR,
                    message=(
                        f"Planet '{planet.name}': water_type='liquid' nhưng "
                        f"temperature_max_k={planet.temperature_max_k}K < 273K. "
                        "Nước không thể ở thể lỏng ở nhiệt độ này."
                    ),
                    suggestion=(
                        "Đổi water_type thành 'ice', hoặc tăng nhiệt độ hành tinh."
                    ),
                    context={"planet_id": planet.planet_id},
                ))
            if planet.temperature_min_k > TEMP_MAX_LIQUID_WATER_K:
                result.add(ValidationError(
                    code="R-P04",
                    severity=Severity.ERROR,
                    message=(
                        f"Planet '{planet.name}': water_type='liquid' nhưng "
                        f"temperature_min_k={planet.temperature_min_k}K > 373K. "
                        "Nước sẽ bốc hơi hoàn toàn."
                    ),
                    suggestion=(
                        "Đổi water_type thành 'vapor', hoặc giảm nhiệt độ hành tinh."
                    ),
                    context={"planet_id": planet.planet_id},
                ))

        # R-P05: Trọng lực quá thấp khó giữ khí quyển
        if planet.gravity < GRAVITY_MIN_ATMOSPHERE_RETENTION:
            atm = planet.atmosphere.lower()
            if atm not in ("vacuum", "none"):
                result.add(ValidationError(
                    code="R-P05",
                    severity=Severity.WARNING,
                    message=(
                        f"Planet '{planet.name}': Trọng lực {planet.gravity}g "
                        f"rất thấp nhưng atmosphere='{planet.atmosphere}'. "
                        "Khí quyển dày khó duy trì ở trọng lực này."
                    ),
                    suggestion=(
                        "Cân nhắc đổi atmosphere thành 'thin', 'trace', hoặc 'vacuum'."
                    ),
                    context={"planet_id": planet.planet_id},
                ))

        # R-P06: Trọng lực cực cao
        if planet.gravity > GRAVITY_EXTREME_HIGH:
            result.add(ValidationError(
                code="R-P06",
                severity=Severity.WARNING,
                message=(
                    f"Planet '{planet.name}': Trọng lực {planet.gravity}g "
                    "cực cao. Sinh vật đứng thẳng hầu như không thể tồn tại."
                ),
                suggestion=(
                    "Nếu có sinh vật đứng thẳng, cần ghi chú cơ chế thích nghi "
                    "đặc biệt (khung xương kim loại, tiến hóa nặng, v.v.)."
                ),
                context={"planet_id": planet.planet_id},
            ))

        # R-P07: Hành tinh sa mạc không có rừng nhiệt đới (Rule Library)
        if "desert" in planet.biomes and "tropical_rainforest" in planet.biomes:
            result.add(ValidationError(
                code="R-P07",
                severity=Severity.ERROR,
                message=(
                    f"Planet '{planet.name}': Biome chứa cả 'desert' và "
                    "'tropical_rainforest' — hai biome này mâu thuẫn nhau."
                ),
                suggestion=(
                    "Chọn một trong hai, hoặc tách thành hai vùng hành tinh khác nhau."
                ),
                context={"planet_id": planet.planet_id},
            ))

        # R-P08: Hành tinh băng giá không có rừng nhiệt đới
        if planet.climate in ("arctic", "frozen") and "tropical_rainforest" in planet.biomes:
            result.add(ValidationError(
                code="R-P08",
                severity=Severity.ERROR,
                message=(
                    f"Planet '{planet.name}': Climate='{planet.climate}' nhưng "
                    "biome có 'tropical_rainforest'. Mâu thuẫn khí hậu."
                ),
                suggestion="Loại bỏ biome tropical_rainforest hoặc sửa climate.",
                context={"planet_id": planet.planet_id},
            ))

        # R-P09: Không có từ trường + bức xạ cao => sinh vật bề mặt khó tồn tại
        if not planet.has_magnetic_field and planet.radiation_level in ("high", "extreme"):
            result.add(ValidationError(
                code="R-P09",
                severity=Severity.WARNING,
                message=(
                    f"Planet '{planet.name}': Không có từ trường "
                    f"và radiation_level='{planet.radiation_level}'. "
                    "Sinh vật bề mặt sẽ bị bức xạ tiêu diệt nhanh chóng."
                ),
                suggestion=(
                    "Thêm cơ chế bảo vệ (lớp đá dày, sinh sống dưới đất, "
                    "hoặc sinh vật có khả năng kháng bức xạ đặc biệt)."
                ),
                context={"planet_id": planet.planet_id},
            ))

        # R-P10: moon_count âm
        if planet.moon_count < 0:
            result.add(ValidationError(
                code="R-P10",
                severity=Severity.ERROR,
                message=f"Planet '{planet.name}': moon_count={planet.moon_count} < 0.",
                suggestion="Đặt moon_count >= 0.",
                context={"planet_id": planet.planet_id},
            ))

        # R-P11: tech_level phải nằm trong danh sách hợp lệ
        if planet.tech_level not in TECH_LEVEL_ORDER:
            result.add(ValidationError(
                code="R-P11",
                severity=Severity.ERROR,
                message=(
                    f"Planet '{planet.name}': tech_level='{planet.tech_level}' "
                    f"không hợp lệ. Các giá trị cho phép: {TECH_LEVEL_ORDER}."
                ),
                suggestion=f"Chọn một giá trị trong: {TECH_LEVEL_ORDER}.",
                context={"planet_id": planet.planet_id},
            ))

        return result

    # -----------------------------------------------------------------------
    # 2. Kiểm tra Species
    # -----------------------------------------------------------------------

    def check_species_internal_consistency(self, species: Species) -> ValidationResult:
        """Kiểm tra tính nhất quán nội bộ của một Species."""
        result = ValidationResult.empty()

        # R-S01: Không thể có cả phổi lẫn quang hợp làm cơ chế hô hấp chính
        if species.has_lungs and species.has_photosynthesis and species.breathes == "photosynthesis":
            result.add(ValidationError(
                code="R-S01",
                severity=Severity.WARNING,
                message=(
                    f"Species '{species.name}': has_lungs=True nhưng "
                    "breathes='photosynthesis'. Phổi sẽ trở thành cơ quan thừa."
                ),
                suggestion=(
                    "Đặt has_lungs=False nếu chỉ quang hợp, "
                    "hoặc đổi breathes thành 'oxygen' nếu phổi là chính."
                ),
                context={"species_id": species.species_id},
            ))

        # R-S02: eye_count âm
        if species.eye_count < 0:
            result.add(ValidationError(
                code="R-S02",
                severity=Severity.ERROR,
                message=f"Species '{species.name}': eye_count={species.eye_count} < 0.",
                suggestion="Đặt eye_count >= 0 (0 = mù hoàn toàn).",
                context={"species_id": species.species_id},
            ))

        # R-S03: limb_count âm
        if species.limb_count < 0:
            result.add(ValidationError(
                code="R-S03",
                severity=Severity.ERROR,
                message=f"Species '{species.name}': limb_count={species.limb_count} < 0.",
                suggestion="Đặt limb_count >= 0.",
                context={"species_id": species.species_id},
            ))

        # R-S04: Nhiệt độ cơ thể phải nằm trong khoảng sinh tồn
        if not (species.min_survivable_temp_k <= species.body_temp_k <= species.max_survivable_temp_k):
            result.add(ValidationError(
                code="R-S04",
                severity=Severity.ERROR,
                message=(
                    f"Species '{species.name}': body_temp_k={species.body_temp_k}K "
                    f"nằm ngoài khoảng sinh tồn "
                    f"[{species.min_survivable_temp_k}, {species.max_survivable_temp_k}]K."
                ),
                suggestion="Sửa body_temp_k để nằm trong khoảng min/max.",
                context={"species_id": species.species_id},
            ))

        # R-S05: min_survivable phải <= max_survivable
        if species.min_survivable_temp_k > species.max_survivable_temp_k:
            result.add(ValidationError(
                code="R-S05",
                severity=Severity.ERROR,
                message=(
                    f"Species '{species.name}': "
                    f"min_survivable_temp_k={species.min_survivable_temp_k}K > "
                    f"max_survivable_temp_k={species.max_survivable_temp_k}K."
                ),
                suggestion="Đảo lại hoặc sửa giá trị min/max.",
                context={"species_id": species.species_id},
            ))

        # R-S06: breathes phải là giá trị hợp lệ
        valid_breathes = {"oxygen", "methane", "ammonia", "photosynthesis",
                          "chemosynthesis", "none", "hydrogen"}
        if species.breathes not in valid_breathes:
            result.add(ValidationError(
                code="R-S06",
                severity=Severity.ERROR,
                message=(
                    f"Species '{species.name}': breathes='{species.breathes}' "
                    f"không hợp lệ. Các giá trị cho phép: {sorted(valid_breathes)}."
                ),
                suggestion="Chọn giá trị hợp lệ cho trường breathes.",
                context={"species_id": species.species_id},
            ))

        return result

    # -----------------------------------------------------------------------
    # 3. Kiểm tra Species vs Planet — check_breathing_logic
    # -----------------------------------------------------------------------

    def check_breathing_logic(self, planet: Planet, species: Species) -> ValidationResult:
        """
        R-B: Kiểm tra logic hô hấp.
        Nếu hành tinh không có oxygen trong atmosphere mà species lại có lungs
        và thở bằng oxygen → vi phạm.
        """
        result = ValidationResult.empty()
        atm = planet.atmosphere.lower().strip()
        breathes = species.breathes.lower().strip()

        # R-B01: Species thở oxygen nhưng hành tinh không có oxygen
        if breathes == "oxygen" and atm not in OXYGEN_BEARING_ATMOSPHERES:
            severity = Severity.ERROR
            msg_extra = ""
            if atm == "low_oxygen":
                # low_oxygen vẫn thở được nhưng khó
                severity = Severity.WARNING
                msg_extra = " (low_oxygen — thở được nhưng cần cơ chế thích nghi)."
            result.add(ValidationError(
                code="R-B01",
                severity=severity,
                message=(
                    f"Species '{species.name}' thở oxygen nhưng Planet "
                    f"'{planet.name}' có atmosphere='{planet.atmosphere}'"
                    f"{msg_extra}."
                    " Không thể tồn tại mà không có thiết bị hỗ trợ."
                ),
                suggestion=(
                    "Thêm ghi chú thiết bị thở trong Character JSON, "
                    "hoặc đổi breathes của species cho phù hợp atmosphere."
                ),
                context={
                    "planet_id": planet.planet_id,
                    "species_id": species.species_id,
                    "atmosphere": planet.atmosphere,
                },
            ))

        # R-B02: Species có phổi nhưng hành tinh là vacuum/none
        if species.has_lungs and atm in ("vacuum", "none"):
            result.add(ValidationError(
                code="R-B02",
                severity=Severity.ERROR,
                message=(
                    f"Species '{species.name}' có phổi (has_lungs=True) "
                    f"nhưng Planet '{planet.name}' không có khí quyển "
                    f"(atmosphere='{planet.atmosphere}'). "
                    "Phổi vô dụng và áp suất trong/ngoài cơ thể sẽ gây tử vong."
                ),
                suggestion=(
                    "Thêm bộ giáp áp suất vào Character/Species, "
                    "hoặc đổi breathes thành 'none' và loại bỏ phổi."
                ),
                context={
                    "planet_id": planet.planet_id,
                    "species_id": species.species_id,
                },
            ))

        # R-B03: Species thở methane nhưng hành tinh không có methane
        if breathes == "methane" and "methane" not in atm:
            result.add(ValidationError(
                code="R-B03",
                severity=Severity.ERROR,
                message=(
                    f"Species '{species.name}' thở methane nhưng Planet "
                    f"'{planet.name}' không có methane trong atmosphere "
                    f"('{planet.atmosphere}')."
                ),
                suggestion=(
                    "Thêm thiết bị cung cấp methane, hoặc điều chỉnh "
                    "atmosphere của hành tinh."
                ),
                context={
                    "planet_id": planet.planet_id,
                    "species_id": species.species_id,
                },
            ))

        # R-B04: Species quang hợp nhưng hành tinh không có ánh sáng (underground only)
        if species.has_photosynthesis and breathes == "photosynthesis":
            if planet.radiation_level == "none" or planet.sky_color.lower() == "none":
                result.add(ValidationError(
                    code="R-B04",
                    severity=Severity.WARNING,
                    message=(
                        f"Species '{species.name}' quang hợp nhưng Planet "
                        f"'{planet.name}' có thể không có đủ ánh sáng "
                        "(radiation=none hoặc sky=none)."
                    ),
                    suggestion=(
                        "Xác nhận nguồn năng lượng thay thế (chemosynthesis, "
                        "tia cực tím nhân tạo, v.v.)."
                    ),
                    context={
                        "planet_id": planet.planet_id,
                        "species_id": species.species_id,
                    },
                ))

        return result

    # -----------------------------------------------------------------------
    # 4. Kiểm tra nhiệt độ sinh tồn
    # -----------------------------------------------------------------------

    def check_temperature_survival(self, planet: Planet, species: Species) -> ValidationResult:
        """
        R-T: Kiểm tra xem khoảng nhiệt độ của hành tinh có nằm trong
        ngưỡng sinh tồn của species không.
        """
        result = ValidationResult.empty()

        # Toàn bộ nhiệt độ hành tinh cao hơn max của species
        if planet.temperature_min_k > species.max_survivable_temp_k:
            result.add(ValidationError(
                code="R-T01",
                severity=Severity.ERROR,
                message=(
                    f"Planet '{planet.name}' (min {planet.temperature_min_k}K) "
                    f"quá nóng so với Species '{species.name}' "
                    f"(max sinh tồn {species.max_survivable_temp_k}K). "
                    "Species sẽ chết ngay lập tức."
                ),
                suggestion=(
                    "Thêm ghi chú thiết bị làm mát, hoặc đặt species trên "
                    "hành tinh mát hơn."
                ),
                context={
                    "planet_id": planet.planet_id,
                    "species_id": species.species_id,
                },
            ))

        # Toàn bộ nhiệt độ hành tinh thấp hơn min của species
        if planet.temperature_max_k < species.min_survivable_temp_k:
            result.add(ValidationError(
                code="R-T02",
                severity=Severity.ERROR,
                message=(
                    f"Planet '{planet.name}' (max {planet.temperature_max_k}K) "
                    f"quá lạnh so với Species '{species.name}' "
                    f"(min sinh tồn {species.min_survivable_temp_k}K). "
                    "Species sẽ đóng băng."
                ),
                suggestion=(
                    "Thêm thiết bị sưởi ấm hoặc quần áo đặc biệt, "
                    "hoặc đặt species trên hành tinh ấm hơn."
                ),
                context={
                    "planet_id": planet.planet_id,
                    "species_id": species.species_id,
                },
            ))

        # Cảnh báo: nhiệt độ hành tinh vẫn trong ngưỡng nhưng gần giới hạn
        if result.is_valid:
            margin = 20  # Kelvin
            if planet.temperature_max_k > species.max_survivable_temp_k - margin:
                result.add(ValidationError(
                    code="R-T03",
                    severity=Severity.WARNING,
                    message=(
                        f"Planet '{planet.name}' có thể đạt "
                        f"{planet.temperature_max_k}K, gần sát ngưỡng max "
                        f"của Species '{species.name}' "
                        f"({species.max_survivable_temp_k}K)."
                    ),
                    suggestion="Cân nhắc thêm ghi chú về khả năng chịu nhiệt.",
                    context={
                        "planet_id": planet.planet_id,
                        "species_id": species.species_id,
                    },
                ))

        return result

    # -----------------------------------------------------------------------
    # 5. Kiểm tra Character Rule Library
    # -----------------------------------------------------------------------

    def check_character_rules(self, character: Character, species: Species) -> ValidationResult:
        """
        R-C: Kiểm tra các quy tắc từ Rule Library áp dụng cho nhân vật.
        Bao gồm các rule cứng cho MC (nữ không mặc giáp nặng, nam không đổi tóc, v.v.)
        """
        result = ValidationResult.empty()

        # R-C01: MC nữ không mặc giáp hạng nặng (Rule Library)
        if character.is_mc and character.is_mc_female and character.wears_heavy_armor:
            result.add(ValidationError(
                code="R-C01",
                severity=Severity.ERROR,
                message=(
                    f"MC nữ '{character.name}' đang mặc giáp hạng nặng "
                    "(wears_heavy_armor=True). Vi phạm Rule Library."
                ),
                suggestion=(
                    "Đổi trang phục MC nữ thành giáp nhẹ, trang phục phong cách, "
                    "hoặc trang phục hành trình. Không dùng heavy armor."
                ),
                context={"character_id": character.character_id},
            ))

        # R-C02: MC nam không đổi kiểu tóc (hair_style phải nhất quán)
        # Quy tắc này được kiểm tra ở cấp Episode — ở đây chỉ cảnh báo nếu hair_style rỗng
        if character.is_mc and character.is_mc_male and not character.hair_style.strip():
            result.add(ValidationError(
                code="R-C02",
                severity=Severity.WARNING,
                message=(
                    f"MC nam '{character.name}': hair_style đang rỗng. "
                    "Rule Library yêu cầu MC nam không được đổi kiểu tóc, "
                    "cần định nghĩa hair_style cố định."
                ),
                suggestion=(
                    "Điền hair_style cụ thể vào JSON của MC nam và "
                    "giữ nguyên qua tất cả các tập."
                ),
                context={"character_id": character.character_id},
            ))

        # R-C03: Species có đặc điểm sừng nhưng character không ghi nhận (nhất quán)
        if species.has_horn and "horn" not in [a.lower() for a in character.accessories]:
            # Chỉ INFO — không phải lỗi, nhưng nên ghi chú
            result.add(ValidationError(
                code="R-C03",
                severity=Severity.INFO,
                message=(
                    f"Character '{character.name}' thuộc Species "
                    f"'{species.name}' (has_horn=True) nhưng không có "
                    "'horn' trong accessories list."
                ),
                suggestion=(
                    "Thêm 'horn' vào accessories hoặc xác nhận đây là "
                    "ngoại lệ sinh học có ghi chú."
                ),
                context={
                    "character_id": character.character_id,
                    "species_id": species.species_id,
                },
            ))

        # R-C04: Species có đặc điểm đuôi nhưng không ghi nhận
        if species.has_tail and "tail" not in [a.lower() for a in character.accessories]:
            result.add(ValidationError(
                code="R-C04",
                severity=Severity.INFO,
                message=(
                    f"Character '{character.name}' thuộc Species "
                    f"'{species.name}' (has_tail=True) nhưng không có "
                    "'tail' trong accessories list."
                ),
                suggestion=(
                    "Xác nhận đuôi được thể hiện trong Character Blueprint "
                    "để nhất quán hình ảnh qua các tập."
                ),
                context={
                    "character_id": character.character_id,
                    "species_id": species.species_id,
                },
            ))

        return result

    # -----------------------------------------------------------------------
    # 6. Kiểm tra Environment vs Planet
    # -----------------------------------------------------------------------

    def check_environment_consistency(self, planet: Planet, env: Environment) -> ValidationResult:
        """
        R-E: Kiểm tra scene environment có nhất quán với planet blueprint không.
        """
        result = ValidationResult.empty()

        # R-E01: Planet không có tuyết nhưng scene có tuyết
        is_cold_planet = planet.climate in ("arctic", "frozen", "cold")
        if env.has_snow and not is_cold_planet:
            # Kiểm tra nhiệt độ thực tế
            if planet.temperature_min_k > TEMP_MIN_LIQUID_WATER_K:
                result.add(ValidationError(
                    code="R-E01",
                    severity=Severity.ERROR,
                    message=(
                        f"Scene '{env.scene_id}' trên Planet '{planet.name}' "
                        f"có tuyết (has_snow=True) nhưng nhiệt độ min "
                        f"là {planet.temperature_min_k}K > 273K. "
                        "Tuyết không thể tồn tại."
                    ),
                    suggestion=(
                        "Loại bỏ tuyết khỏi scene này, "
                        "hoặc chuyển scene sang vùng cao lạnh hơn của hành tinh."
                    ),
                    context={
                        "planet_id": planet.planet_id,
                        "scene_id": env.scene_id,
                    },
                ))

        # R-E02: Scene có rừng nhiệt đới nhưng hành tinh là sa mạc/băng
        if env.has_tropical_forest and "desert" in planet.biomes:
            result.add(ValidationError(
                code="R-E02",
                severity=Severity.ERROR,
                message=(
                    f"Scene '{env.scene_id}' có rừng nhiệt đới trên Planet "
                    f"'{planet.name}' vốn là hành tinh sa mạc. Mâu thuẫn biome."
                ),
                suggestion=(
                    "Loại bỏ has_tropical_forest hoặc chuyển scene sang "
                    "hành tinh khác có biome phù hợp."
                ),
                context={
                    "planet_id": planet.planet_id,
                    "scene_id": env.scene_id,
                },
            ))

        # R-E03: Scene có dung nham nhưng hành tinh là băng giá
        if env.has_lava and planet.temperature_max_k < 500:
            result.add(ValidationError(
                code="R-E03",
                severity=Severity.ERROR,
                message=(
                    f"Scene '{env.scene_id}': has_lava=True nhưng Planet "
                    f"'{planet.name}' có nhiệt độ max chỉ {planet.temperature_max_k}K "
                    "(thấp hơn nhiệt độ nóng chảy đá ~600K+). "
                    "Dung nham không thể tồn tại."
                ),
                suggestion=(
                    "Loại bỏ has_lava, hoặc chuyển scene sang hành tinh núi lửa."
                ),
                context={
                    "planet_id": planet.planet_id,
                    "scene_id": env.scene_id,
                },
            ))

        # R-E04: Ánh sáng ban ngày không thể có trên hành tinh không có mặt trời
        if env.lighting == "daylight" and planet.sky_color.lower() == "none":
            result.add(ValidationError(
                code="R-E04",
                severity=Severity.WARNING,
                message=(
                    f"Scene '{env.scene_id}': lighting='daylight' nhưng "
                    f"Planet '{planet.name}' có sky_color='none' "
                    "(có thể không có bầu trời/mặt trời)."
                ),
                suggestion=(
                    "Kiểm tra nguồn sáng của hành tinh. "
                    "Đổi lighting thành 'bioluminescent' hoặc 'artificial' nếu phù hợp."
                ),
                context={
                    "planet_id": planet.planet_id,
                    "scene_id": env.scene_id,
                },
            ))

        return result

    # -----------------------------------------------------------------------
    # 7. Kiểm tra tính nhất quán MC giữa các tập (Episode-level)
    # -----------------------------------------------------------------------

    def check_mc_consistency_across_episodes(
        self,
        mc_json_original: dict[str, Any],
        mc_json_current: dict[str, Any],
    ) -> ValidationResult:
        """
        R-M: So sánh JSON MC tập hiện tại với JSON gốc cố định.
        Đảm bảo không có trường cố định nào bị thay đổi.
        """
        result = ValidationResult.empty()

        IMMUTABLE_FIELDS = [
            "character_id", "name", "species_id", "native_planet_id",
            "hair_style", "eye_color", "skin_color", "height",
        ]

        for field_name in IMMUTABLE_FIELDS:
            original_val = mc_json_original.get(field_name)
            current_val  = mc_json_current.get(field_name)
            if original_val is not None and current_val is not None:
                if original_val != current_val:
                    result.add(ValidationError(
                        code="R-M01",
                        severity=Severity.ERROR,
                        message=(
                            f"MC '{mc_json_original.get('name', '?')}': "
                            f"Trường bất biến '{field_name}' đã bị thay đổi. "
                            f"Gốc: '{original_val}' → Hiện tại: '{current_val}'."
                        ),
                        suggestion=(
                            "Khôi phục giá trị gốc. "
                            "LLM không được phép thay đổi các trường cố định của MC."
                        ),
                        context={
                            "field": field_name,
                            "original": original_val,
                            "current": current_val,
                        },
                    ))

        return result

    # -----------------------------------------------------------------------
    # 8. Kiểm tra Species vs Planet nơi đang cư trú (không phải native)
    # -----------------------------------------------------------------------

    def check_species_on_foreign_planet(
        self, planet: Planet, species: Species, has_life_support: bool = False
    ) -> ValidationResult:
        """
        R-F: Kiểm tra khi species ở trên một hành tinh không phải gốc của mình.
        has_life_support=True nếu nhân vật được ghi chú có thiết bị hỗ trợ.
        """
        result = ValidationResult.empty()

        if has_life_support:
            result.add(ValidationError(
                code="R-F00",
                severity=Severity.INFO,
                message=(
                    f"Species '{species.name}' trên Planet '{planet.name}' "
                    "với thiết bị hỗ trợ sự sống. Các kiểm tra môi trường được bỏ qua."
                ),
                suggestion="Đảm bảo thiết bị hỗ trợ được thể hiện trong prompt hình ảnh.",
                context={},
            ))
            return result

        # Gọi các kiểm tra cơ bản
        result.merge(self.check_breathing_logic(planet, species))
        result.merge(self.check_temperature_survival(planet, species))

        return result

    # -----------------------------------------------------------------------
    # 9. Validate toàn bộ một Scene
    # -----------------------------------------------------------------------

    def validate_scene(
        self,
        planet: Planet,
        species_list: list[Species],
        characters: list[Character],
        environment: Environment,
        mc_originals: list[dict[str, Any]] | None = None,
        mc_currents: list[dict[str, Any]] | None = None,
    ) -> ValidationResult:
        """
        Kiểm tra toàn bộ một cảnh quay:
        - Planet internal
        - Environment vs Planet
        - Mỗi Species vs Planet (breathing + temperature)
        - Mỗi Character rules
        - MC consistency (nếu cung cấp)
        """
        result = ValidationResult.empty()

        # Kiểm tra hành tinh
        result.merge(self.check_planet_internal_consistency(planet))

        # Kiểm tra environment
        result.merge(self.check_environment_consistency(planet, environment))

        # Kiểm tra từng species
        species_map: dict[str, Species] = {s.species_id: s for s in species_list}
        for sp in species_list:
            result.merge(self.check_species_internal_consistency(sp))
            result.merge(self.check_breathing_logic(planet, sp))
            result.merge(self.check_temperature_survival(planet, sp))

        # Kiểm tra từng character
        for char in characters:
            sp = species_map.get(char.species_id)
            if sp:
                result.merge(self.check_character_rules(char, sp))
            else:
                result.add(ValidationError(
                    code="R-C99",
                    severity=Severity.ERROR,
                    message=(
                        f"Character '{char.name}': species_id='{char.species_id}' "
                        "không tìm thấy trong species_list."
                    ),
                    suggestion="Kiểm tra lại species_id hoặc bổ sung Species vào danh sách.",
                    context={"character_id": char.character_id},
                ))

        # Kiểm tra MC consistency
        if mc_originals and mc_currents:
            for orig, curr in zip(mc_originals, mc_currents):
                result.merge(self.check_mc_consistency_across_episodes(orig, curr))

        return result


# ---------------------------------------------------------------------------
# Demo / Quick-test (chạy trực tiếp để kiểm tra)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    validator = WorldValidator()

    # --- Tạo dữ liệu mẫu ---
    hanoi_planet = Planet(
        planet_id="PLN-001",
        name="Tinh Cầu Hanorus",
        atmosphere="oxygen_rich",
        climate="tropical",
        temperature_min_k=288,
        temperature_max_k=313,
        gravity=1.0,
        has_water=True,
        water_type="liquid",
        biomes=["tropical_rainforest", "wetland"],
        moon_count=1,
        has_magnetic_field=True,
        radiation_level="low",
        sky_color="blue",
        soil_color="brown",
        tech_level="advanced",
    )

    desert_planet = Planet(
        planet_id="PLN-002",
        name="Sa Mạc Zaroth",
        atmosphere="nitrogen_oxygen",
        climate="desert",
        temperature_min_k=300,
        temperature_max_k=420,
        gravity=0.9,
        has_water=False,
        water_type="none",
        biomes=["desert", "canyon"],
        moon_count=2,
        has_magnetic_field=False,
        radiation_level="high",
        sky_color="orange",
        soil_color="red",
        tech_level="medieval",
    )

    # Species thở oxygen — hợp lệ trên Hanorus
    human_species = Species(
        species_id="SPC-001",
        name="Homo Nova",
        has_lungs=True,
        has_gills=False,
        has_photosynthesis=False,
        skin_type="smooth",
        eye_count=2,
        limb_count=4,
        has_horn=False,
        has_tail=False,
        has_wings=False,
        is_warm_blooded=True,
        body_temp_k=310,
        min_survivable_temp_k=273,
        max_survivable_temp_k=323,
        breathes="oxygen",
        diet="omnivore",
        native_planet_id="PLN-001",
        can_use_technology=True,
        tech_compatibility=["advanced", "modern"],
    )

    # MC nữ — vi phạm rule heavy armor
    mc_female = Character(
        character_id="MC-F",
        name="Aria Vân",
        species_id="SPC-001",
        planet_id="PLN-001",
        native_planet_id="PLN-001",
        clothing_material="metal",
        wears_heavy_armor=True,   # ← VI PHẠM
        is_mc_female=True,
        is_mc=True,
        hair_style="long_black",
        is_mc_male=False,
        accessories=["ring"],
    )

    env_hanoi = Environment(
        scene_id="SCN-001",
        planet_id="PLN-001",
        biome="tropical_rainforest",
        has_snow=False,
        has_tropical_forest=True,
        has_lava=False,
        lighting="daylight",
    )

    # Environment vi phạm — tuyết trên sa mạc nóng
    env_desert_snow = Environment(
        scene_id="SCN-002",
        planet_id="PLN-002",
        biome="desert",
        has_snow=True,             # ← VI PHẠM
        has_tropical_forest=False,
        has_lava=False,
        lighting="daylight",
    )

    print("=" * 60)
    print("TEST 1: Hanoi Planet (hợp lệ)")
    print("=" * 60)
    r1 = validator.check_planet_internal_consistency(hanoi_planet)
    print(r1.summary())

    print("\n" + "=" * 60)
    print("TEST 2: Sa Mạc Zaroth (không có từ trường + bức xạ cao)")
    print("=" * 60)
    r2 = validator.check_planet_internal_consistency(desert_planet)
    print(r2.summary())

    print("\n" + "=" * 60)
    print("TEST 3: Breathing Logic — Homo Nova thở oxygen trên Hanorus (OK)")
    print("=" * 60)
    r3 = validator.check_breathing_logic(hanoi_planet, human_species)
    print(r3.summary())

    print("\n" + "=" * 60)
    print("TEST 4: Breathing Logic — Homo Nova thở oxygen trên Sa Mạc (vacuum atmosphere test)")
    print("=" * 60)
    vacuum_planet = Planet(
        planet_id="PLN-003",
        name="Hành Tinh Chân Không",
        atmosphere="vacuum",
        climate="extreme",
        temperature_min_k=50,
        temperature_max_k=450,
        gravity=0.4,
        has_water=False,
        water_type="none",
        biomes=["barren"],
        moon_count=0,
        has_magnetic_field=False,
        radiation_level="extreme",
        sky_color="none",
        soil_color="grey",
        tech_level="primitive",
    )
    r4 = validator.check_breathing_logic(vacuum_planet, human_species)
    print(r4.summary())

    print("\n" + "=" * 60)
    print("TEST 5: MC nữ mặc heavy armor (vi phạm Rule Library)")
    print("=" * 60)
    r5 = validator.check_character_rules(mc_female, human_species)
    print(r5.summary())

    print("\n" + "=" * 60)
    print("TEST 6: Environment — tuyết trên sa mạc nóng (vi phạm)")
    print("=" * 60)
    r6 = validator.check_environment_consistency(desert_planet, env_desert_snow)
    print(r6.summary())

    print("\n" + "=" * 60)
    print("TEST 7: Validate toàn bộ Scene (Hanoi Planet)")
    print("=" * 60)
    r7 = validator.validate_scene(
        planet=hanoi_planet,
        species_list=[human_species],
        characters=[mc_female],
        environment=env_hanoi,
    )
    print(r7.summary())
