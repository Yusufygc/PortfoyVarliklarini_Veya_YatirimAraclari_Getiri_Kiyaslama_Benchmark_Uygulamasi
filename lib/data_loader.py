import os
import pickle
import warnings
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

REQUIRED_PORTFOLIO_COLS = ["Varlık Adı", "Alış Tarihi", "Alış Fiyatı", "Miktar", "Komisyon"]
REQUIRED_TRANSACTION_COLS = ["Tarih", "Varlık Adı", "İşlem Türü", "Fiyat", "Miktar", "Komisyon"]
VALID_ISLEM_TURLERI = {"ALIŞ", "SATIŞ", "NAKIT_GIRIS", "NAKIT_CIKIS"}
MAX_FORWARD_FILL_DAYS = 5


def fetch_prices(
    symbols: list,
    start: str,
    end: str,
    cache_path: str,
    max_cache_age_hours: int = 12,
) -> pd.DataFrame:
    cache_file = os.path.join(cache_path, "prices_cache.pkl")
    if os.path.exists(cache_file):
        age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))).total_seconds() / 3600
        if age_hours < max_cache_age_hours:
            with open(cache_file, "rb") as f:
                cached = pickle.load(f)
            cached_symbols = set(cached.columns.tolist())
            if set(symbols).issubset(cached_symbols):
                sliced = cached.loc[start:end, symbols]
                # Cache geçerli: istenen başlangıç tarihini kapsıyor olmalı (7 gün tolerans)
                if not sliced.empty and sliced.index[0] <= pd.Timestamp(start) + pd.Timedelta(days=7):
                    return sliced

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = yf.download(symbols, start=start, end=end, auto_adjust=True, progress=False)

    if isinstance(raw.columns, pd.MultiIndex):
        df = raw["Close"]
    else:
        df = raw[["Close"]] if len(symbols) == 1 else raw

    if len(symbols) == 1 and isinstance(df, pd.Series):
        df = df.to_frame(name=symbols[0])
    elif len(symbols) == 1:
        df.columns = symbols

    df = df.sort_index()

    # Forward-fill with gap warning
    gap_mask = df.isna().sum(axis=1) > 0
    df_filled = df.ffill(limit=MAX_FORWARD_FILL_DAYS)
    remaining_gaps = df_filled.isna().sum().sum()
    if remaining_gaps > 0:
        warnings.warn(
            f"{remaining_gaps} eksik değer {MAX_FORWARD_FILL_DAYS} iş günü sınırını aştı. "
            "Sembol veya tarih aralığını kontrol et.",
            UserWarning,
            stacklevel=2,
        )

    os.makedirs(cache_path, exist_ok=True)
    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            existing = pickle.load(f)
        df_filled = pd.concat([existing, df_filled]).groupby(level=0).last()

    with open(cache_file, "wb") as f:
        pickle.dump(df_filled, f)

    return df_filled.loc[start:end, [s for s in symbols if s in df_filled.columns]]


def load_portfolio_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    missing = [c for c in REQUIRED_PORTFOLIO_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"portfolio.csv eksik sütunlar: {missing}. Beklenen: {REQUIRED_PORTFOLIO_COLS}")
    df["Alış Tarihi"] = pd.to_datetime(df["Alış Tarihi"], dayfirst=True)
    df["Alış Fiyatı"] = pd.to_numeric(df["Alış Fiyatı"], errors="raise")
    df["Miktar"] = pd.to_numeric(df["Miktar"], errors="raise")
    df["Komisyon"] = pd.to_numeric(df["Komisyon"], errors="raise").fillna(0)
    return df.reset_index(drop=True)


def load_transactions_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    missing = [c for c in REQUIRED_TRANSACTION_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"transactions.csv eksik sütunlar: {missing}. Beklenen: {REQUIRED_TRANSACTION_COLS}")
    invalid = set(df["İşlem Türü"].unique()) - VALID_ISLEM_TURLERI
    if invalid:
        raise ValueError(f"Geçersiz İşlem Türü değerleri: {invalid}. Geçerli: {VALID_ISLEM_TURLERI}")
    df["Tarih"] = pd.to_datetime(df["Tarih"], dayfirst=True)
    df["Fiyat"] = pd.to_numeric(df["Fiyat"], errors="raise")
    df["Miktar"] = pd.to_numeric(df["Miktar"], errors="raise")
    df["Komisyon"] = pd.to_numeric(df["Komisyon"], errors="raise").fillna(0)
    return df.sort_values("Tarih").reset_index(drop=True)


def load_cpi_series(filepath: str) -> pd.Series:
    df = pd.read_csv(filepath)
    if "Tarih" not in df.columns or "CPI_Endeks" not in df.columns:
        raise ValueError("cpi_turkey.csv 'Tarih' ve 'CPI_Endeks' sütunları içermeli.")
    df["Tarih"] = pd.to_datetime(df["Tarih"], dayfirst=True)
    s = df.set_index("Tarih")["CPI_Endeks"].sort_index()
    daily_idx = pd.date_range(s.index.min(), datetime.today(), freq="D")
    return s.reindex(daily_idx).ffill()


def load_fx_series(pair: str, start: str, end: str, cache_path: str) -> pd.Series:
    df = fetch_prices([pair], start=start, end=end, cache_path=cache_path)
    return df[pair].dropna()


def load_tcmb_rates(filepath: str, policy_rate_pct: float = None) -> pd.Series:
    """
    Tier 3: CSV dosyasından okur. Yoksa policy_rate_pct sabitiyle günlük bileşik faiz üretir.
    """
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        if "Tarih" not in df.columns or "Faiz_Orani_Yillik_Pct" not in df.columns:
            raise ValueError("tcmb_rates.csv 'Tarih' ve 'Faiz_Orani_Yillik_Pct' sütunları içermeli.")
        df["Tarih"] = pd.to_datetime(df["Tarih"], dayfirst=True)
        s = df.set_index("Tarih")["Faiz_Orani_Yillik_Pct"].sort_index()
        daily_idx = pd.date_range(s.index.min(), datetime.today(), freq="D")
        return s.reindex(daily_idx).ffill()

    if policy_rate_pct is None:
        raise ValueError("tcmb_rates.csv bulunamadı ve policy_rate_pct verilmedi.")

    # Sabit oran → günlük bileşik faiz endeksi (başlangıç=100)
    start_dt = datetime(2015, 1, 1)
    end_dt = datetime.today()
    daily_rate = (1 + policy_rate_pct / 100) ** (1 / 365) - 1
    days = pd.date_range(start_dt, end_dt, freq="D")
    values = 100 * (1 + daily_rate) ** range(len(days))
    return pd.Series(values, index=days, name="Mevduat_Endeks")
