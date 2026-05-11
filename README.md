# BenchmarkTakip

Kişisel yatırım portföyünü finansal benchmark'larla karşılaştıran interaktif Jupyter dashboard'u.

## Özellikler

- **Benchmark karşılaştırması:** Gram Altın, Gram Gümüş, USD/TRY, EUR/TRY, BIST100, Mevduat faizi
- **Normalizasyon:** Tüm varlıklar başlangıç=100 bazında, doğrudan karşılaştırılabilir
- **Para birimi modları:** TL (nominal), USD, Reel (TÜFE deflate)
- **İnteraktif kontroller:** Tarih aralığı seçici, para birimi toggle
- **Veri kaynağı:** yfinance (canlı), TCMB EVDS, TÜİK CPI

## Notebook'lar

| Dosya | Amaç |
|-------|------|
| `BenchmarkKarsilastirma.ipynb` | Ana dashboard — benchmark karşılaştırma + getiri tablosu |
| `BenchmarkVeriTest.ipynb` | Veri doğrulama — yfinance bağlantısı, gram dönüşüm, normalizasyon testleri |
| `PortfolyoBenchmark.ipynb` | Portföy vs benchmark karşılaştırması (geliştirme aşamasında) |

## Kurulum

```bash
pip install -r requirements.txt
```

## Proje Yapısı

```
BenchmarkTakip/
├── lib/
│   ├── benchmark_engine.py   # Normalizasyon, TL/USD/REAL dönüşüm, mevduat serisi
│   ├── data_loader.py        # yfinance fetch, cache, CSV yükleyiciler
│   ├── chart_builder.py      # Plotly grafik oluşturucu
│   ├── portfolio_engine.py   # TWRR, maliyet hesabı (geliştirme aşamasında)
│   └── widgets.py            # ipywidgets kontrolleri
├── data/
│   ├── portfolio.csv         # Portföy pozisyonları
│   ├── transactions.csv      # İşlem geçmişi
│   ├── cpi_turkey.csv        # TÜİK CPI endeksi
│   └── tcmb_rates.csv        # TCMB politika faizi
├── docs/wiki/                # Mimari kararlar ve wiki
└── requirements.txt
```

## Teknik Notlar

- **Gram dönüşüm:** `GC=F` ve `SI=F` troy ons bazlı — `× USDTRY ÷ 31.1035` ile TL/gram'a çevrilir
- **Mevduat:** Gerçek zamanlı API yok — `tcmb_rates.csv` veya sabit oran ile bileşik faiz eğrisi üretilir
- **Cache:** yfinance verisi `data/cache/prices_cache.pkl` içinde 12 saat saklanır
- **Maliyet:** Ağırlıklı Ortalama Maliyet (WAC) yöntemi, FIFO/LIFO değil
