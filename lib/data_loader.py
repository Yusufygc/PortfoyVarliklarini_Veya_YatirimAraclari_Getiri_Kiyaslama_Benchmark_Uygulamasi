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

MACRO_TTL_DAYS = 7
MACRO_CACHE_FILE = "macro_cache.pkl"


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
            try:
                with open(cache_file, "rb") as f:
                    cached = pickle.load(f)
                cached_symbols = set(cached.columns.tolist())
                if set(symbols).issubset(cached_symbols):
                    sliced = cached.loc[start:end, symbols]
                    # Cache geçerli: istenen başlangıç tarihini kapsıyor olmalı (7 gün tolerans)
                    if not sliced.empty and sliced.index[0] <= pd.Timestamp(start) + pd.Timedelta(days=7):
                        return sliced
            except Exception as exc:
                warnings.warn(
                    f"Fiyat cache okunamadı, bozuk dosya silinecek: {exc}",
                    UserWarning,
                    stacklevel=2,
                )
                try:
                    os.remove(cache_file)
                except OSError:
                    pass

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

    # Per-symbol retry: multi-symbol download bazı sembollerde tüm NaN dönerse tek tek dene
    for sym in symbols:
        if sym not in df.columns or df[sym].dropna().empty:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    retry = yf.download(sym, start=start, end=end, auto_adjust=True, progress=False)
                if not retry.empty:
                    close = retry["Close"] if "Close" in retry.columns else retry
                    if isinstance(close, pd.DataFrame):
                        close = close.iloc[:, 0]
                    df[sym] = close
            except Exception as exc:
                warnings.warn(
                    f"yfinance tek-sembol retry başarısız ({sym}): {exc}",
                    UserWarning,
                    stacklevel=2,
                )

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
        try:
            with open(cache_file, "rb") as f:
                existing = pickle.load(f)
            df_filled = pd.concat([existing, df_filled]).groupby(level=0).last()
        except Exception as exc:
            warnings.warn(
                f"Mevcut fiyat cache birleştirilemedi, bozuk dosya silinip yeniden yazılacak: {exc}",
                UserWarning,
                stacklevel=2,
            )
            try:
                os.remove(cache_file)
            except OSError:
                pass

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
    import os
    if not os.path.exists(filepath):
        return pd.DataFrame(columns=REQUIRED_TRANSACTION_COLS)
    df = pd.read_csv(filepath)
    missing = [c for c in REQUIRED_TRANSACTION_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"transactions.csv eksik sütunlar: {missing}. Beklenen: {REQUIRED_TRANSACTION_COLS}")
    _LEGACY_RENAME = {"Altin": "Gram Altin", "Gumus": "Gram Gumus"}
    df["Varlık Adı"] = df["Varlık Adı"].replace(_LEGACY_RENAME)

    invalid = set(df["İşlem Türü"].unique()) - VALID_ISLEM_TURLERI
    if invalid:
        raise ValueError(f"Geçersiz İşlem Türü değerleri: {invalid}. Geçerli: {VALID_ISLEM_TURLERI}")
    df["Tarih"] = pd.to_datetime(df["Tarih"], dayfirst=True)
    df["Fiyat"] = pd.to_numeric(df["Fiyat"], errors="raise")
    df["Miktar"] = pd.to_numeric(df["Miktar"], errors="raise")
    df["Komisyon"] = pd.to_numeric(df["Komisyon"], errors="raise").fillna(0)
    return df.sort_values("Tarih").reset_index(drop=True)


def _macro_stale(cache_path: str, key: str) -> bool:
    cache_file = os.path.join(cache_path, MACRO_CACHE_FILE)
    if not os.path.exists(cache_file):
        return True
    try:
        with open(cache_file, "rb") as f:
            cache = pickle.load(f)
    except Exception:
        return True
    entry = cache.get(key)
    if not entry:
        return True
    updated_at = entry.get("updated_at")
    if not updated_at:
        return True
    return (datetime.now() - updated_at).days >= MACRO_TTL_DAYS


def _update_macro_cache(cache_path: str, key: str, df: pd.DataFrame, source: str) -> None:
    os.makedirs(cache_path, exist_ok=True)
    cache_file = os.path.join(cache_path, MACRO_CACHE_FILE)
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                cache = pickle.load(f)
        except Exception:
            cache = {}
    cache[key] = {"df": df.copy(), "source": source, "updated_at": datetime.now()}
    with open(cache_file, "wb") as f:
        pickle.dump(cache, f)


def _upsert_csv(filepath: str, new_df: pd.DataFrame, key: str = "Tarih") -> None:
    """Mevcut CSV ile yeni df'yi birleştir, key sütunundaki duplicate'lerde son kayıt kazanır.
    Dosyaya dayfirst (GG.AA.YYYY) formatında yazar."""
    if os.path.exists(filepath):
        try:
            existing = pd.read_csv(filepath)
            existing[key] = pd.to_datetime(existing[key], dayfirst=True, errors="coerce")
        except Exception:
            existing = pd.DataFrame(columns=new_df.columns)
    else:
        existing = pd.DataFrame(columns=new_df.columns)

    new_df = new_df.copy()
    new_df[key] = pd.to_datetime(new_df[key], errors="coerce")

    merged = pd.concat([existing, new_df], ignore_index=True)
    merged = merged.dropna(subset=[key])
    merged = merged.drop_duplicates(subset=[key], keep="last").sort_values(key).reset_index(drop=True)
    merged[key] = merged[key].dt.strftime("%d.%m.%Y")

    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    merged.to_csv(filepath, index=False)


def load_cpi_series(filepath: str, cache_path: str = "data", auto_refresh: bool = True) -> pd.Series:
    if auto_refresh and _macro_stale(cache_path, "cpi"):
        try:
            from lib import macro_scraper
            df, src = macro_scraper.fetch_cpi_with_fallback(baseline_csv_path=filepath)
            _upsert_csv(filepath, df, key="Tarih")
            _update_macro_cache(cache_path, "cpi", df, src)
        except Exception as exc:
            warnings.warn(
                f"CPI scrape başarısız, mevcut CSV kullanılıyor: {exc}",
                UserWarning,
                stacklevel=2,
            )

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


def load_tcmb_rates(
    filepath: str,
    policy_rate_pct: float = None,
    cache_path: str = "data",
    auto_refresh: bool = True,
) -> pd.Series:
    """
    Tier 1: TTL dolmuşsa web scraping ile günceller (TCMB → EVDS → Bigpara).
    Tier 2: CSV dosyasından okur.
    Tier 3: policy_rate_pct sabitiyle günlük yıllık faiz serisi üretir.
    """
    if auto_refresh and _macro_stale(cache_path, "rate"):
        try:
            from lib import macro_scraper
            df, src = macro_scraper.fetch_policy_rate_with_fallback()
            _upsert_csv(filepath, df, key="Tarih")
            _update_macro_cache(cache_path, "rate", df, src)
        except Exception as exc:
            warnings.warn(
                f"Faiz scrape başarısız, mevcut CSV/sabit oran kullanılıyor: {exc}",
                UserWarning,
                stacklevel=2,
            )

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

    # Sabit oran -> günlük yıllık faiz oranı serisi.
    # Endeks üretimi build_deposit_series() içinde yapılır.
    start_dt = datetime(2015, 1, 1)
    end_dt = datetime.today()
    days = pd.date_range(start_dt, end_dt, freq="D")
    return pd.Series(policy_rate_pct, index=days, name="Faiz_Orani_Yillik_Pct")
