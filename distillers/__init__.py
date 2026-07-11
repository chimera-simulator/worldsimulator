"""
distillers/ — Strategy Pattern cho Gate 6.5 Library Distillation
====================================================================
Mỗi library_type có 1 class Distiller riêng (kế thừa
`BaseLibraryDistiller`), đăng ký thủ công trong `DistillerRegistry`
(xem `distillers/registry.py`). Package này cố tình để rỗng — import
trực tiếp từ các submodule (`distillers.base`, `distillers.registry`,
`distillers.species`, ...) thay vì re-export ở đây, để tránh side-effect
import ngoài ý muốn ở module-load time.
"""
from __future__ import annotations
