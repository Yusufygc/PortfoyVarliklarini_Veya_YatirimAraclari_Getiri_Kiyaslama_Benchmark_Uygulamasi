import warnings

import pandas as pd

# Sabitler `lib/constants.py`'de tutulur; geriye uyumluluk için yeniden export.
from constants import (
    USD_NATIVE_SYMBOLS,
    TL_NATIVE_SYMBOLS,
    GRAM_SYMBOLS,
    TROY_OZ_TO_GRAM,
)

__all__ = [
    "USD_NATIVE_SYMBOLS",
    "TL_NATIVE_SYMBOLS",
    "GRAM_SYMBOLS",
    "TROY_OZ_TO_GRAM",
    "normalize_to_100",
    "build_benchmark_series",
    "build_deposit_series",
]


def normalize_to_100(price_series: pd.Series, start_date: str) -> pd.Series:
    """
    Seriyi start_date'teki değere böler, 100 ile çarpar.
    start_date indexte yoksa en yakın sonraki iş gününü kullanır.
    """
    start_dt = pd.Timestamp(start_date)
    available = price_series.index[price_series.index >= start_dt]
    if available.empty:
        raise ValueError(f"normalize_to_100: {start_date} sonrası veri yok.")
    actual_start = available[0]
    base = price_series.loc[actual_start]
    if base == 0:
        raise ValueError(f"Baz değer sıfır ({actual_start}). Normalizasyon yapılamaz.")
    return price_series / base * 100


def _convert_to_tl(series: pd.Series, symbol: str, fx_usdtry: pd.Series) -> pd.Series:
    """USD bazlı sembolü TL'ye çevirir. GC=F ve SI=F için gram bazına da çevirir."""
    if symbol in USD_NATIVE_SYMBOLS:
        fx_aligned = fx_usdtry.reindex(series.index).ffill()
        tl = series * fx_aligned
        if symbol in GRAM_SYMBOLS:
            tl = tl / TROY_OZ_TO_GRAM  # USD/troy oz × TL/USD → TL/troy oz → TL/gram
        return tl
    return series


def _convert_to_usd(series: pd.Series, symbol: str, fx_usdtry: pd.Series) -> pd.Series:
    """TL bazlı sembolü USD'ye çevirir. GC=F ve SI=F için USD/gram'a çevirir."""
    if symbol in TL_NATIVE_SYMBOLS:
        fx_aligned = fx_usdtry.reindex(series.index).ffill()
        return series / fx_aligned
    if symbol in GRAM_SYMBOLS:
        return series / TROY_OZ_TO_GRAM  # USD/troy oz → USD/gram
    return series


def build_benchmark_series(
    symbols: list,
    start_date: str,
    end_date: str,
    prices: pd.DataFrame,
    fx_usdtry: pd.Series,
    cpi_series: pd.Series = None,
    currency: str = "TL",
) -> pd.DataFrame:
    """
    Her sembol için normalize edilmiş (başlangıç=100) seri döndürür.

    Args:
        currency: "TL" | "USD" | "REAL"
            - TL:   TL nominal (USD bazlı semboller × USDTRY)
            - USD:  USD bazlı (TL bazlı semboller ÷ USDTRY)
            - REAL: TL nominal, sonra TÜFE ile deflate

    Returns:
        DataFrame: index=Date, columns=symbols, values=normalized index
    """
    if prices.columns.duplicated().any():
        prices = prices.loc[:, ~prices.columns.duplicated(keep="first")]
    if isinstance(fx_usdtry, pd.DataFrame):
        fx_usdtry = fx_usdtry.iloc[:, 0]
    fx_usdtry = fx_usdtry[~fx_usdtry.index.duplicated(keep="first")]

    result = {}
    date_range = pd.date_range(start_date, end_date, freq="B")

    for sym in symbols:
        if sym not in prices.columns:
            continue

        raw = prices[sym].reindex(date_range).ffill().dropna()

        if currency == "TL":
            converted = _convert_to_tl(raw, sym, fx_usdtry)
        elif currency == "USD":
            converted = _convert_to_usd(raw, sym, fx_usdtry)
        elif currency == "REAL":
            if cpi_series is None:
                raise ValueError("REAL mod için cpi_series gerekli.")
            tl_series = _convert_to_tl(raw, sym, fx_usdtry)
            cpi_aligned = cpi_series.reindex(tl_series.index).ffill()
            cpi_base = cpi_aligned.iloc[0]
            converted = tl_series / (cpi_aligned / cpi_base)
        else:
            raise ValueError(f"Geçersiz currency: {currency}. 'TL', 'USD' veya 'REAL' olmalı.")

        converted = converted.dropna()
        try:
            normalized = normalize_to_100(converted, start_date)
            result[sym] = normalized
        except ValueError:
            continue

    return pd.DataFrame(result)


def build_deposit_series(
    tcmb_rates: pd.Series,
    start_date: str,
    end_date: str,
) -> pd.Series:
    """
    Mevduat faizini normalize edilmiş kümülatif getiri endeksine çevirir.
    tcmb_rates: günlük yıllık faiz oranı (%) serisi.
    Returns: pd.Series index=date, values=cumulative index (başlangıç=100)

    NOT: tcmb_rates start_date'ten sonra başlıyorsa bfill ileri bir oranı geriye
    yansıtır; bu durumda UserWarning basılır (sessiz hatalı yorum riski).
    """
    date_range = pd.date_range(start_date, end_date, freq="B")
    filled = tcmb_rates.reindex(date_range).ffill()
    if pd.isna(filled.iloc[0]):
        first_valid = tcmb_rates.first_valid_index()
        warnings.warn(
            f"Mevduat/faiz verisi {start_date}'i kapsamıyor (ilk veri: "
            f"{first_valid.date() if first_valid is not None else 'yok'}). "
            "Önceki dönem için sonraki bir oran geriye yansıtıldı (yaklaşık değer).",
            UserWarning, stacklevel=2,
        )
        filled = filled.bfill()
    daily_rates = (1 + filled / 100) ** (1 / 365) - 1
    cumulative = (1 + daily_rates).cumprod()
    cumulative = cumulative / cumulative.iloc[0] * 100
    cumulative.name = "Mevduat"
    return cumulative
