# Depolama

Kaynak: [[index]] - [[mimari]] - [[stack]]

## Veri Klasoru

Yerel ortamda varsayilan veri klasoru `data/` dizinidir. Colab'da Drive klasoru varsa `/content/drive/MyDrive/PortfolioProject/` kullanilir. `PORTFOLIO_DATA_DIR` ortam degiskeni verilirse o klasor onceliklidir.

```text
data/
  transactions.csv
  portfolio.csv
  cpi_turkey.csv
  tcmb_rates.csv
  cache/
    prices_cache.pkl
    yf_tz_cache/
```

## `cpi_turkey.csv`

Reel/TUFE modunun ana veri dosyasidir.

```csv
Tarih,CPI_Endeks
01.01.2020,446.45
01.02.2020,448.02
```

Kurallar:

- `Tarih`: ayin ilk gunu, `GG.AA.YYYY`
- `CPI_Endeks`: aylik enflasyon yuzdesi degil, endeks seviyesi
- Ondalik ayirici nokta olmali
- Her ay icin tek satir olmali
- Seri pozitif olmali
- Guncel ay henuz yayimlanmamissa son resmi ay ileri tasinir; CSV'ye tahmini ay eklenmez

Notebook calisirken `ensure_cpi_coverage()` eksik aylari tamamlamaya calisir ve basarili olursa CSV'yi kalici olarak gunceller.

## `tcmb_rates.csv`

Mevduat faiz gecmisidir.

```csv
Tarih,Faiz_Orani_Yillik_Pct
01.01.2023,42.5
```

CSV yoksa notebook `TCMB_POLICY_RATE_PCT` sabitini kullanir.

## Cache Politikasi

- `prices_cache.pkl`: yfinance fiyat cache'i.
- `yf_tz_cache/`: yfinance timezone/cookie yardimci cache'i.
- Fiyat cache'i istenen tarih araligini kapsamiyorsa yeniden indirme denenir.

## Ilgili

[[veri_kaynaklari]] - [[stack]] - [[mimari]]
