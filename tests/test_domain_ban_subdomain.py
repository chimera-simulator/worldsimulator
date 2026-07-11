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

from domain_ban import is_domain_or_subdomain_in, is_academic_domain


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


if __name__ == "__main__":
    unittest.main()
