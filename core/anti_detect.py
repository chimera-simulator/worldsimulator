"""
core/anti_detect.py — Wrapper mỏng quanh curl_cffi.AsyncSession
================================================================
Tách riêng để adaptive_router.py không import curl_cffi trực tiếp.
Hiện tại tier4_stealth_tls.py đã self-contained — module này dành cho
extension sau (shared session pool, custom TLS params, v.v.).
"""
# Placeholder — extension point cho future anti-detect logic
