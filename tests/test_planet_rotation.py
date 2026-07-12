"""
tests/test_planet_rotation.py — [SPEC_FIX_2_6][Coder 1 — lượt 2]
=====================================================================
Unit test cho phần "engine" của Planet-Type Rotation (mục 2.6) mà Coder 1
giao ở lượt 2 (sau khi Coder 3 hoàn tất interface missing_required_fields
trong t3_normalize.py): `t0_search.generate_queries_for_field()` (chữ ký
3 param mới) và `main._get_current_planet_archetype()` /
`main._advance_planet_cursor()` / `main._handle_planet_gate_result()`.

Test `config.PLANET_TYPE_CATALOG` / `config.LIBRARY_REQUIRED_FIELDS["planet"]`
(phần nền móng lượt 1) đã nằm ở tests/test_planet_rotation_config.py — KHÔNG
lặp lại ở đây.

Nếu môi trường thiếu dependency runtime của main.py/t0_search.py (httpx,
pymongo, google-generativeai, ...), các test liên quan tự SKIP thay vì
FAIL, theo đúng pattern đã dùng ở tests/test_main_time_budget.py — để
không chặn `python -m unittest discover tests/` trên máy chưa cài đủ
requirements.txt.
"""
from __future__ import annotations

import copy
import unittest

import config

try:
    import t0_search
    _T0_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - phụ thuộc môi trường CI (thiếu httpx)
    t0_search = None
    _T0_IMPORT_ERROR = e

try:
    import main
    _MAIN_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - phụ thuộc môi trường CI (thiếu pymongo/httpx/...)
    main = None
    _MAIN_IMPORT_ERROR = e


# =============================================================================
# 1. generate_queries_for_field() — chữ ký 3 param mới (t0_search.py)
# =============================================================================
@unittest.skipIf(t0_search is None, f"t0_search.py không import được: {_T0_IMPORT_ERROR}")
class TestGenerateQueriesForFieldNewSignature(unittest.TestCase):

    def test_generate_queries_for_field_new_signature(self):
        # 3 args bắt buộc: anchor_name, seed_kw, field_name.
        queries = t0_search.generate_queries_for_field(
            "crystal_world",
            "crystal_world planet concept art worldbuilding",
            "form_1_planet_foundation.planet_identity.terrain_patterns",
        )
        self.assertEqual(len(queries), 5)
        # Target_Concept = anchor_name + Context: seed_kw phải xuất hiện
        # trong ít nhất các query "concept art"/"design"/"reference sheet".
        target_concept = (
            "crystal_world + Context: crystal_world planet concept art worldbuilding"
        )
        self.assertIn(target_concept, queries[0])
        self.assertIn(target_concept, queries[1])
        self.assertIn(target_concept, queries[3])
        # Các query "worldbuilding description"/"fictional variant types"
        # dùng anchor_name trực tiếp (không lặp seed_kw).
        self.assertIn("crystal_world", queries[2])
        self.assertIn("crystal_world", queries[4])

    def test_generate_queries_for_field_rejects_old_2_param_call(self):
        # BREAKING CHANGE: gọi kiểu cũ (2 param) phải raise TypeError.
        with self.assertRaises(TypeError):
            t0_search.generate_queries_for_field("some_field_name")  # type: ignore[call-arg]


# =============================================================================
# 2-6. main.py rotation engine
# =============================================================================
@unittest.skipIf(main is None, f"main.py không import được trong môi trường này: {_MAIN_IMPORT_ERROR}")
class TestPlanetRotationEngine(unittest.TestCase):

    def _empty_blackbook(self) -> dict:
        return {"keywords": {}, "scrape_state": {}, "version": 1}

    def test_blackbook_init_planet_rotation(self):
        blackbook = self._empty_blackbook()
        rotation = main._get_current_planet_archetype(blackbook)
        self.assertEqual(rotation["cursor_index"], 0)
        self.assertIsNone(rotation["in_progress"])
        self.assertEqual(rotation["completed_this_week"], [])
        self.assertEqual(rotation["failed_aborted_log"], [])
        # Phải ghi lại vào chính blackbook (mutate in-place), không chỉ trả bản copy rời.
        self.assertIn("planet_rotation", blackbook)
        self.assertIs(blackbook["planet_rotation"], rotation)

    def test_blackbook_init_planet_rotation_idempotent(self):
        blackbook = self._empty_blackbook()
        rotation_1 = main._get_current_planet_archetype(blackbook)
        rotation_1["cursor_index"] = 5
        rotation_2 = main._get_current_planet_archetype(blackbook)
        # Lần gọi thứ 2 không được reset lại state đã có.
        self.assertEqual(rotation_2["cursor_index"], 5)

    def test_advance_cursor_wraps(self):
        blackbook = self._empty_blackbook()
        main._get_current_planet_archetype(blackbook)
        catalog_len = len(config.PLANET_TYPE_CATALOG)

        # Xoay đúng catalog_len - 1 lần đầu tiên phải tăng dần tuần tự.
        archetype_id = None
        for expected_idx in range(1, catalog_len):
            archetype_id = main._advance_planet_cursor(blackbook, config)
            self.assertEqual(
                blackbook["planet_rotation"]["cursor_index"], expected_idx
            )
            self.assertEqual(archetype_id, config.PLANET_TYPE_CATALOG[expected_idx])

        # Xoay thêm 1 lần nữa (lần thứ catalog_len) phải wrap về 0.
        archetype_id = main._advance_planet_cursor(blackbook, config)
        self.assertEqual(blackbook["planet_rotation"]["cursor_index"], 0)
        self.assertEqual(archetype_id, config.PLANET_TYPE_CATALOG[0])

    def test_retry_pending_no_cursor_advance(self):
        blackbook = self._empty_blackbook()
        rotation = main._get_current_planet_archetype(blackbook)
        rotation["in_progress"] = {
            "working_planet_id": "PLANET_TEST_01",
            "archetype_id": "jungle_world",
            "started_at": "2026-07-12T17:01:00Z",
            "status": "in_progress",
            "retry_count": 0,
            "fields_filled": [],
            "fields_pending": [],
        }
        cursor_before = rotation["cursor_index"]

        gate_result = {
            "reject_reason": "planet_required_fields_missing",
            "missing_required_fields": [
                "form_1_planet_foundation.planet_identity.terrain_patterns",
            ],
        }
        gate_report = {"reject_reason": gate_result["reject_reason"]}

        main._handle_planet_gate_result(
            blackbook, gate_result, gate_report, "PLANET_TEST_01", config,
        )

        rotation_after = blackbook["planet_rotation"]
        self.assertEqual(rotation_after["cursor_index"], cursor_before)
        self.assertIsNotNone(rotation_after["in_progress"])
        self.assertEqual(rotation_after["in_progress"]["status"], "retry_pending")
        self.assertEqual(rotation_after["in_progress"]["retry_count"], 1)
        self.assertEqual(
            rotation_after["in_progress"]["fields_pending"],
            gate_result["missing_required_fields"],
        )

    def test_failed_aborted_after_3_windows(self):
        blackbook = self._empty_blackbook()
        rotation = main._get_current_planet_archetype(blackbook)
        rotation["in_progress"] = {
            "working_planet_id": "PLANET_TEST_02",
            "archetype_id": "toxic_world",
            "started_at": "2026-07-10T18:00:00Z",
            "status": "in_progress",
            "retry_count": 2,  # đã reject 2 cửa sổ trước đó
            "fields_filled": [],
            "fields_pending": ["form_1_planet_foundation.planet_identity.terrain_patterns"],
        }
        cursor_before = rotation["cursor_index"]

        gate_result = {
            "reject_reason": "planet_required_fields_missing",
            "missing_required_fields": [
                "form_1_planet_foundation.planet_identity.terrain_patterns",
            ],
        }
        gate_report = {"reject_reason": gate_result["reject_reason"]}

        main._handle_planet_gate_result(
            blackbook, gate_result, gate_report, "PLANET_TEST_02", config,
        )

        rotation_after = blackbook["planet_rotation"]
        # Cửa sổ reject thứ 3 -> failed_aborted, cursor PHẢI xoay.
        self.assertNotEqual(rotation_after["cursor_index"], cursor_before)
        self.assertIsNone(rotation_after["in_progress"])
        self.assertEqual(len(rotation_after["failed_aborted_log"]), 1)
        log_entry = rotation_after["failed_aborted_log"][0]
        self.assertEqual(log_entry["working_planet_id"], "PLANET_TEST_02")
        self.assertEqual(log_entry["archetype_id"], "toxic_world")
        self.assertEqual(log_entry["retry_count"], 3)
        self.assertIn("aborted_at", log_entry)

    def test_completed_advances_cursor(self):
        blackbook = self._empty_blackbook()
        rotation = main._get_current_planet_archetype(blackbook)
        rotation["in_progress"] = {
            "working_planet_id": "PLANET_TEST_03",
            "archetype_id": "ocean_world",
            "started_at": "2026-07-12T10:00:00Z",
            "status": "in_progress",
            "retry_count": 0,
            "fields_filled": [],
            "fields_pending": [],
        }
        cursor_before = rotation["cursor_index"]

        gate_result = {"reject_reason": None, "missing_required_fields": []}
        gate_report = {"reject_reason": None}

        main._handle_planet_gate_result(
            blackbook, gate_result, gate_report, "PLANET_TEST_03", config,
        )

        rotation_after = blackbook["planet_rotation"]
        self.assertIsNone(rotation_after["in_progress"])
        self.assertIn("ocean_world", rotation_after["completed_this_week"])
        self.assertNotEqual(rotation_after["cursor_index"], cursor_before)

    def test_completed_this_week_no_duplicate(self):
        # Nếu 1 archetype hoàn thành 2 lần (không nên xảy ra bình thường,
        # nhưng đảm bảo không append trùng nếu id đã có sẵn trong list).
        blackbook = self._empty_blackbook()
        rotation = main._get_current_planet_archetype(blackbook)
        rotation["completed_this_week"] = ["ocean_world"]
        rotation["in_progress"] = {
            "working_planet_id": "PLANET_TEST_04",
            "archetype_id": "ocean_world",
            "started_at": "2026-07-12T10:00:00Z",
            "status": "in_progress",
            "retry_count": 0,
            "fields_filled": [],
            "fields_pending": [],
        }
        gate_result = {"reject_reason": None, "missing_required_fields": []}
        gate_report = {"reject_reason": None}
        main._handle_planet_gate_result(
            blackbook, gate_result, gate_report, "PLANET_TEST_04", config,
        )
        self.assertEqual(
            blackbook["planet_rotation"]["completed_this_week"].count("ocean_world"), 1
        )

    def test_retry_count_per_window_not_per_call(self):
        # retry_count đếm theo SỐ CỬA SỔ 25 PHÚT KHÁC NHAU (= số lần
        # run_pipeline_once() reject cùng 1 working planet), KHÔNG phải số
        # lần gọi API bên trong 1 cửa sổ. _handle_planet_gate_result() chỉ
        # được gọi tối đa 1 lần / chu kỳ pipeline cho working planet hiện
        # tại (main.py chỉ xử lý 1 document planet / chu kỳ), nên
        # retry_count += 1 mỗi lần gọi hàm này tự nhiên khớp đúng định
        # nghĩa "1 cửa sổ = 1 lần gọi".
        blackbook = self._empty_blackbook()
        rotation = main._get_current_planet_archetype(blackbook)
        rotation["in_progress"] = {
            "working_planet_id": "PLANET_TEST_05",
            "archetype_id": "hollow_world",
            "started_at": "2026-07-12T10:00:00Z",
            "status": "in_progress",
            "retry_count": 0,
            "fields_filled": [],
            "fields_pending": [],
        }
        gate_result = {
            "reject_reason": "planet_required_fields_missing",
            "missing_required_fields": ["form_1_planet_foundation.planet_identity.terrain_patterns"],
        }
        gate_report = {"reject_reason": gate_result["reject_reason"]}

        # Cửa sổ #1 (chu kỳ pipeline #1) reject.
        main._handle_planet_gate_result(blackbook, gate_result, gate_report, "PLANET_TEST_05", config)
        self.assertEqual(blackbook["planet_rotation"]["in_progress"]["retry_count"], 1)

        # Cửa sổ #2 (chu kỳ pipeline #2, riêng biệt) reject.
        main._handle_planet_gate_result(blackbook, gate_result, gate_report, "PLANET_TEST_05", config)
        self.assertEqual(blackbook["planet_rotation"]["in_progress"]["retry_count"], 2)


if __name__ == "__main__":
    unittest.main()
