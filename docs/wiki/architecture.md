# Mimari — BenchmarkTakip

## Klasör yapısı

```
BenchmarkTakip/
├── BenchmarkKarsilastirma.ipynb   # Benchmark karşılaştırma dashboard'u
├── PortfolyoBenchmark.ipynb       # Portföy + benchmark dashboard
├── BenchmarkVeriTest.ipynb        # Veri doğrulama ve smoke testleri
├── lib/
│   ├── constants.py               # Paylaşılan sabitler (sembol setleri, troy oz dönüşüm)
│   ├── data_loader.py             # Fiyat/CPI/TCMB/mevduat veri yükleme
│   ├── macro_scraper.py           # Web scraping + TCMB indeksi hesaplama
│   ├── benchmark_engine.py        # Benchmark serisi normalize + mevduat endeksi
│   ├── chart_builder.py           # Plotly grafik üreticiler
│   ├── chart_builder_v2.py        # BenchmarkKarsilastirma özgün grafik
│   ├── portfolio_engine.py        # WAC hesaplama + portföy değer serisi
│   ├── portfoy_dashboard.py       # ipywidgets form/kontrol factory
│   └── widgets.py                 # Düşük seviye widget yardımcıları
├── data/
│   ├── cpi_turkey.csv             # Aylık TÜFE endeks seviyeleri
│   ├── tcmb_rates.csv             # TCMB politika faizi geçmişi
│   ├── deposit_rates.csv          # Banka mevduat ortalama faizleri
│   ├── transactions.csv           # Portföy işlem kaydı (oluşturulana kadar yok)
│   └── prices_cache.pkl           # yfinance fiyat cache'i
├── docs/wiki/                     # Bu dokümantasyon
└── requirements.txt
```

## Modül bağımlılık sırası

```
constants.py          ← kimseyi import etmez
    ↑
data_loader.py        ← constants (dolaylı yok; os/pandas/etc.)
macro_scraper.py      ← constants, pandas, requests
benchmark_engine.py   ← constants, pandas, warnings
portfolio_engine.py   ← constants
chart_builder.py      ← benchmark_engine, pandas, plotly
portfoy_dashboard.py  ← data_loader, portfolio_engine, benchmark_engine, chart_builder
```

`constants.py` dairesel import riskini kırar: `benchmark_engine` ↔ `portfolio_engine` doğrudan import yoktur.

## Veri akışı

```
yfinance (API)  →  fetch_prices()  →  prices_cache.pkl
tcmb_rates.csv  →  load_tcmb_rates()  →  tcmb_rates (pd.Series)
deposit_rates.csv + scraper  →  load_deposit_rates()  →  deposit_rates (pd.Series)
cpi_turkey.csv + EVDS/DBnomics  →  load_cpi_series() + ensure_cpi_coverage()  →  cpi_series

prices + fx_usdtry + currency  →  build_benchmark_series()  →  normalize 100 başlangıç
deposit_rates  →  build_deposit_series()  →  bileşik mevduat endeksi

transactions + prices + wac  →  compute_portfolio_value_series()  →  portföy zaman serisi
portföy serisi  →  compute_portfolio_performance_index()  →  TWRR endeksi
```
