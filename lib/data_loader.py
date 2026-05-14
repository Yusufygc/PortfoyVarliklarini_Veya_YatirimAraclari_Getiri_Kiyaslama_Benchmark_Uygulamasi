import os
import json
import pickle
import warnings
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

REQUIRED_PORTFOLIO_COLS = ["Varlık Adı", "Alış Tarihi", "Alış Fiyatı", "Miktar", "Komisyon"]
REQUIRED_TRANSACTION_COLS = ["Tarih", "Varlık Adı", "İşlem Türü", "Fiyat", "Miktar", "Komisyon"]
VALID_ISLEM_TURLERI = {"ALIŞ", "SATIŞ", "NAKIT_GIRIS", "NAKIT_CIKIS"}
MAX_FORWARD_FILL_DAYS = 5
CACHE_START_TOLERANCE_DAYS = 7
CPI_EVDS_SERIES = "TP.FG.J0"
CPI_DBNOMICS_MOM_URL = "https://api.db.nomics.world/v22/series/TCMB/CPI/cpimtm?observations=1"


def _normalize_symbols(symbols: list) -> list:
    return list(dict.fromkeys(symbols))


def _set_yfinance_cache_location(cache_path: str) -> None:
    os.makedirs(cache_path, exist_ok=True)
    if hasattr(yf, "set_tz_cache_location"):
        yf_cache_path = os.path.join(cache_path, "yf_tz_cache")
        os.makedirs(yf_cache_path, exist_ok=True)
        yf.set_tz_cache_location(yf_cache_path)


def _validate_price_coverage(
    df: pd.DataFrame,
    symbols: list,
    start: str,
    end: str,
    tolerance_days: int = CACHE_START_TOLERANCE_DAYS,
) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError(f"Fiyat verisi bos: {start} - {end}.")

    symbols = _normalize_symbols(symbols)
    missing_cols = [sym for sym in symbols if sym not in df.columns]
    if missing_cols:
        raise ValueError(f"Fiyat verisinde eksik semboller var: {missing_cols}.")

    sliced = df.loc[start:end, symbols]
    if sliced.empty:
        raise ValueError(f"Fiyat verisi secilen aralikta bos: {start} - {end}.")

    start_limit = pd.Timestamp(start) + pd.Timedelta(days=tolerance_days)
    late_or_empty = []
    for sym in symbols:
        first_valid = sliced[sym].first_valid_index()
        if first_valid is None:
            late_or_empty.append(f"{sym}: veri yok")
        elif pd.Timestamp(first_valid) > start_limit:
            late_or_empty.append(f"{sym}: ilk veri {pd.Timestamp(first_valid).date()}")

    if late_or_empty:
        raise ValueError(
            "Fiyat verisi istenen baslangic tarihini kapsamiyor. "
            f"Istenen baslangic: {start}; " + "; ".join(late_or_empty)
        )

    return sliced


def fetch_prices(
    symbols: list,
    start: str,
    end: str,
    cache_path: str,
    max_cache_age_hours: int = 12,
    require_start_coverage: bool = True,
) -> pd.DataFrame:
    symbols = _normalize_symbols(symbols)
    _set_yfinance_cache_location(cache_path)
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
                    if require_start_coverage:
                        return _validate_price_coverage(sliced, symbols, start, end)
                    if not sliced.empty:
                        return sliced
            except ValueError as exc:
                warnings.warn(
                    f"Fiyat cache kapsami yetersiz, yfinance yeniden denenecek: {exc}",
                    UserWarning,
                    stacklevel=2,
                )
            except Exception as exc:
                warnings.warn(
                    f"Fiyat cache okunamadı, yfinance yeniden denenecek: {exc}",
                    UserWarning,
                    stacklevel=2,
                )

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

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                existing = pickle.load(f)
            df_filled = pd.concat([existing, df_filled]).groupby(level=0).last()
        except Exception as exc:
            warnings.warn(
                f"Mevcut fiyat cache birleştirilemedi, yeni cache yazılacak: {exc}",
                UserWarning,
                stacklevel=2,
            )

    with open(cache_file, "wb") as f:
        pickle.dump(df_filled, f)

    if require_start_coverage:
        return _validate_price_coverage(df_filled, symbols, start, end)
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


def load_cpi_series(filepath: str) -> pd.Series:
    df = pd.read_csv(filepath)
    if "Tarih" not in df.columns or "CPI_Endeks" not in df.columns:
        raise ValueError("cpi_turkey.csv 'Tarih' ve 'CPI_Endeks' sütunları içermeli.")
    df["Tarih"] = pd.to_datetime(df["Tarih"], dayfirst=True)
    s = df.set_index("Tarih")["CPI_Endeks"].sort_index()
    daily_idx = pd.date_range(s.index.min(), datetime.today(), freq="D")
    return s.reindex(daily_idx).ffill()


def _load_cpi_monthly(filepath: str) -> pd.Series:
    if not os.path.exists(filepath):
        return pd.Series(dtype="float64", name="CPI_Endeks")
    df = pd.read_csv(filepath)
    if "Tarih" not in df.columns or "CPI_Endeks" not in df.columns:
        raise ValueError("cpi_turkey.csv 'Tarih' ve 'CPI_Endeks' sutunlari icermeli.")
    df["Tarih"] = pd.to_datetime(df["Tarih"], dayfirst=True, errors="raise")
    df["CPI_Endeks"] = pd.to_numeric(df["CPI_Endeks"], errors="raise")
    series = df.dropna(subset=["Tarih", "CPI_Endeks"]).set_index("Tarih")["CPI_Endeks"]
    series.index = series.index.to_period("M").to_timestamp()
    return series.sort_index().groupby(level=0).last().rename("CPI_Endeks")


def _validate_cpi_monthly(series: pd.Series) -> pd.Series:
    series = series.dropna().sort_index()
    if series.empty:
        raise ValueError("CPI verisi bos.")
    if (series <= 0).any():
        raise ValueError("CPI_Endeks sifir veya negatif deger iceriyor.")
    return series


def _write_cpi_monthly(filepath: str, series: pd.Series) -> None:
    series = _validate_cpi_monthly(series)
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    df = series.reset_index()
    df.columns = ["Tarih", "CPI_Endeks"]
    df["Tarih"] = df["Tarih"].dt.strftime("%d.%m.%Y")
    df["CPI_Endeks"] = df["CPI_Endeks"].round(2)
    df.to_csv(filepath, index=False)


def _month_range(start_date: str, end_date: str) -> pd.DatetimeIndex:
    start = pd.Timestamp(start_date).to_period("M").to_timestamp()
    end = pd.Timestamp(end_date).to_period("M").to_timestamp()
    return pd.date_range(start, end, freq="MS")


def _required_cpi_month_range(start_date: str, end_date: str, today=None) -> pd.DatetimeIndex:
    start = pd.Timestamp(start_date).to_period("M").to_timestamp()
    end = pd.Timestamp(end_date).to_period("M").to_timestamp()
    current_month = pd.Timestamp(today or datetime.today()).to_period("M").to_timestamp()

    if end == current_month:
        end = current_month - pd.DateOffset(months=1)

    return pd.date_range(start, end, freq="MS")


def _format_month_span(months: pd.DatetimeIndex) -> str:
    if len(months) == 0:
        return "yok"
    if len(months) == 1:
        return months[0].strftime("%Y-%m")
    return f"{months[0].strftime('%Y-%m')} ... {months[-1].strftime('%Y-%m')}"


def _format_missing_months(months: pd.DatetimeIndex, max_items: int = 6) -> str:
    if len(months) == 0:
        return "yok"
    shown = ", ".join(m.strftime("%Y-%m") for m in months[:max_items])
    if len(months) > max_items:
        shown += ", ..."
    return shown


def _open_json(url: str, headers: dict = None, timeout: int = 30) -> dict:
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_cpi_from_evds(start_date: str, end_date: str, api_key: str = None) -> pd.Series:
    api_key = api_key or os.environ.get("EVDS_API_KEY") or os.environ.get("TCMB_EVDS_API_KEY")
    if not api_key:
        raise ValueError("EVDS API key bulunamadi. EVDS_API_KEY veya TCMB_EVDS_API_KEY ayarlanmali.")

    start = pd.Timestamp(start_date).strftime("%d-%m-%Y")
    end = pd.Timestamp(end_date).strftime("%d-%m-%Y")
    url = (
        f"https://evds3.tcmb.gov.tr/igmevdsms-dis/series={CPI_EVDS_SERIES}"
        f"&startDate={start}&endDate={end}&type=json"
    )
    data = _open_json(url, headers={"key": api_key})
    if str(data.get("status", "")) == "403":
        raise ValueError(data.get("message", "EVDS yetki hatasi."))

    rows = data.get("items") or data.get("data") or data.get("observations") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    values = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_value = row.get("Tarih") or row.get("DATE") or row.get("date")
        cpi_value = row.get(CPI_EVDS_SERIES) or row.get(CPI_EVDS_SERIES.replace(".", "_")) or row.get("TP_FG_J0")
        if cpi_value is None:
            numeric_keys = [
                k for k, v in row.items()
                if k not in {"Tarih", "DATE", "date", "UNIXTIME"} and v not in (None, "")
            ]
            if numeric_keys:
                cpi_value = row[numeric_keys[0]]
        if date_value is None or cpi_value in (None, ""):
            continue
        try:
            ts = pd.to_datetime(date_value, dayfirst=True).to_period("M").to_timestamp()
            values[ts] = float(str(cpi_value).replace(",", "."))
        except Exception:
            continue
    if not values:
        raise ValueError("EVDS CPI yaniti parse edilemedi.")
    return pd.Series(values).sort_index().rename("CPI_Endeks")


def _fetch_cpi_mom_from_dbnomics() -> pd.Series:
    data = _open_json(CPI_DBNOMICS_MOM_URL)
    docs = (((data.get("series") or {}).get("docs")) or [])
    if not docs:
        raise ValueError("DBnomics CPI aylik degisim serisi bulunamadi.")
    doc = docs[0]
    periods = doc.get("period") or []
    values = doc.get("value") or []
    result = {}
    for period, value in zip(periods, values):
        if value in (None, ""):
            continue
        result[pd.Period(period, freq="M").to_timestamp()] = float(value)
    if not result:
        raise ValueError("DBnomics CPI aylik degisim yaniti bos.")
    return pd.Series(result).sort_index().rename("CPI_MoM_Pct")


def _extend_cpi_with_monthly_changes(existing: pd.Series, monthly_change_pct: pd.Series) -> pd.Series:
    if existing.empty:
        raise ValueError("Aylik degisimlerden CPI uretmek icin en az bir mevcut CPI degeri gerekli.")
    result = existing.copy().sort_index()
    changes = monthly_change_pct.dropna().sort_index()

    for month in sorted(changes.index[changes.index < result.index.min()], reverse=True):
        next_month = month + pd.DateOffset(months=1)
        if next_month in result.index and month not in result.index:
            result.loc[month] = result.loc[next_month] / (1 + changes.loc[next_month] / 100)

    for month in changes.index[changes.index > result.index.max()]:
        prev_month = month - pd.DateOffset(months=1)
        if prev_month in result.index and month not in result.index:
            result.loc[month] = result.loc[prev_month] * (1 + changes.loc[month] / 100)

    return result.sort_index().rename("CPI_Endeks")


def ensure_cpi_coverage(filepath: str, start_date: str, end_date: str, api_key: str = None) -> pd.Series:
    existing = _load_cpi_monthly(filepath)
    requested_months = _month_range(start_date, end_date)
    required_months = _required_cpi_month_range(start_date, end_date)
    combined = existing.copy()
    update_error = None

    if len(required_months.difference(combined.index)) > 0:
        try:
            evds_series = _fetch_cpi_from_evds(start_date, end_date, api_key=api_key)
            combined = pd.concat([combined, evds_series]).groupby(level=0).last()
        except Exception as evds_exc:
            try:
                mom = _fetch_cpi_mom_from_dbnomics()
                combined = _extend_cpi_with_monthly_changes(combined, mom)
            except Exception as db_exc:
                update_error = f"EVDS: {evds_exc}; DBnomics: {db_exc}"

    missing = required_months.difference(combined.index)
    if len(missing) > 0:
        if not combined.empty:
            _write_cpi_monthly(filepath, _validate_cpi_monthly(combined))
        csv_last = combined.index.max().strftime("%Y-%m") if not combined.empty else "bos"
        current_month = pd.Timestamp(datetime.today()).to_period("M").to_timestamp()
        current_month_note = ""
        if requested_months[-1] == current_month and required_months[-1] < requested_months[-1]:
            current_month_note = (
                f" {requested_months[-1].strftime('%Y-%m')} henuz yayimlanmamis olabilir; "
                "son yayimlanan ay ileri tasinacak."
            )
        update_note = f" Otomatik kaynak uyarisi: {update_error}" if update_error else ""
        raise ValueError(
            "TUFE verisi secilen araligi kapsayacak sekilde guncellenemedi. "
            f"CSV son ayi: {csv_last}. "
            f"Gerekli resmi aylar: {_format_month_span(required_months)}. "
            f"Eksik aylar: {_format_missing_months(missing)}."
            f"{current_month_note}"
            f"{update_note}"
        )

    combined = _validate_cpi_monthly(combined)
    _write_cpi_monthly(filepath, combined)
    daily_idx = pd.date_range(combined.index.min(), datetime.today(), freq="D")
    return combined.reindex(daily_idx).ffill()


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

    # Sabit oran -> günlük yıllık faiz oranı serisi.
    # Endeks üretimi build_deposit_series() içinde yapılır.
    start_dt = datetime(2015, 1, 1)
    end_dt = datetime.today()
    days = pd.date_range(start_dt, end_dt, freq="D")
    return pd.Series(policy_rate_pct, index=days, name="Faiz_Orani_Yillik_Pct")
