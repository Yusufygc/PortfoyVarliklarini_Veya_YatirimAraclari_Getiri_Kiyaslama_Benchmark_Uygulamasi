# Veri Dosyaları Referansı

## `data/cpi_turkey.csv`

```csv
Tarih,CPI_Endeks
2020-01-01,446.45
2020-02-01,448.02
```

- `Tarih`: ayın ilk günü (YYYY-MM-DD)
- `CPI_Endeks`: pozitif endeks seviyesi (aylık enflasyon yüzdesi değil)

Aylık enflasyondan endeks oluşturma:
```
Yeni_CPI = Onceki_CPI * (1 + Aylik_Enflasyon_Pct / 100)
```

Reel/TÜFE modu için zorunludur. `ensure_cpi_coverage()` eksik ayları otomatik tamamlamaya çalışır.

---

## `data/tcmb_rates.csv`

```csv
Tarih,Faiz_Orani_Yillik_Pct
2023-01-01,42.5
```

TCMB 1-Hafta Repo politika faizi geçmişi. `get_latest_policy_rate()` son satırı okur → `TCMB_POLICY_RATE_PCT` dinamik belirlenir; notebook manuel güncellenmez.

Dosya yoksa `get_latest_policy_rate(filepath, fallback=37.0)` → fallback döner.

---

## `data/deposit_rates.csv`

```csv
Tarih,Faiz_Orani_Yillik_Pct
2024-12-31,71.04
2026-05-16,44.88
```

Bankaların TL mevduatlara uyguladığı ağırlıklı ortalama brüt yıllık faiz. "Mevduat" benchmark'ı için kullanılır.

Politika faizinden 5-10 puan düşük olabilir; aynı değil.

TTL: 7 gün. Scrape zinciri: WorldBank → Hesapkurdu → CSV fallback → politika faizi fallback.

**2025 boşluğu:** WorldBank 2024-12-31'de bitiyor. Hesapkurdu bugün spot. Aradaki 12+ ay `_extend_deposit_rate_linear()` lineer interpolasyon ile doldurulur (UserWarning basılır). Daha hassas 2025 verisi için bu CSV'ye manuel satır ekle (örn. TCMB EVDS 1-3 ay vadeli mevduat ortalaması).

---

## `data/transactions.csv`

```csv
Tarih,Varlık Adı,İşlem Türü,Fiyat,Miktar,Komisyon
01.01.2023,Gram Altin,ALIŞ,1823.5,0.5,0
```

- Tarih: `DD.MM.YYYY`
- İşlem Türü: `ALIŞ`, `SATIŞ`, `NAKIT_GIRIS`, `NAKIT_CIKIS`
- İlk açılışta dosya yoksa "Henüz işlem yok" mesajı görünür — normal.

---

## `data/prices_cache.pkl`

yfinance indirilen fiyatların binary cache'i. Pickle formatı. 8 saatlik TTL; atom yazma ile korunur. Sil → yeniden indirilir.

---

## `data/portfolio.csv` (legacy)

```csv
Varlık Adı,Alış Tarihi,Alış Fiyatı,Miktar,Komisyon
Gram Altin,01.01.2023,1823.50,0.5,0
```

Eski tek-işlem formatı. `transactions.csv` varsa bu dosya kullanılmaz. `_LEGACY_RENAME` mapping: "Altin" → "Gram Altin".
