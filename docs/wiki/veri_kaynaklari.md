# Veri Kaynaklari

Kaynak: [[index]] - [[mimari]]

## Fiyat Verileri

Fiyatlar `yfinance` uzerinden alinir ve `data/cache/prices_cache.pkl` icinde cache'lenir.

| Varlik | Sembol | Ham veri | Kullanim |
|--------|--------|----------|----------|
| Gram Altin | `GC=F` | USD/troy ons | TL modunda USDTRY ile TL/gram, USD modunda USD/gram |
| Gram Gumus | `SI=F` | USD/troy ons | TL modunda USDTRY ile TL/gram, USD modunda USD/gram |
| Dolar | `USDTRY=X` | TL/USD | TL modunda kur serisi, USD modunda yaklasik 100 referans |
| Euro | `EURTRY=X` | TL/EUR | USD modunda EUR degeri USD bazina cevrilir |
| BIST100 | `XU100.IS` | TL puan | USD modunda USDTRY ile bolunur |

Fiyat cache'i istenen baslangic tarihini kapsamiyorsa sessizce kabul edilmez. Sistem yfinance ile yeniden indirmeyi dener; yine kapsam yoksa hata verir.

## TUFE / CPI Verisi

Reel mod icin `data/cpi_turkey.csv` kullanilir.

```csv
Tarih,CPI_Endeks
01.01.2020,446.45
01.02.2020,448.02
```

Bu dosyada aylik enflasyon orani degil, TUFE endeks seviyesi yer alir. Endeksin 2003=100 veya baska bir bazla gelmesi sorun degildir; ayni seri icinde tutarli olmasi yeterlidir.

Icindeki ayin TUFE verisi henuz yayimlanmamissa sistem son yayimlanan resmi ayi gunluk olarak ileri tasir. Tahmini endeks uretilmez.

## CPI Guncelleme Sirasi

`data_loader.ensure_cpi_coverage(filepath, start_date, end_date)` secilen aralik icin CPI kapsamini tamamlamaya calisir.

1. Yerel `cpi_turkey.csv` okunur.
2. Eksik ay varsa EVDS denenir. Bunun icin `EVDS_API_KEY` veya `TCMB_EVDS_API_KEY` ortam degiskeni gerekir.
3. EVDS anahtari yoksa DBnomics TCMB/CPI aylik degisim serisiyle mevcut endeks degerlerinden eksik gecmis aylar turetilir.
4. Tamamlanan veri ayni CSV'ye yazilir.

DBnomics aynasi her zaman bugune kadar guncel olmayabilir. Guncel aylar icin en guvenilir yol EVDS API key kullanmak veya CSV'yi manuel tamamlamaktir.

Kaynaklar:

- TCMB Consumer Prices: https://www.tcmb.gov.tr/wps/wcm/connect/en/tcmb%2Ben/main%2Bmenu/statistics/inflation%2Bdata
- DBnomics TCMB/CPI: https://db.nomics.world/TCMB/CPI

## Mevduat Faizi

Mevduat serisi `data/tcmb_rates.csv` varsa buradan okunur. CSV yoksa `TCMB_POLICY_RATE_PCT` sabitiyle gunluk bilesik endeks uretilir.

```csv
Tarih,Faiz_Orani_Yillik_Pct
01.01.2023,42.5
```

## Ilgili

[[stack]] - [[depolama]] - [[mimari]] - [[normalizasyon]]
