# OUT_OF_SCOPE_REPO1 — không thuộc Design Pattern Harvester (t0..t5+summarizer).
# Giữ nguyên nội dung gốc, chỉ tách khỏi luồng import chính của main.py Repo 1.
# Xem SPEC_KY_THUAT_REPO1_V2.md mục 14 để biết lý do.

"""
T6: WORLD FORGE — Khoa Học -> Blueprint Giả Tưởng
====================================================
Đây là ranh giới LLM chính thức của pipeline `rulesworldsimulator` (Repo 1).
KHÔNG có bước nào trước T6 được gọi LLM (T0-T5 chỉ scrape/normalize/dedupe/
upload thuần Python). T6 là nơi DUY NHẤT dữ liệu khoa học thô được "thổi hồn"
thành dữ liệu giả tưởng, và ngay trong T6 việc này cũng bị chia tách rõ:

    - Suy luận VẬT LÝ (số liệu, nhãn, thuộc tính)  -> Python thuần, không LLM.
    - Diễn đạt HÌNH THÁI + VĂN MIÊU TẢ             -> LLM (forge_blueprint /
                                                        forge_fiction).

Input contract (khớp với `t5_upload.py` / T3-T4 upstream — xem
`world_rules` collection): 1 "quy luật khoa học" là 1 dict dạng:

    {
        "content_hash": "hash_123",
        "rule_type": "biochemistry" | "physics" | "geology" | "climate" | ...,
        "url": "...",
        "title": "...",
        "summary": "...",                 # tóm tắt do summarizer.py (T3) sinh
        "key_facts": ["...", "..."],       # các câu dữ kiện rời, T3
        "causal_sentences": ["...", ...],  # câu quan hệ nhân-quả trích từ nguồn, T3
        "matched_keywords": ["...", ...],  # từ khóa khớp SCIENCE_ONTOLOGY_KEYWORDS
        "run_id": "...",
        "uploaded_at": "...",
    }

Output: 1 Blueprint dict hoàn chỉnh, sẵn sàng `insert_one`/`insert_many` vào
MongoDB collection Blueprint (Repo 1 hoặc Repo 3 tùy nơi gọi), gồm:
    - Toàn bộ field của schema mục tiêu (Planet/Species/Creature/Flora...).
    - `fictional_description`: văn miêu tả do LLM (forge_fiction) sinh.
    - `_forge_meta`: log truy nguyên (rule gốc nào, đã suy ra gì, có mâu thuẫn
      Rule Library nào không) — để debug/audit, KHÔNG phải trường hiển thị.
"""

from __future__ import annotations

import re
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional

from schemas import (
    Planet,
    PhysicsAttributes,
    Species,
    Creature,
    Flora,
    Rule,
    RuleLibrary,
    RuleScope,
    RuleType,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Các target schema mà Forge biết cách khởi tạo template rỗng cho.
_TARGET_SCHEMA = {
    "planet": Planet,
    "species": Species,
    "creature": Creature,
    "flora": Flora,
}


# ---------------------------------------------------------------------------
# BƯỚC 2 — PHÂN TÍCH VẬT LÝ (PYTHON THUẦN, TUYỆT ĐỐI KHÔNG LLM)
# ---------------------------------------------------------------------------
#
# Mỗi rule là (regex_pattern, field, value_hoặc_hàm_suy_ra).
# `value` có thể là:
#   - giá trị cố định (str/float/int)
#   - callable(match) -> giá trị, khi cần đọc lại số liệu trong câu khớp
#     (ví dụ "-40°C" -> parse ra số để suy climate biome theo ngưỡng).
#
# Đây CHÍNH LÀ nơi domain knowledge vật lý sống — mở rộng bằng cách thêm dòng,
# không cần đụng vào logic điều khiển bên dưới.

def _f(value):
    """Helper: bọc 1 giá trị cố định thành callable(match) để dùng đồng nhất."""
    return lambda m: value


# Mỗi entry: (regex_pattern, field, value_fn, canonical_tag)
#
# `canonical_tag` là tên tiếng Anh chuẩn hóa của hiện tượng vừa khớp — dùng để
# so khớp với `Rule.attribute` trong Rule Library ở check_rule_conflicts().
# Giá trị hiển thị (value_fn) có thể là label tiếng Việt, nhưng việc so khớp
# rule KHÔNG dựa vào label hiển thị (dễ lệch ngôn ngữ) mà dựa vào tag này.
PHYSICS_RULES: list[tuple[str, str, Any, str]] = [
    # --- Áp suất / trọng lực ---
    (r"\bhigh[- ]pressure\b|\báp suất cao\b", "gravity", _f("1.5g"), "high_pressure"),
    (r"\blow[- ]pressure\b|\báp suất thấp\b", "gravity", _f("0.6g"), "low_pressure"),
    (r"\bmicrogravity\b|\bvi trọng lực\b", "gravity", _f("0.1g"), "microgravity"),
    (r"\bsuper[- ]?earth\b|\bsiêu trái đất\b", "gravity", _f("1.8g"), "super_earth"),

    # --- Khí quyển ---
    (r"\bmethane[- ]rich\b|\bgiàu methane\b", "atmosphere", _f("Methane-Nitrogen, dày"), "methane_rich"),
    (r"\btoxic atmosphere\b|\bkhí quyển độc\b|\bsulfur(ic)?\b|\blưu huỳnh\b",
     "atmosphere", _f("Lưu huỳnh-CO2, độc hại"), "toxic_sulfuric"),
    (r"\bthin atmosphere\b|\bkhí quyển mỏng\b", "atmosphere", _f("Nitrogen-Oxygen, mỏng"), "thin_atmosphere"),
    (r"\bno atmosphere\b|\bkhông có khí quyển\b|\bvacuum\b", "atmosphere", _f("Chân không"), "vacuum"),
    (r"\boxygen[- ]rich\b|\bgiàu oxy\b", "atmosphere", _f("Oxygen-Nitrogen, đậm đặc"), "oxygen_rich"),

    # --- Bức xạ ---
    (r"\bhigh radiation\b|\bbức xạ cao\b|\bgamma[- ]ray\b",
     "sun_type", _f("Sao mẹ hoạt động mạnh, bức xạ cao"), "high_radiation"),
    (r"\bred dwarf\b|\bsao lùn đỏ\b", "sun_type", _f("Sao lùn đỏ (M-type)"), "red_dwarf"),
    (r"\bbinary star\b|\bsao đôi\b", "sun_type", _f("Hệ sao đôi"), "binary_star"),

    # --- Địa hình / thủy quyển ---
    (r"\bvolcanic\b|\bnúi lửa\b", "terrain", _f("Núi lửa hoạt động"), "volcanic"),
    (r"\bfrozen ocean\b|\bđại dương đóng băng\b|\bice sheet\b|\bbăng vĩnh cửu\b",
     "terrain", _f("Băng nguyên / băng hà"), "frozen_ocean"),
    (r"\bdesert\b|\bsa mạc\b|\barid\b|\bkhô hạn\b", "terrain", _f("Sa mạc đá/cát"), "desert"),
    (r"\bdeep ocean\b|\bhydrothermal vent\b|\bmạch nhiệt thủy\b",
     "terrain", _f("Đại dương sâu, mạch nhiệt thủy"), "hydrothermal_vent"),
    (r"\bkarst\b|\blimestone\b|\bnúi đá vôi\b", "terrain", _f("Núi đá vôi, hang động"), "karst"),
]

# Ngưỡng nhiệt độ trung bình (°C) -> (climate, biome). Sắp theo thứ tự giảm dần
# nhiệt độ; hàm chọn khoảng đầu tiên mà nhiệt độ khớp.
_TEMPERATURE_THRESHOLDS: list[tuple[float, str, str]] = [
    (60.0, "Cực nhiệt, thù địch", "Sa mạc đá nung"),
    (35.0, "Nhiệt đới khô nóng", "Cao nguyên/Sa mạc"),
    (15.0, "Ôn hòa", "Rừng/Đồng cỏ"),
    (0.0, "Lạnh, ẩm", "Rừng lá kim/Đài nguyên"),
    (-30.0, "Cực hàn, khô", "Băng nguyên"),
    (float("-inf"), "Băng giá tuyệt đối", "Băng vĩnh cửu không sự sống bề mặt"),
]


def _extract_temperature(text: str) -> Optional[float]:
    """Tìm số nhiệt độ trung bình (°C) trong text, trả về float hoặc None."""
    m = re.search(
        r"(-?\d+(?:\.\d+)?)\s?°?c\b(?:[^.]{0,40}\baverage\b)?|"
        r"\baverage\b[^.]{0,40}(-?\d+(?:\.\d+)?)\s?°?c\b",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _extract_moon_count(text: str) -> Optional[int]:
    m = re.search(r"\b(\d+)\s*moons?\b|\b(\d+)\s*mặt trăng\b", text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def analyze_physics(rule: dict) -> dict:
    """BUOC 2 - Suy luan thuoc tinh vat ly tu 1 quy luat khoa hoc tho.

    Chi dung regex/if-else thuan Python. Tra ve dict phang gom cac field vat
    ly da suy ra duoc, cong voi 1 khoa noi bo `_tags`: dict field -> tag
    chuan hoa (tieng Anh) cua hien tuong da khop, dung rieng cho
    check_rule_conflicts(). Khoa `_tags` bi loc bo truoc khi field nay cham
    vao bat ky dataclass schema nao.
    """
    corpus = " . ".join(
        filter(
            None,
            [
                rule.get("summary", ""),
                *rule.get("causal_sentences", []),
                *rule.get("key_facts", []),
                " ".join(rule.get("matched_keywords", []) or []),
            ],
        )
    ).lower()

    inferred: dict[str, Any] = {}
    tags: dict[str, str] = {}

    for pattern, field, value_fn, tag in PHYSICS_RULES:
        m = re.search(pattern, corpus, re.IGNORECASE)
        if m and field not in inferred:
            inferred[field] = value_fn(m)
            tags[field] = tag

    temp = _extract_temperature(corpus)
    if temp is not None:
        inferred["temperature_range"] = f"~{temp:.0f}C trung binh"
        tags["temperature_range"] = "temperature_average"
        for threshold, climate, biome in _TEMPERATURE_THRESHOLDS:
            if temp >= threshold:
                inferred.setdefault("climate", climate)
                inferred.setdefault("biome", biome)
                tags.setdefault("climate", "temperature_average")
                tags.setdefault("biome", "temperature_average")
                break

    moons = _extract_moon_count(corpus)
    if moons is not None:
        inferred["moon_count"] = moons
        tags["moon_count"] = "moon_count"

    inferred["_tags"] = tags
    return inferred


# ---------------------------------------------------------------------------
# KIỂM TRA CHÉO VỚI RULE LIBRARY (vẫn Python thuần — không LLM)
# ---------------------------------------------------------------------------

def check_rule_conflicts(
    inferred: dict, target_id: Optional[str], rule_library: Optional[RuleLibrary]
) -> list[str]:
    """So khop cac gia tri vat ly vua suy ra voi Rule Library.

    So khop dua tren `_tags` (canonical tag tieng Anh gan theo moi field o
    analyze_physics()), KHONG so khop tren value hien thi - value hien thi
    co the la tieng Viet nen so truc tiep de bo sot mau thuan thuc.

    Tra ve danh sach ghi chu mau thuan (validation notes). Rule Library luon
    duoc uu tien: neu co FORBIDDEN rule khop tag cua 1 field vua suy luan,
    field do bi loai khoi `inferred` (mutated in-place) va ghi chu lai ly do.
    """
    notes: list[str] = []
    tags = inferred.get("_tags", {})
    if not rule_library or not rule_library.rules:
        return notes

    for r in rule_library.rules:
        if r.target_id and target_id and r.target_id != target_id:
            continue
        if not r.attribute:
            continue

        rule_attr = r.attribute.lower().replace(" ", "_")

        for field, tag in list(tags.items()):
            if field not in inferred:
                continue  # da bi xoa boi 1 rule truoc do trong vong lap nay
            if rule_attr == tag or rule_attr in tag or tag in rule_attr:
                if r.rule_type == RuleType.FORBIDDEN:
                    notes.append(
                        f"Mau thuan: physics suy ra '{field}={inferred[field]}' (tag="
                        f"'{tag}') nhung Rule {r.rule_id} cam '{r.attribute}'. "
                        f"Da loai bo field, uu tien Rule Library."
                    )
                    del inferred[field]
                    del tags[field]

    return notes


# ---------------------------------------------------------------------------
# BƯỚC 2b — DỰNG TEMPLATE SCHEMA TỪ KẾT QUẢ PHYSICS
# ---------------------------------------------------------------------------

def build_template(
    rule: dict,
    target_type: str,
    target_id: Optional[str] = None,
    existing: Optional[dict] = None,
    physics: Optional[dict] = None,
) -> Any:
    """Khởi tạo (hoặc cập nhật) 1 dataclass schema mục tiêu, chỉ điền các field
    vật lý mà `analyze_physics()` suy ra được. Mọi field khác giữ nguyên
    None/rỗng — đây chính là các "trường còn trống" mà LLM ở Bước 3 sẽ lấp.

    `existing`: nếu Repo 1 đã có sẵn 1 bản ghi partial (vd đã có `name`,
    `species_id`...), truyền vào đây để không bị mất dữ liệu đã có — khớp
    nguyên tắc #2 của forge_blueprint.md ("không đụng vào trường đã có").

    `physics`: nếu đã tính sẵn (và đã lọc qua `check_rule_conflicts`), truyền
    vào đây để build_template không tự tính lại (và vô tình bỏ qua việc lọc
    theo Rule Library). Nếu None, tự tính bằng `analyze_physics(rule)` — chỉ
    dùng khi gọi build_template() độc lập, không qua forge_blueprint().
    """
    if target_type not in _TARGET_SCHEMA:
        raise ValueError(
            f"target_type '{target_type}' không hợp lệ. "
            f"Chọn 1 trong: {list(_TARGET_SCHEMA)}"
        )

    schema_cls = _TARGET_SCHEMA[target_type]
    if physics is None:
        physics = analyze_physics(rule)

    id_field = f"{target_type}_id"
    entity_id = target_id or (existing or {}).get(id_field) or rule.get("content_hash") or "UNKNOWN_ID"

    kwargs: dict[str, Any] = dict(existing or {})
    kwargs.setdefault(id_field, entity_id)
    kwargs.setdefault("name", kwargs.get("name") or entity_id)

    if target_type == "planet":
        physics_kwargs = {
            k: v
            for k, v in physics.items()
            if k in {"gravity", "temperature_range", "atmosphere", "sun_type", "moon_count"}
        }
        existing_physics = kwargs.get("physics_attributes")
        if isinstance(existing_physics, PhysicsAttributes):
            existing_physics_kwargs = asdict(existing_physics)
        elif isinstance(existing_physics, dict):
            existing_physics_kwargs = existing_physics
        else:
            existing_physics_kwargs = {}
        merged_physics = {**physics_kwargs, **{
            k: v for k, v in existing_physics_kwargs.items() if v is not None
        }}
        kwargs["physics_attributes"] = PhysicsAttributes(**merged_physics)

        for f in ("climate", "terrain", "biome"):
            if f in physics:
                kwargs.setdefault(f, physics[f])
    else:
        # Species / Creature / Flora: physics của "hành tinh mẹ" ảnh hưởng
        # tới môi trường sống (`habitat`) — vẫn chỉ là mapping trực tiếp,
        # không phải LLM suy luận tự do.
        if target_type in ("creature", "flora"):
            habitat_source = physics.get("biome") or physics.get("terrain")
            if habitat_source:
                kwargs.setdefault("habitat", habitat_source)

    # Field không thuộc schema (vd metadata thô của rule) không được lọt vào
    # constructor của dataclass, tránh TypeError.
    valid_fields = {f for f in schema_cls.__dataclass_fields__}
    kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}

    instance = schema_cls(**kwargs)
    return instance, physics


# ---------------------------------------------------------------------------
# HẠ TẦNG GỌI LLM (STUB — ĐIỂM CẮM THẬT SỰ LÀ GEMINI_POOL CỦA CHIMERA)
# ---------------------------------------------------------------------------

def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _call_llm_mock(system_prompt: str, user_payload: str) -> str:
    """Hàm GIẢ LẬP gọi LLM — KHÔNG gọi API thật.

    Đây là điểm cắm duy nhất cần thay bằng lời gọi thật tới `GEMINI_POOL`
    (theo convention CHIMERA hiện có ở các module khác: world_genesis.py,
    world_history.py...). Giữ nguyên signature (system_prompt, user_payload)
    -> str khi tích hợp thật, để không phải sửa logic gọi ở dưới.

    Ví dụ tích hợp thật (không chạy ở đây):

        from chimera.llm_pool import GEMINI_POOL
        response = GEMINI_POOL.generate(
            system_instruction=system_prompt,
            contents=user_payload,
        )
        return response.text

    Ở đây trả về placeholder có cấu trúc để pipeline downstream (tests,
    dry-run CI) không crash khi chưa cắm key thật.
    """
    logger.debug(
        "[_call_llm_mock] system_prompt=%d chars, user_payload=%d chars — "
        "MOCK MODE, chưa gọi LLM thật.",
        len(system_prompt),
        len(user_payload),
    )
    return "__LLM_MOCK_RESPONSE__"


# ---------------------------------------------------------------------------
# BƯỚC 3 — LLM LẤP TRƯỜNG HÌNH THÁI (dựa trên forge_blueprint.md)
# ---------------------------------------------------------------------------

def llm_fill_blueprint(
    template: Any,
    physics: dict,
    rule: dict,
    rule_library: Optional[RuleLibrary] = None,
) -> dict:
    """Gọi (giả lập) LLM theo `prompts/forge_blueprint.md` để lấp các trường
    còn trống của template (vd Morphology của Species/Creature) dựa trên
    physics đã suy luận ở Bước 2. LLM CHỈ được lấp field null, không được
    tạo entity mới hay sửa field đã có giá trị (ràng buộc nằm trong chính
    forge_blueprint.md, không lặp lại logic đó bằng Python ở đây).
    """
    system_prompt = _load_prompt("forge_blueprint.md")

    template_dict = asdict(template) if is_dataclass(template) else dict(template)

    user_payload = (
        f"JSON_TEMPLATE:\n{template_dict}\n\n"
        f"RAW_PHYSICS_DATA:\n{physics}\n\n"
        f"RULE_LIBRARY:\n{[asdict(r) for r in (rule_library.rules if rule_library else [])]}\n\n"
        f"SOURCE_RULE_META:\n"
        f"rule_type={rule.get('rule_type')}, content_hash={rule.get('content_hash')}"
    )

    _raw_response = _call_llm_mock(system_prompt, user_payload)

    # --- MOCK FILL: trong hệ thống thật, đây là bước parse JSON trả về từ
    # LLM (`json.loads(_raw_response)`) và merge đè lên các field null. Ở
    # mock mode, ta chỉ đảm bảo mọi field còn None có 1 giá trị placeholder
    # rõ ràng là "chưa được LLM lấp thật", để không lẫn với dữ liệu physics.
    filled = dict(template_dict)
    for key, value in filled.items():
        if value is None:
            filled[key] = f"<LLM_PENDING:{key}>"
        elif isinstance(value, dict):
            filled[key] = {
                sub_k: (sub_v if sub_v is not None else f"<LLM_PENDING:{key}.{sub_k}>")
                for sub_k, sub_v in value.items()
            }

    return filled


# ---------------------------------------------------------------------------
# BƯỚC 4 — LLM VIẾT FICTIONAL_DESCRIPTION (dựa trên forge_fiction.md)
# ---------------------------------------------------------------------------

def llm_write_fiction(
    complete_blueprint: dict,
    rule_library: Optional[RuleLibrary] = None,
) -> str:
    """Gọi (giả lập) LLM theo `prompts/forge_fiction.md` để viết đoạn văn
    miêu tả 150-300 từ, giọng field-notes khách quan-hư cấu, dựa trên
    blueprint ĐÃ HOÀN CHỈNH (không còn null) từ Bước 3.
    """
    system_prompt = _load_prompt("forge_fiction.md")

    user_payload = (
        f"COMPLETE_BLUEPRINT:\n{complete_blueprint}\n\n"
        f"RULE_LIBRARY:\n{[asdict(r) for r in (rule_library.rules if rule_library else [])]}"
    )

    _raw_response = _call_llm_mock(system_prompt, user_payload)

    if _raw_response == "__LLM_MOCK_RESPONSE__":
        name = (
            complete_blueprint.get("name")
            or complete_blueprint.get("planet_id")
            or complete_blueprint.get("species_id")
            or complete_blueprint.get("creature_id")
            or complete_blueprint.get("flora_id")
            or "Thực thể chưa định danh"
        )
        return (
            f"<LLM_PENDING: mô tả field-notes cho '{name}' — cần gọi GEMINI_POOL "
            f"thật với system_prompt forge_fiction.md để sinh 150-300 từ.>"
        )

    return _raw_response


# ---------------------------------------------------------------------------
# BƯỚC 5 — ORCHESTRATOR: rule khoa học -> Blueprint hoàn chỉnh cho MongoDB
# ---------------------------------------------------------------------------

def forge_blueprint(
    rule: dict,
    target_type: str = "planet",
    target_id: Optional[str] = None,
    existing: Optional[dict] = None,
    rule_library: Optional[RuleLibrary] = None,
) -> dict:
    """Entry point chính của T6.

    Args:
        rule: 1 quy luật khoa học thô (xem docstring đầu file cho shape).
        target_type: "planet" | "species" | "creature" | "flora".
        target_id: id thực thể mục tiêu nếu đã biết (vd đang bồi đắp cho 1
            planet có sẵn); nếu None, tự sinh từ content_hash của rule.
        existing: bản ghi partial đã có sẵn trong DB (nếu có) — các field đã
            có giá trị ở đây sẽ KHÔNG bị ghi đè bởi Bước 2/3.
        rule_library: Rule Library hiện có, dùng để validate chéo ở Bước 2
            và làm ràng buộc ngữ cảnh cho LLM ở Bước 3/4.

    Returns:
        dict Blueprint hoàn chỉnh, sẵn sàng `insert_one` vào MongoDB.
    """
    # Bước 2a: suy luận vật lý thuần Python.
    physics = analyze_physics(rule)

    # Bước 2b: kiểm tra chéo Rule Library TRƯỚC khi field lọt vào template
    # (Rule Library luôn ưu tiên hơn physics — nguyên tắc #5 forge_blueprint.md).
    entity_id = target_id or (existing or {}).get(f"{target_type}_id") or rule.get("content_hash")
    validation_notes = check_rule_conflicts(physics, entity_id, rule_library)

    # Bước 2c: dựng template chỉ với physics đã lọc sạch mâu thuẫn.
    template, physics = build_template(rule, target_type, target_id, existing, physics)

    # Bước 3: LLM (giả lập) lấp trường hình thái còn trống.
    filled_blueprint = llm_fill_blueprint(template, physics, rule, rule_library)

    # Bước 4: LLM (giả lập) viết fictional_description.
    fictional_description = llm_write_fiction(filled_blueprint, rule_library)

    # Bước 5: đóng gói Blueprint hoàn chỉnh cho MongoDB.
    blueprint = dict(filled_blueprint)
    blueprint["fictional_description"] = fictional_description
    blueprint["_forge_meta"] = {
        "target_type": target_type,
        "source_content_hash": rule.get("content_hash"),
        "source_rule_type": rule.get("rule_type"),
        "source_run_id": rule.get("run_id"),
        "inferred_physics": physics,
        "validation_notes": validation_notes,
    }

    return blueprint


# ---------------------------------------------------------------------------
# DEMO / SMOKE TEST
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[T6] %(message)s")

    demo_rule = {
        "content_hash": "hash_abc789",
        "rule_type": "climate",
        "url": "https://example.org/exoplanet-report",
        "title": "Báo cáo khí hậu hành tinh giả định P07",
        "summary": "Hành tinh có khí quyển mỏng, nhiệt độ trung bình -40°C, địa hình núi đá vôi.",
        "key_facts": [
            "Nhiệt độ trung bình -40°C.",
            "Khí quyển mỏng, chủ yếu Nitrogen.",
            "Địa hình chính là núi đá vôi (karst).",
        ],
        "causal_sentences": [
            "Vì khí quyển mỏng nên nhiệt lượng ban ngày thoát nhanh vào ban đêm.",
        ],
        "matched_keywords": ["thin atmosphere", "karst", "cold"],
        "run_id": "local_demo_run",
    }

    demo_rule_library = RuleLibrary(
        rules=[
            Rule(
                rule_id="R01",
                scope=RuleScope.PLANET,
                rule_type=RuleType.FORBIDDEN,
                target_id="hash_abc789",
                attribute="volcanic",
                description="Hành tinh P07 không được có địa hình núi lửa.",
            )
        ]
    )

    result = forge_blueprint(
        demo_rule,
        target_type="planet",
        rule_library=demo_rule_library,
    )

    import json

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
