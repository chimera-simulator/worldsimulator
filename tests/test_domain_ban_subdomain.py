"""
tests/test_domain_ban_subdomain.py — Unit test cho P1-D (subdomain bypass fix)
trong domain_ban.py, theo mục 4 (ACCEPTANCE CRITERIA) của
SPEC_FIX_P1C_P1D_SearchFallback_DomainBan.md.

Chạy: python3 -m unittest tests.test_domain_ban_subdomain -v  (từ thư mục repo1/)
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain_ban import (
    is_domain_or_subdomain_in,
    is_academic_domain,
    force_unban_all,
    reset_test_domains,
)


class TestIsDomainOrSubdomainIn(unittest.TestCase):
    def test_subdomain_matches(self):
        self.assertTrue(is_domain_or_subdomain_in("m.esa.int", {"esa.int"}))

    def test_exact_match(self):
        self.assertTrue(is_domain_or_subdomain_in("esa.int", {"esa.int"}))

    def test_lookalike_suffix_does_not_match(self):
        # "myesa.int" chỉ trùng hậu tố ký tự với "esa.int", KHÔNG phải
        # subdomain thật (thiếu dấu chấm phân cách) -> phải là False.
        self.assertFalse(is_domain_or_subdomain_in("myesa.int", {"esa.int"}))

    def test_case_insensitive(self):
        self.assertTrue(is_domain_or_subdomain_in("M.ESA.INT", {"esa.int"}))

    def test_deep_subdomain_matches(self):
        self.assertTrue(is_domain_or_subdomain_in("a.b.esa.int", {"esa.int"}))

    def test_unrelated_domain_does_not_match(self):
        self.assertFalse(is_domain_or_subdomain_in("example.com", {"esa.int"}))

    def test_empty_domain_returns_false(self):
        self.assertFalse(is_domain_or_subdomain_in("", {"esa.int"}))


class TestIsAcademicDomainSubdomain(unittest.TestCase):
    def test_sciences_esa_int_is_academic(self):
        # Bug cụ thể nêu trong spec: trước đây trả False, giờ phải True.
        self.assertTrue(is_academic_domain("sciences.esa.int"))

    def test_m_nasa_gov_is_academic(self):
        self.assertTrue(is_academic_domain("m.nasa.gov"))

    def test_exact_blacklist_domain_still_academic(self):
        self.assertTrue(is_academic_domain("nasa.gov"))

    def test_edu_suffix_still_works(self):
        # ACADEMIC_DOMAIN_SUFFIXES check không bị đụng tới, phải còn hoạt động.
        self.assertTrue(is_academic_domain("mit.edu"))

    def test_non_academic_domain_stays_false(self):
        self.assertFalse(is_academic_domain("artstation.com"))


class TestForceUnbanAll(unittest.TestCase):
    def test_unbans_all_banned_domains(self):
        blackbook = {
            "bad-a.com": {"status": "banned", "failures": 5, "banned_until": "2099-01-01T00:00:00+00:00"},
            "bad-b.com": {"status": "banned", "failures": 3, "banned_until": "2099-01-01T00:00:00+00:00"},
            "good.com": {"status": "active", "failures": 0},
        }
        count = force_unban_all(blackbook)
        self.assertEqual(count, 2)
        self.assertEqual(blackbook["bad-a.com"]["status"], "active")
        self.assertEqual(blackbook["bad-a.com"]["failures"], 0)
        self.assertNotIn("banned_until", blackbook["bad-a.com"])
        self.assertEqual(blackbook["bad-b.com"]["status"], "active")
        # domain vốn đã active không bị đụng vào
        self.assertEqual(blackbook["good.com"]["status"], "active")

    def test_keeps_round_robin_and_adapter_label(self):
        blackbook = {
            "bad.com": {
                "status": "banned",
                "failures": 3,
                "banned_until": "2099-01-01T00:00:00+00:00",
                "skill": "tier2_reader",
                "adapter_label_valid_until": "2099-01-01T00:00:00+00:00",
                "round_robin_cursor": 7,
            },
        }
        force_unban_all(blackbook)
        # skill/adapter_label/round_robin_cursor phải được GIỮ NGUYÊN
        self.assertEqual(blackbook["bad.com"]["skill"], "tier2_reader")
        self.assertEqual(blackbook["bad.com"]["adapter_label_valid_until"], "2099-01-01T00:00:00+00:00")
        self.assertEqual(blackbook["bad.com"]["round_robin_cursor"], 7)

    def test_empty_blackbook_returns_zero(self):
        self.assertEqual(force_unban_all({}), 0)

    def test_no_banned_domains_returns_zero(self):
        blackbook = {"good.com": {"status": "active", "failures": 0}}
        self.assertEqual(force_unban_all(blackbook), 0)


class TestResetTestDomains(unittest.TestCase):
    def test_resets_only_listed_domains(self):
        blackbook = {
            "target.com": {
                "status": "banned", "failures": 3,
                "banned_until": "2099-01-01T00:00:00+00:00",
                "skill": "tier1_http",
                "adapter_label_valid_until": "2099-01-01T00:00:00+00:00",
            },
            "untouched.com": {
                "status": "banned", "failures": 3,
                "banned_until": "2099-01-01T00:00:00+00:00",
            },
        }
        count = reset_test_domains(blackbook, ["target.com"])
        self.assertEqual(count, 1)
        self.assertEqual(blackbook["target.com"]["status"], "active")
        self.assertEqual(blackbook["target.com"]["failures"], 0)
        self.assertNotIn("banned_until", blackbook["target.com"])
        self.assertNotIn("skill", blackbook["target.com"])
        self.assertNotIn("adapter_label_valid_until", blackbook["target.com"])
        # domain không nằm trong danh sách phải giữ nguyên trạng thái banned
        self.assertEqual(blackbook["untouched.com"]["status"], "banned")

    def test_nonexistent_domain_is_skipped(self):
        blackbook = {"exists.com": {"status": "active", "failures": 0}}
        count = reset_test_domains(blackbook, ["does-not-exist.com"])
        self.assertEqual(count, 0)

    def test_empty_domain_list_returns_zero(self):
        blackbook = {"exists.com": {"status": "banned", "failures": 3}}
        self.assertEqual(reset_test_domains(blackbook, []), 0)


if __name__ == "__main__":
    unittest.main()
