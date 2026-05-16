# Hesaplama Notları

## WAC (Ağırlıklı Ortalama Maliyet)

`lib/portfolio_engine.py` → `compute_wac()`

### Formüller

**ALIŞ:**
```
birim_maliyet = fiyat + komisyon / miktar
yeni_wac = (eski_wac * eski_miktar + birim_maliyet * yeni_miktar) / toplam_miktar
```

**SATIŞ:**
```
net_birim_fiyat = fiyat - komisyon / miktar
realized_pnl += (net_birim_fiyat - wac) * miktar
```

Komisyon her iki tarafta da birim başına dağıtılır. Bu simetri: ALIŞ'ta WAC'a eklenen birim komisyon, SATIŞ'ta net gelirden çıkarılır. Net kar = satış komisyonu ve alış komisyonu dahil gerçek ekonomik kar.

### Örnek

```
ALIŞ: 100 adet @ 100 TL, komisyon 10 TL
  birim_maliyet = 100 + 10/100 = 100.10
  WAC = 100.10

SATIŞ: 50 adet @ 110 TL, komisyon 5 TL
  net_birim = 110 - 5/50 = 109.90
  realized_pnl = (109.90 - 100.10) * 50 = 490 TL
```

---

## Benchmark normalizasyonu

`lib/benchmark_engine.py` → `build_benchmark_series()`

Tüm seriler başlangıç tarihinde 100 yapılır:

```
endeks_t = (fiyat_t / fiyat_baslangic) * 100
```

- TL modu: nominal TL değerleri
- USD modu: TL değerler / USDTRY kuruna bölünür; altın/gümüş zaten USD/gram
- Reel/TÜFE modu: nominal TL → TÜFE deflasyonu:
  ```
  CPI_oran_t = CPI_t / CPI_baslangic
  Reel_t = TL_t / CPI_oran_t
  ```

### Altın/Gümüş dönüşüm

yfinance troy ons (USD) → gram çevrimi:

```
TL/gram  = USD/troy_oz * USDTRY / 31.1035
USD/gram = USD/troy_oz / 31.1035
```

Sabit `TROY_OZ_TO_GRAM = 31.1035` `lib/constants.py`'den gelir.

---

## Mevduat bileşik endeksi

`lib/benchmark_engine.py` → `build_deposit_series()`

Yıllık faiz oranından günlük bileşik endeks:

```
günlük_oran = (1 + yıllık_oran/100)^(1/365) - 1
kümülatif_t = ∏(1 + günlük_oran_s) for s in [baslangic, t]
endeks_t = kümülatif_t / kümülatif_baslangic * 100
```

Veri başlangıç tarihini kapsamıyorsa `bfill()` önceki en erken oranı geriye yansıtır ve `UserWarning` basılır.

---

## Mevduat verisi kaynak zinciri ve 2025 boşluğu

`lib/data_loader.py` → `load_deposit_rates()` → `lib/macro_scraper.py` → `fetch_deposit_rate_with_fallback()`

Kaynak önceliği:
1. **WorldBank Open Data** (`FR.INR.DPST`) — Türkiye yıllık brüt mevduat faizi, 1978–2024
2. **Hesapkurdu.com** — 8 banka için bugünkü spot ortalama
3. CSV mevcut ama scrape fail → CSV kullanılır (uyarı)
4. CSV yoksa → `fallback_policy_rate_series` devreye girer + uyarı

### 2025 boşluğu interpolasyonu

WorldBank 2024-12-31'de bitiyor; Hesapkurdu sadece bugün spot veriyor. Arada 12+ aylık boşluk `_extend_deposit_rate_linear()` ile doldurulur:

- 180 günden uzun aralıklarda lineer interpolasyon noktaları eklenir
- Her eklenen noktada `UserWarning` basılır ("yaklaşık değer, gerçek TCMB verisi değil")
- Daha hassas veri: `data/deposit_rates.csv`'ye TCMB EVDS'den manuel satır ekle

---

## TÜFE/CPI kapsama kontrolü

`lib/data_loader.py` → `ensure_cpi_coverage()`

Kaynak önceliği:
1. `data/cpi_turkey.csv`
2. TCMB EVDS API (`EVDS_API_KEY` veya `TCMB_EVDS_API_KEY` ile)
3. DBnomics TCMB/CPI

İçinde bulunulan ayın TÜFE'si henüz yayımlanmamışsa son resmi ay ileri taşınır. Tahmini endeks yazılmaz.

---

## HTTP retry

`lib/macro_scraper.py` → `_http_get()`

3 deneme, üstel geri çekilme:
- 1. hata → 2 sn bekle
- 2. hata → 4 sn bekle
- 3. hata → exception fırlat

Retry: 429, 5xx, timeout, bağlantı hatası. No-retry: 4xx (429 hariç).

---

## Atomik CSV yazma

`lib/data_loader.py` → `_atomic_write_bytes()`

```
temp_file = mkstemp(dir=same_directory)
write to temp_file
os.replace(temp_file, target_file)  # atomik rename
```

İki paralel yazma durumunda ikinci `os.replace` birincinin üstüne atomik yazar; kısmi/bozuk satır olmaz.

---

## `_macro_stale` TTL kontrolü

```python
(datetime.now() - updated_at).total_seconds() >= MACRO_TTL_DAYS * 86400
```

`.days` integer floor kullanılmaz (6 gün 23 saat = 6 → false-negative). `total_seconds()` kesin karşılaştırma.
