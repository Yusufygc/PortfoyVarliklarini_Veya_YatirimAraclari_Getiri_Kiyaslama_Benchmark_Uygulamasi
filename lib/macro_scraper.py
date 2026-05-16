"""
Makro veri scraping: CPI / TÜFE / Politika Faizi.

Çoklu kaynak fallback zinciri (ilk başarılı kaynak kazanır):
  CPI:   TÜİK → TCMB EVDS → enflasyonverileri.com
  Faiz:  TCMB 1-Week Repo → TCMB EVDS → TCMB TR

Her scraper başarılı olursa `pd.DataFrame` (sütunlar: Tarih, <metric>) döner.
Hata → exception fırlat → orkestratör bir sonraki kaynağa geçer.
Hepsi düşerse RuntimeError; çağıran taraf (data_loader) mevcut CSV'ye düşer.

URL/selector'lar değişebileceği için modül başında sabit olarak tutulur.
Site yapısı değişirse buradan tek satır düzenlemekle güncellenebilir.
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
import warnings
from datetime import datetime
from typing import Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("macro_scraper")

HTTP_TIMEOUT = 15
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

URL_TCMB_INFLATION_DATA = "https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/Inflation+Data"
URL_TUIK_CPI_CATEGORY = "https://veriportali.tuik.gov.tr/Kategori/GetKategori?p=enflasyon-ve-fiyat-115&dil=1"
URL_EVDS_CPI = "https://evds2.tcmb.gov.tr/index.php?/evds/serieMarket/collapse_2/5949411/DataGroup/turkish/bie_aylik_tuketici_fiyat_end/"
URL_ENFLASYON_CPI = "https://www.enflasyonverileri.com/yillara-gore-enflasyon-tufe-endeksi.aspx"

URL_TCMB_1W_REPO_EN = "https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Core+Functions/Monetary+Policy/Central+Bank+Interest+Rates/1+Week+Repo"
URL_TCMB_1W_REPO_TR = "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Temel+Faaliyetler/Para+Politikasi/Merkez+Bankasinin+Faizleri/1+Hafta+Repo"
URL_EVDS_POLICY_RATE = "https://evds2.tcmb.gov.tr/index.php?/evds/serieMarket/collapse_2/5949411/DataGroup/turkish/bie_haftalikfaiz/"

URL_WORLDBANK_DEPOSIT_TR = (
    "https://api.worldbank.org/v2/country/TR/indicator/FR.INR.DPST"
    "?format=json&per_page=100"
)
URL_HESAPKURDU_DEPOSIT = "https://www.hesapkurdu.com/mevduat"

# CPI: en az 6 aylık veri ve son satır 60 günden eski olmamalı
MIN_CPI_ROWS = 6
MAX_CPI_AGE_DAYS = 60
# Faiz: en az 3 değişiklik kaydı, son kayıt 365 günden eski olmamalı
MIN_RATE_ROWS = 3
MAX_RATE_AGE_DAYS = 365


# ---------------------------------------------------------------------------
# HTTP yardımcısı
# ---------------------------------------------------------------------------

def _http_get(url: str, max_attempts: int = 3) -> requests.Response:
    """HTTP GET + retry. 429/5xx/timeout → backoff (2,4 sn). 4xx → no retry."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            resp = requests.get(
                url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT, allow_redirects=True
            )
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                raise requests.HTTPError(
                    f"HTTP {resp.status_code} for {url}", response=resp
                )
            resp.raise_for_status()
            return resp
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_exc = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status and 400 <= status < 500 and status != 429:
                raise
            if attempt < max_attempts - 1:
                wait = 2 ** attempt * 2
                logger.warning(
                    "HTTP %s attempt %d/%d failed (%s); retrying in %ds",
                    url, attempt + 1, max_attempts, exc, wait,
                )
                time.sleep(wait)
    raise last_exc


def _read_html_tables(html: str) -> list:
    """pd.read_html sarmalayıcısı: lxml flavor zorunlu, html5lib gerektirmez."""
    return pd.read_html(io.StringIO(html), decimal=",", thousands=".", flavor="lxml")


def _parse_tr_number(value) -> float:
    """'1.234,56' veya '1234,56' veya '1234.56' → float."""
    if value is None:
        raise ValueError("boş sayı")
    s = str(value).strip().replace("\xa0", "").replace(" ", "").replace("%", "")
    if not s or s.lower() in ("nan", "none", "-"):
        raise ValueError("boş sayı")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def _validate_cpi(df: pd.DataFrame, source: str) -> None:
    if df.empty or len(df) < MIN_CPI_ROWS:
        raise ValueError(f"{source}: yetersiz satır ({len(df)} < {MIN_CPI_ROWS})")
    if df["CPI_Endeks"].isna().any():
        raise ValueError(f"{source}: CPI_Endeks NaN içeriyor")
    if (df["CPI_Endeks"] <= 0).any():
        raise ValueError(f"{source}: CPI_Endeks ≤ 0 değer içeriyor")
    last = pd.to_datetime(df["Tarih"]).max()
    age = (datetime.today() - last).days
    if age > MAX_CPI_AGE_DAYS:
        raise ValueError(f"{source}: son CPI {age} gün eski (limit {MAX_CPI_AGE_DAYS})")


def _validate_rate(df: pd.DataFrame, source: str) -> None:
    if df.empty or len(df) < MIN_RATE_ROWS:
        raise ValueError(f"{source}: yetersiz satır ({len(df)} < {MIN_RATE_ROWS})")
    if df["Faiz_Orani_Yillik_Pct"].isna().any():
        raise ValueError(f"{source}: Faiz_Orani_Yillik_Pct NaN içeriyor")
    if (df["Faiz_Orani_Yillik_Pct"] < 0).any() or (df["Faiz_Orani_Yillik_Pct"] > 200).any():
        raise ValueError(f"{source}: faiz oranı makul aralık dışında")
    last = pd.to_datetime(df["Tarih"]).max()
    age = (datetime.today() - last).days
    if age > MAX_RATE_AGE_DAYS:
        raise ValueError(f"{source}: son faiz {age} gün eski (limit {MAX_RATE_AGE_DAYS})")


# ---------------------------------------------------------------------------
# CPI scraper'ları
# ---------------------------------------------------------------------------

def scrape_tcmb_cpi_changes() -> pd.DataFrame:
    """
    TCMB Inflation Data sayfasından aylık TÜFE MoM% değişimini çeker.

    Sayfa endeks değeri yayımlamaz; sadece YoY% ve MoM% kolonları vardır.
    Dönen df sütunları: Tarih (ay başı), CPI_MoM_Pct, CPI_YoY_Pct.
    Endeks değeri elde etmek için `tcmb_changes_to_index()` yardımcısı kullanılır.
    """
    resp = _http_get(URL_TCMB_INFLATION_DATA)
    soup = BeautifulSoup(resp.text, "html.parser")

    table = None
    for t in soup.find_all("table"):
        # CPI tablosu summary attribute veya yakındaki h2 ile ayırt edilebilir
        summary = (t.get("summary") or "").lower()
        if "consumer price" in summary or "cpi" in summary:
            table = t
            break
    if table is None:
        # Fallback: önceki h2 başlığında "Consumer Price Index" geçen ilk tablo
        for h2 in soup.find_all("h2"):
            if "Consumer Price Index" in h2.get_text():
                table = h2.find_next("table")
                if table is not None:
                    break
    if table is None:
        raise RuntimeError("TCMB CPI: Consumer Price Index tablosu bulunamadı")

    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        date_str = cells[0]
        # Format: "MM-YYYY" (örn. "04-2026")
        m = re.match(r"^(\d{2})-(\d{4})$", date_str)
        if not m:
            continue
        month, year = int(m.group(1)), int(m.group(2))
        try:
            yoy = _parse_tr_number(cells[1])
            mom = _parse_tr_number(cells[2])
        except ValueError:
            continue
        rows.append((pd.Timestamp(year=year, month=month, day=1), mom, yoy))

    if not rows:
        raise RuntimeError("TCMB CPI: geçerli MoM satırı bulunamadı")

    df = pd.DataFrame(rows, columns=["Tarih", "CPI_MoM_Pct", "CPI_YoY_Pct"])
    df = df.sort_values("Tarih").reset_index(drop=True)
    return df


def tcmb_changes_to_index(changes_df: pd.DataFrame, baseline_csv_path: str) -> pd.DataFrame:
    """
    TCMB'den çekilen MoM% serisini, mevcut CSV'deki son endeks değeri baseline alınarak
    compound ile endeks serisine çevirir. Yalnızca baseline'dan SONRA gelen aylar üretilir.
    """
    if not os.path.exists(baseline_csv_path):
        raise RuntimeError(f"baseline CSV yok: {baseline_csv_path}")

    base = pd.read_csv(baseline_csv_path)
    base["Tarih"] = pd.to_datetime(base["Tarih"], dayfirst=True)
    base = base.sort_values("Tarih").reset_index(drop=True)
    if base.empty or "CPI_Endeks" not in base.columns:
        raise RuntimeError("baseline CSV boş veya CPI_Endeks yok")

    last_date = base["Tarih"].iloc[-1]
    last_index = float(base["CPI_Endeks"].iloc[-1])

    fwd = changes_df[changes_df["Tarih"] > last_date].sort_values("Tarih").reset_index(drop=True)
    if fwd.empty:
        # Baseline güncel; sadece son satırı geri döndür
        return pd.DataFrame({"Tarih": [last_date], "CPI_Endeks": [last_index]})

    rows = []
    current = last_index
    for _, r in fwd.iterrows():
        current = current * (1.0 + r["CPI_MoM_Pct"] / 100.0)
        rows.append((r["Tarih"], round(current, 2)))
    return pd.DataFrame(rows, columns=["Tarih", "CPI_Endeks"])


def scrape_tcmb_cpi(baseline_csv_path: str) -> pd.DataFrame:
    """
    TCMB Inflation Data → MoM% → mevcut CSV baseline + compound = endeks.
    Sadece baseline'dan sonra gelen yeni ayları üretir (boş olabilir).
    """
    changes = scrape_tcmb_cpi_changes()
    df = tcmb_changes_to_index(changes, baseline_csv_path)
    # Yalnızca yeni satırlar varsa validate; baseline güncelse tek satırla kabul et
    if len(df) >= MIN_CPI_ROWS:
        _validate_cpi(df, "TCMB-CPI")
    else:
        # En az 1 satır, en güncel ay 60 günden eski değil
        last = pd.to_datetime(df["Tarih"]).max()
        age = (datetime.today() - last).days
        if age > MAX_CPI_AGE_DAYS:
            raise ValueError(f"TCMB-CPI: son CPI {age} gün eski (limit {MAX_CPI_AGE_DAYS})")
    return df


def scrape_tuik_cpi() -> pd.DataFrame:
    """
    TÜİK Tüketici Fiyat Endeksi - aylık genel endeks.

    NOT: data.tuik.gov.tr / veriportali.tuik.gov.tr sayfaları JS-render kullanıyor.
    Statik HTML scraping çoğunlukla başarısız olur; o durumda fallback'e geçilir.
    """
    resp = _http_get(URL_TUIK_CPI_CATEGORY)
    soup = BeautifulSoup(resp.text, "html.parser")

    bulten_link = None
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if "Tüketici Fiyat" in text and "Endeks" in text:
            href = a["href"]
            if href.startswith("/"):
                href = "https://veriportali.tuik.gov.tr" + href
            bulten_link = href
            break
    if not bulten_link:
        raise RuntimeError("TÜİK: TÜFE bülten linki bulunamadı (JS-render sayfası olabilir)")

    bulten_resp = _http_get(bulten_link)

    xlsx_link = None
    bulten_soup = BeautifulSoup(bulten_resp.text, "html.parser")
    for a in bulten_soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith((".xls", ".xlsx")) and ("endeks" in href.lower() or "tufe" in href.lower()):
            if href.startswith("/"):
                href = "https://veriportali.tuik.gov.tr" + href
            xlsx_link = href
            break

    if xlsx_link:
        xlsx_resp = _http_get(xlsx_link)
        df = _parse_tuik_xlsx(xlsx_resp.content)
    else:
        tables = _read_html_tables(bulten_resp.text)
        df = _parse_tuik_html_table(tables)

    _validate_cpi(df, "TÜİK")
    return df


def _parse_tuik_xlsx(content: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(content), header=None)
    header_row = None
    for i, row in raw.iterrows():
        cells = [str(c) for c in row.values]
        joined = " ".join(cells).lower()
        if ("yıl" in joined or "yil" in joined) and ("ay" in joined or "endeks" in joined):
            header_row = i
            break
    if header_row is None:
        raise RuntimeError("TÜİK Excel: başlık satırı bulunamadı")
    df = pd.read_excel(io.BytesIO(content), header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    return _normalize_year_month_to_cpi(df)


def _parse_tuik_html_table(tables: list) -> pd.DataFrame:
    for t in tables:
        cols = [str(c).lower() for c in t.columns]
        joined = " ".join(cols)
        if ("yıl" in joined or "yil" in joined) and "ay" in joined and "endeks" in joined:
            return _normalize_year_month_to_cpi(t)
    raise RuntimeError("TÜİK HTML: TÜFE tablosu bulunamadı")


def _normalize_year_month_to_cpi(df: pd.DataFrame) -> pd.DataFrame:
    """Yıl/Ay/Endeks kolonlarını standart Tarih/CPI_Endeks formuna çevir."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    yil_col = next((c for c in df.columns if c.lower() in ("yıl", "yil", "year")), None)
    ay_col = next((c for c in df.columns if c.lower() in ("ay", "month")), None)
    endeks_col = next((c for c in df.columns if "endeks" in c.lower() or "index" in c.lower()), None)

    if not (yil_col and ay_col and endeks_col):
        raise RuntimeError(f"TÜİK normalize: sütun bulunamadı (kolonlar: {list(df.columns)})")

    df = df[[yil_col, ay_col, endeks_col]].dropna()
    df.columns = ["Yil", "Ay", "CPI_Endeks"]

    ay_map = {
        "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5,
        "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
        "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
    }
    def _ay_to_int(v):
        s = str(v).strip().lower()
        if s.isdigit():
            return int(s)
        return ay_map.get(s)

    df["Ay_Int"] = df["Ay"].map(_ay_to_int)
    df = df.dropna(subset=["Ay_Int"])
    df["Yil"] = df["Yil"].astype(int)
    df["Ay_Int"] = df["Ay_Int"].astype(int)
    df["Tarih"] = pd.to_datetime(df["Yil"].astype(str) + "-" + df["Ay_Int"].astype(str).str.zfill(2) + "-01")
    df["CPI_Endeks"] = df["CPI_Endeks"].apply(_parse_tr_number)
    return df[["Tarih", "CPI_Endeks"]].sort_values("Tarih").reset_index(drop=True)


def scrape_evds_cpi() -> pd.DataFrame:
    """TCMB EVDS web - bie_aylik_tuketici_fiyat_end serisi (HTML tablosu)."""
    resp = _http_get(URL_EVDS_CPI)
    tables = _read_html_tables(resp.text)
    df = None
    for t in tables:
        cols = [str(c).lower() for c in t.columns]
        if any("tarih" in c for c in cols) and any("endeks" in c or "tüfe" in c or "tufe" in c for c in cols):
            df = t.copy()
            break
    if df is None:
        raise RuntimeError("EVDS: TÜFE tablosu bulunamadı")

    tarih_col = next(c for c in df.columns if "tarih" in str(c).lower())
    endeks_col = next(c for c in df.columns if "endeks" in str(c).lower() or "tüfe" in str(c).lower() or "tufe" in str(c).lower())
    out = pd.DataFrame({
        "Tarih": pd.to_datetime(df[tarih_col], errors="coerce"),
        "CPI_Endeks": df[endeks_col].apply(lambda v: _parse_tr_number(v) if pd.notna(v) else None),
    })
    out = out.dropna().sort_values("Tarih").reset_index(drop=True)
    _validate_cpi(out, "EVDS")
    return out


def scrape_enflasyon_cpi() -> pd.DataFrame:
    """Aggregator: enflasyonverileri.com — aylık TÜFE endeksi."""
    resp = _http_get(URL_ENFLASYON_CPI)
    tables = _read_html_tables(resp.text)

    df = None
    for t in tables:
        cols = [str(c).lower() for c in t.columns]
        if any("yıl" in c or "yil" in c for c in cols) and any("endeks" in c for c in cols):
            df = t.copy()
            break
        if any("ay" in c for c in cols) and any("endeks" in c for c in cols):
            df = t.copy()
            break

    if df is None:
        raise RuntimeError("enflasyonverileri.com: TÜFE endeks tablosu bulunamadı")

    out = _normalize_year_month_to_cpi(df)
    _validate_cpi(out, "enflasyonverileri")
    return out


# ---------------------------------------------------------------------------
# Politika faizi scraper'ları
# ---------------------------------------------------------------------------

def _scrape_tcmb_1week_repo_from(url: str, source: str) -> pd.DataFrame:
    """TCMB '1 Week Repo' / '1 Hafta Repo' sayfasından tarihçeyi çek.

    TCMB sayfası `<table id="midTable">` kullanır; başlık satırı `<th>` değil
    `<td>` olduğu için pd.read_html çoğunlukla algılayamaz. BeautifulSoup ile
    doğrudan parse edilir.

    Tablo formatı: DATE | Borrowing | Lending. Lending sütunu politika faizidir
    (Borrowing genelde '-' boş). Tarih DD.MM.YYYY formatında.
    """
    resp = _http_get(url)
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", id="midTable") or soup.find("table")
    if table is None:
        raise RuntimeError(f"{source}: faiz tablosu bulunamadı")

    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        date_str = cells[0]
        if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
            continue
        borrowing = cells[1] if len(cells) > 1 else "-"
        lending = cells[2] if len(cells) > 2 else "-"
        # Lending önce, boşsa Borrowing
        rate_str = lending if lending and lending != "-" else borrowing
        if not rate_str or rate_str == "-":
            continue
        try:
            rate = _parse_tr_number(rate_str)
        except ValueError:
            continue
        rows.append((date_str, rate))

    if not rows:
        raise RuntimeError(f"{source}: geçerli faiz satırı bulunamadı")

    out = pd.DataFrame(rows, columns=["Tarih", "Faiz_Orani_Yillik_Pct"])
    out["Tarih"] = pd.to_datetime(out["Tarih"], dayfirst=True, errors="coerce")
    out = out.dropna().sort_values("Tarih").reset_index(drop=True)
    _validate_rate(out, source)
    return out


def scrape_tcmb_policy_rate() -> pd.DataFrame:
    """TCMB resmi '1 Week Repo' (EN) sayfası — politika faizi tarihçesi."""
    return _scrape_tcmb_1week_repo_from(URL_TCMB_1W_REPO_EN, "TCMB-EN")


def scrape_tcmb_policy_rate_tr() -> pd.DataFrame:
    """TCMB '1 Hafta Repo' (TR) sayfası — EN sürümü düşerse fallback."""
    return _scrape_tcmb_1week_repo_from(URL_TCMB_1W_REPO_TR, "TCMB-TR")


def scrape_evds_policy_rate() -> pd.DataFrame:
    """TCMB EVDS bie_haftalikfaiz — haftalık repo faizi serisi."""
    resp = _http_get(URL_EVDS_POLICY_RATE)
    tables = _read_html_tables(resp.text)

    df = None
    for t in tables:
        cols = [str(c).lower() for c in t.columns]
        if any("tarih" in c for c in cols) and any("faiz" in c or "oran" in c for c in cols):
            df = t.copy()
            break
    if df is None:
        raise RuntimeError("EVDS faiz: tablo bulunamadı")

    tarih_col = next(c for c in df.columns if "tarih" in str(c).lower())
    faiz_col = next(c for c in df.columns if "faiz" in str(c).lower() or "oran" in str(c).lower())
    out = pd.DataFrame({
        "Tarih": pd.to_datetime(df[tarih_col], dayfirst=True, errors="coerce"),
        "Faiz_Orani_Yillik_Pct": df[faiz_col].apply(
            lambda v: _parse_tr_number(v) if pd.notna(v) else None
        ),
    })
    out = out.dropna().sort_values("Tarih").reset_index(drop=True)
    _validate_rate(out, "EVDS")
    return out


# ---------------------------------------------------------------------------
# Orkestratörler
# ---------------------------------------------------------------------------

def fetch_cpi_with_fallback(baseline_csv_path: str = None) -> Tuple[pd.DataFrame, str]:
    """CPI için fallback zincirini çalıştırır. (df, source_name) döner.

    `baseline_csv_path` verilirse TCMB MoM% → endeks dönüşümü için kullanılır
    (önerilen kullanım). Verilmezse TCMB scraper'ı atlanır.
    """
    sources = []
    if baseline_csv_path:
        sources.append(("TCMB", lambda: scrape_tcmb_cpi(baseline_csv_path)))
    sources += [
        ("TUIK", scrape_tuik_cpi),
        ("EVDS", scrape_evds_cpi),
        ("enflasyonverileri", scrape_enflasyon_cpi),
    ]
    errors = []
    for name, fn in sources:
        try:
            df = fn()
            return df, name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            logger.warning("CPI scrape kaynağı %s başarısız: %s", name, exc)
            warnings.warn(f"CPI scrape kaynağı {name} başarısız: {exc}", UserWarning, stacklevel=2)
    raise RuntimeError("Tüm CPI kaynakları başarısız:\n" + "\n".join(errors))


def fetch_policy_rate_with_fallback() -> Tuple[pd.DataFrame, str]:
    """Politika faizi için fallback zincirini çalıştırır."""
    sources = [
        ("TCMB-EN", scrape_tcmb_policy_rate),
        ("TCMB-TR", scrape_tcmb_policy_rate_tr),
        ("EVDS", scrape_evds_policy_rate),
    ]
    errors = []
    for name, fn in sources:
        try:
            df = fn()
            return df, name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            logger.warning("Faiz scrape kaynağı %s başarısız: %s", name, exc)
            warnings.warn(f"Faiz scrape kaynağı {name} başarısız: {exc}", UserWarning, stacklevel=2)
    raise RuntimeError("Tüm faiz kaynakları başarısız:\n" + "\n".join(errors))


# ---------------------------------------------------------------------------
# Mevduat faizi (gerçek bankaların TL mevduat ortalama brüt faizi)
# ---------------------------------------------------------------------------

def scrape_worldbank_deposit_rate() -> pd.DataFrame:
    """World Bank Open Data — Turkey Deposit Interest Rate (FR.INR.DPST).
    Yıllık brüt faiz, kaynak TCMB. Auth gerektirmez."""
    resp = _http_get(URL_WORLDBANK_DEPOSIT_TR)
    payload = resp.json()
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError("WorldBank: beklenmeyen JSON yapısı")
    observations = payload[1] or []
    rows = []
    for obs in observations:
        value = obs.get("value")
        year = obs.get("date")
        if value is None or year is None:
            continue
        try:
            rate = float(value)
        except (TypeError, ValueError):
            continue
        rows.append((pd.Timestamp(f"{year}-12-31"), rate))
    if not rows:
        raise RuntimeError("WorldBank: dolu satır yok")
    df = pd.DataFrame(rows, columns=["Tarih", "Faiz_Orani_Yillik_Pct"])
    df = df.sort_values("Tarih").reset_index(drop=True)
    # Yıllık kayıt 365 günden eski olabilir; _validate_rate'i atlayıp özel kontrol:
    if len(df) < MIN_RATE_ROWS:
        raise ValueError(f"WorldBank: yetersiz satır ({len(df)} < {MIN_RATE_ROWS})")
    if (df["Faiz_Orani_Yillik_Pct"] < 0).any() or (df["Faiz_Orani_Yillik_Pct"] > 200).any():
        raise ValueError("WorldBank: faiz oranı makul aralık dışında")
    return df


def scrape_hesapkurdu_deposit_rate_today() -> pd.DataFrame:
    """Hesapkurdu.com güncel banka mevduat faizi tablosu — bugünkü ortalama.
    Tek satırlık DataFrame döner. Defansif kolon tespiti: önce isim, sonra
    yüzde-işaretli sayı kolonunu heuristik olarak bul."""
    resp = _http_get(URL_HESAPKURDU_DEPOSIT)
    tables = _read_html_tables(resp.text)

    target, faiz_col = None, None
    # 1) isim eşleşmesi
    for t in tables:
        for col in t.columns:
            if "faiz oran" in str(col).lower():
                target, faiz_col = t, col
                break
        if target is not None:
            break

    # 2) heuristik: yüzde-işaretli ya da virgüllü ondalık sayı kolonu
    if target is None:
        for t in tables:
            for col in t.columns:
                sample = t[col].astype(str).head(15)
                hits = sample.str.contains(r"%|\d+,\d+", regex=True, na=False).sum()
                if hits >= 3:
                    target, faiz_col = t, col
                    break
            if target is not None:
                break

    if target is None:
        raise RuntimeError("Hesapkurdu: yüzdesel faiz kolonu içeren tablo bulunamadı")

    rates = []
    for raw in target[faiz_col]:
        try:
            rates.append(_parse_tr_number(raw))
        except ValueError:
            continue
    if len(rates) < 3:
        raise RuntimeError(f"Hesapkurdu: yetersiz faiz satırı ({len(rates)} < 3)")
    avg = sum(rates) / len(rates)
    if avg < 0 or avg > 200:
        raise ValueError(f"Hesapkurdu: ortalama faiz makul aralık dışında ({avg})")
    today = pd.Timestamp(datetime.today().date())
    return pd.DataFrame([(today, avg)], columns=["Tarih", "Faiz_Orani_Yillik_Pct"])


def _extend_deposit_rate_linear(
    df: pd.DataFrame, gap_threshold_days: int = 180
) -> pd.DataFrame:
    """Ardışık iki nokta arası `gap_threshold_days`+ ise lineer interpolasyon
    noktaları ekler. Yaklaşık değer; gerçek TCMB verisi değil — UserWarning basılır.

    WorldBank yıllık + Hesapkurdu bugün → arada 1-2 yıl boşluk oluyor; ffill
    eski oranı tüm boşluk boyunca taşıyarak gerçeklikten sapıyordu.
    """
    df = df.sort_values("Tarih").reset_index(drop=True)
    if len(df) < 2:
        return df
    rows = []
    for i in range(1, len(df)):
        t0 = df.loc[i - 1, "Tarih"]
        t1 = df.loc[i, "Tarih"]
        days = (t1 - t0).days
        if days <= gap_threshold_days:
            continue
        r0 = df.loc[i - 1, "Faiz_Orani_Yillik_Pct"]
        r1 = df.loc[i, "Faiz_Orani_Yillik_Pct"]
        for offset in range(gap_threshold_days, days, gap_threshold_days):
            ratio = offset / days
            rows.append((t0 + pd.Timedelta(days=offset), r0 + (r1 - r0) * ratio))
    if not rows:
        return df
    logger.warning(
        "Mevduat verisinde %d+ gün boşluk; %d ara nokta lineer interpolasyon ile dolduruldu",
        gap_threshold_days, len(rows),
    )
    warnings.warn(
        f"Mevduat verisinde {gap_threshold_days}+ gün boşluk var; "
        f"{len(rows)} ara nokta lineer interpolasyon ile dolduruldu "
        "(yaklaşık değer, gerçek TCMB verisi değil).",
        UserWarning, stacklevel=2,
    )
    extra = pd.DataFrame(rows, columns=["Tarih", "Faiz_Orani_Yillik_Pct"])
    return pd.concat([df, extra], ignore_index=True).sort_values("Tarih").reset_index(drop=True)


def fetch_deposit_rate_with_fallback() -> Tuple[pd.DataFrame, str]:
    """Mevduat faizi için kaynak birleştirme:
    WorldBank (tarihsel yıllık) + Hesapkurdu (bugün spot).
    En az biri başarılı olmalı. İkisi de fail → RuntimeError.
    """
    parts = []
    sources_used = []
    errors = []
    for name, fn in [("WORLDBANK", scrape_worldbank_deposit_rate),
                     ("HESAPKURDU", scrape_hesapkurdu_deposit_rate_today)]:
        try:
            parts.append(fn())
            sources_used.append(name)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            logger.warning("Mevduat faizi kaynağı %s başarısız: %s", name, exc)
            warnings.warn(
                f"Mevduat faizi kaynağı {name} başarısız: {exc}",
                UserWarning, stacklevel=2,
            )
    if not parts:
        raise RuntimeError("Tüm mevduat faizi kaynakları başarısız:\n" + "\n".join(errors))
    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates(subset=["Tarih"], keep="last").sort_values("Tarih").reset_index(drop=True)
    df = _extend_deposit_rate_linear(df)
    return df, "+".join(sources_used)
