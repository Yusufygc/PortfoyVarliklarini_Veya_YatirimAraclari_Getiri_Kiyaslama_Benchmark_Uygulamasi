"""Paylaşılan sabitler: sembol kümeleri ve birim dönüşümleri.

`benchmark_engine` ve `portfolio_engine` her ikisi de buradan import eder.
Daha önce `portfolio_engine` `benchmark_engine`'den import ediyordu → çift yönlü
bağ riski. Ortak modül ile bağ kalktı.
"""
from __future__ import annotations

USD_NATIVE_SYMBOLS = {"GC=F", "SI=F"}
TL_NATIVE_SYMBOLS = {"XU100.IS", "USDTRY=X", "EURTRY=X"}
GRAM_SYMBOLS = {"GC=F", "SI=F"}
TROY_OZ_TO_GRAM = 31.1035
