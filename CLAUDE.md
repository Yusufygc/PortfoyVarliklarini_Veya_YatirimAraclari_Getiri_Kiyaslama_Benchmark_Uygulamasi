# CLAUDE.md — BenchmarkTakip

Jupyter tabanlı yatırım benchmark dashboard'u. Python 3.10+.

## Kritik kurallar

- Notebook hücrelerini düzenlerken `NotebookEdit` kullan (`Edit` .ipynb'yi bozar).
- `lib/` değişikliği → her iki ana notebook'u (BenchmarkKarsilastirma + PortfolyoBenchmark) etkisini kontrol et.
- CSV yazma: her zaman `_atomic_write_bytes()` kullan — doğrudan `df.to_csv()` değil.
- Yeni sembol sabiti: `lib/constants.py`'ye ekle; doğrudan modüle yazma (dairesel import riski).

## Proje yapısı hızlı referans

```
lib/constants.py          paylaşılan sabitler (TROY_OZ_TO_GRAM, GRAM_SYMBOLS, vb.)
lib/data_loader.py        fetch_prices, load_cpi_series, load_deposit_rates, get_latest_policy_rate
lib/macro_scraper.py      WorldBank + Hesapkurdu scraping, _extend_deposit_rate_linear
lib/benchmark_engine.py   build_benchmark_series, build_deposit_series
lib/portfolio_engine.py   compute_wac, compute_portfolio_value_series
lib/portfoy_dashboard.py  ipywidgets form/kontrol factory (PortfolyoBenchmark'a özgün)
data/cpi_turkey.csv       aylık TÜFE endeks seviyeleri (CPI_Endeks, endeks seviyesi)
data/tcmb_rates.csv       TCMB politika faizi geçmişi
data/deposit_rates.csv    banka mevduat ortalaması (7 gün TTL, scrape zinciri)
```

## Önemli davranışlar

**`get_latest_policy_rate(filepath, fallback=37.0)`** — `tcmb_rates.csv` son satırından politika faizi okur. Dosya yoksa / bozuksa fallback. Her iki notebook Cell-5 başında çağrılır.

**`_extend_deposit_rate_linear(df, gap_threshold_days=180)`** — `deposit_rates` içinde 180+ günlük boşlukları lineer interpolasyon ile doldurur. Yaklaşık değer; UserWarning basılır. 2025 için geçici çözüm (WorldBank 2024'te bitiyor).

**`_http_get(url, max_attempts=3)`** — 3 deneme, 2/4/8 sn üstel backoff. 4xx (429 hariç) retry yok. `macro_scraper`'daki tüm HTTP çağrıları bunu kullanır.

**`_atomic_write_bytes(filepath, write_fn)`** — `mkstemp` + `os.replace` ile atomik yazma. `_upsert_csv`, `_update_macro_cache`, `fetch_prices` cache write kullanır.

**WAC komisyon simetrisi** — ALIŞ ve SATIŞ her ikisi de komisyonu birim başına dağıtır:
- ALIŞ: `wac = fiyat + komisyon / miktar`
- SATIŞ: `realized = (fiyat - komisyon / miktar - wac) * miktar`

**`_macro_stale` TTL** — `.total_seconds() >= TTL_DAYS * 86400` kullanılır (`.days` integer floor → off-by-one).

## Test notebook

`BenchmarkVeriTest.ipynb` → Run All yapılabilir olmalı. Tüm hücreler PASS veya dokümante UserWarning. CPI testi yıllık YoY kontrolü yapar (aylık `is_monotonic_increasing` değil — mevsimsel düşüşler normaldir). Çapraz kontrol `BENCHMARK_ONLY` setini (BIST100, DOLAR, EURO, Gram Altin, vb.) ALIŞ zorunluluğundan muaf tutar.

## Commit tercihleri

- Her tier/konu ayrı commit.
- README wiki bölümü varsa değişiklikle birlikte güncelle.

## Bilinen limitasyonlar

- `deposit_rates.csv` 2025 aralığı interpolasyon ile dolu (gerçek TCMB verisi değil). Daha hassas değer için CSV'ye manuel satır ekle.
- yfinance `prices_cache.pkl` 8 saatlik TTL; eski cache sorun çıkarırsa sil.
- Hesapkurdu scraper sayfa yapısına bağımlı; HTML değişirse defansif heuristic (yüzde-içeren kolon) devreye girer.
- İçinde bulunulan ayın TÜFE'si henüz yayımlanmamışsa Reel/TÜFE modu son resmi ayı kullanır; tahmini değer yazılmaz.
