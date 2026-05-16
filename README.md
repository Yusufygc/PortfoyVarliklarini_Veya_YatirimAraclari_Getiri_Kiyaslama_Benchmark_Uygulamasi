# BenchmarkTakip

Kişisel yatırım portföyünü ve seçili benchmark varlıklarını TL, dolar ve enflasyon sonrası reel bazda karşılaştıran interaktif Jupyter dashboard'u.

## Kısa yorum

- TL modunda: "Param TL olarak kaç kat arttı?"
- USD modunda: "Param dolar bazında kaç kat arttı?"
- Reel/TÜFE modunda: "Param enflasyonu yendikten sonra kaç kat arttı?"

Bu yüzden grafiklerdeki 100 başlangıç noktası, seçilen tarihteki referanstır. Değer 180 ise seçili bazda 1,8 kat; 75 ise seçili bazda başlangıca göre %25 kayıp anlamına gelir.

## Ana kullanım

`BenchmarkKarsilastirma.ipynb` ana karşılaştırma ekranıdır. Dashboard'da:

- Başlangıç ve bitiş tarihi seçilir.
- TL, USD veya Reel/TÜFE modu seçilir.
- Varlıklar checkbox listesinden tek tek açılıp kapatılır.
- Tek varlık seçilirse tek çizgi, birden fazla varlık seçilirse özel karşılaştırma grafiği üretilir.
- Veri seçilen aralığı kapsamıyorsa grafik çizmek yerine açık hata mesajı gösterilir.

Karşılaştırılabilen varlıklar:

| Varlık | Kaynak | Temel veri |
|---|---|---|
| Gram Altın | yfinance `GC=F` + `USDTRY=X` | USD/troy ons, TL/gram veya USD/gram |
| Gram Gümüş | yfinance `SI=F` + `USDTRY=X` | USD/troy ons, TL/gram veya USD/gram |
| DOLAR | yfinance `USDTRY=X` | TL/USD kuru |
| EURO | yfinance `EURTRY=X` | TL/EUR kuru |
| BIST100 | yfinance `XU100.IS` | TL bazlı endeks puanı |
| Mevduat | `tcmb_rates.csv` veya sabit politika faizi | Bileşik TL mevduat endeksi |

## Modlar neyi kıyaslıyor?

| Mod | Cevapladığı soru | Hesap mantığı |
|---|---|---|
| TL (Nominal) | TL olarak ne kadar büyüdü? | Her varlık nominal TL değerine çevrilir ve başlangıç 100 yapılır. |
| USD | Dolar bazında ne kadar büyüdü? | TL bazlı varlıklar USDTRY'ye bölünür; altın/gümüş USD/gram olarak kullanılır. |
| Reel (TÜFE) | Enflasyonu yendikten sonra ne kaldı? | Tüm varlıklar önce nominal TL bazına alınır, sonra TÜFE endeksiyle deflate edilir. |

Altın ve gümüş için yfinance verisi troy ons cinsinden gelir:

```text
TL/gram  = USD/troy_oz * USDTRY / 31.1035
USD/gram = USD/troy_oz / 31.1035
```

Reel/TÜFE modunda kullanılan temel formül:

```text
CPI_orani_t = CPI_t / CPI_baslangic
Reel_deger_t = Nominal_TL_deger_t / CPI_orani_t
Reel_endeks_t = Reel_deger_t / Reel_deger_baslangic * 100
```

Örnek: Bir varlık TL olarak 3 kat artarken TÜFE 1,5 kat arttıysa reel artış `3 / 1,5 = 2` kattır. Grafikte bu yaklaşık 200 görünür.

## TÜFE/CPI verisi

Reel mod için `data/cpi_turkey.csv` kullanılır. Bu dosyadaki değer aylık enflasyon yüzdesi değil, endeks seviyesidir.

```csv
Tarih,CPI_Endeks
2020-01-01,446.45
2020-02-01,448.02
```

Manuel veri oluşturacaksanız:

- `Tarih` ayın ilk günü olmalı.
- `CPI_Endeks` pozitif ve endeks seviyesi olmalı.
- Aylık enflasyon yüzdesini doğrudan yazmayın.
- Elinizde aylık enflasyon varsa endeksi şu şekilde ilerletin:

```text
Yeni_CPI_Endeks = Onceki_CPI_Endeks * (1 + Aylik_Enflasyon_Yuzde / 100)
```

Notebook çalışırken `ensure_cpi_coverage()` seçilen tarih aralığı için CPI kapsamını tamamlamaya çalışır. Öncelik sırası:

1. Mevcut `data/cpi_turkey.csv`
2. TCMB EVDS API, `EVDS_API_KEY` veya `TCMB_EVDS_API_KEY` tanımlıysa
3. DBnomics TCMB/CPI kaynağı

Veri tamamlanamazsa Reel/TÜFE grafiği boş veya yanıltıcı çizilmez; kullanıcıya kapsam hatası gösterilir.

İçinde bulunulan ayın TÜFE verisi henüz yayımlanmamışsa sistem son yayımlanan resmi ayı günlük olarak ileri taşır. Örneğin `2026-05-14` için `2026-04-01` endeksi varsa Reel/TÜFE grafiği çizilir; Mayıs ayına tahmini endeks yazılmaz.

## Kurulum

Gereksinim: **Python 3.10 veya üzeri**.

### Yerel Jupyter

```bash
git clone https://github.com/Yusufygc/PortfoyVarliklarini_Veya_YatirimAraclari_Getiri_Kiyaslama_Benchmark_Uygulamasi.git
cd PortfoyVarliklarini_Veya_YatirimAraclari_Getiri_Kiyaslama_Benchmark_Uygulamasi
pip install -r requirements.txt
jupyter notebook BenchmarkKarsilastirma.ipynb
```

Conda ortamı örneği:

```powershell
C:\Users\<KULLANICI>\anaconda3\envs\BencmarkTakip\python.exe -m jupyter notebook BenchmarkKarsilastirma.ipynb
```

### Google Colab

Colab'da **File → Open notebook → GitHub** sekmesine gidip repo URL'sini yapıştırın:

```
https://github.com/Yusufygc/PortfoyVarliklarini_Veya_YatirimAraclari_Getiri_Kiyaslama_Benchmark_Uygulamasi
```

`BenchmarkKarsilastirma.ipynb` veya `PortfolyoBenchmark.ipynb` seçin ve açın. Cell-1'i çalıştırın; repo klonu ve `pip install` otomatik yapılır.

**Drive ile kalıcı veri** (opsiyonel): işlem geçmişinizi (`transactions.csv`) Drive'da saklamak isterseniz Cell-2 Drive mount otomatik yapılır. `PORTFOLIO_DATA_DIR` çevre değişkeniyle özel klasör de seçebilirsiniz.

### Yeni kullanıcı için ilk çalıştırma (`PortfolyoBenchmark.ipynb`)

İlk açılışta `data/transactions.csv` yoksa "Henüz işlem yok" mesajı görünür — bu normal. Hücre 6'daki işlem formundan ilk alış/satış/nakit girişini ekleyin → `transactions.csv` otomatik oluşturulur, dashboard yenilenir. Şema referansı [aşağıda](#datatransactionscsv).

### Veri klasörü önceliği

Notebook'lar repo kökündeki `lib/` klasörünü otomatik bulur. Veri klasörü önceliği:

1. `PORTFOLIO_DATA_DIR` çevre değişkeni (her ikisinde de geçerli)
2. Colab'da varsa `/content/drive/MyDrive/PortfolioProject/`
3. Repo içindeki `data/`

## Proje yapısı

```text
BenchmarkTakip/
├── BenchmarkKarsilastirma.ipynb
├── PortfolyoBenchmark.ipynb
├── BenchmarkVeriTest.ipynb
├── lib/
│   ├── constants.py         # Paylaşılan sabitler (TROY_OZ_TO_GRAM, sembol setleri)
│   ├── data_loader.py
│   ├── macro_scraper.py
│   ├── benchmark_engine.py
│   ├── chart_builder.py
│   ├── chart_builder_v2.py
│   ├── portfolio_engine.py
│   ├── portfoy_dashboard.py
│   └── widgets.py
├── data/
│   ├── cpi_turkey.csv
│   ├── tcmb_rates.csv
│   ├── deposit_rates.csv
│   ├── portfolio.csv
│   └── transactions.csv
├── docs/wiki/
│   ├── architecture.md
│   ├── hesaplama-notlari.md
│   └── veri-dosyalari.md
└── requirements.txt
```

## Veri dosyaları

### `data/cpi_turkey.csv`

```csv
Tarih,CPI_Endeks
2023-01-01,1203.48
```

Reel/TÜFE modu için zorunludur.

### `data/tcmb_rates.csv`

```csv
Tarih,Faiz_Orani_Yillik_Pct
2023-01-01,42.5
```

TCMB **politika faizi** (1-Hafta Repo). `get_latest_policy_rate()` ile notebook'lar `TCMB_POLICY_RATE_PCT` sabitini bu dosyanın son satırından okur — TCMB rate kararı değişince notebook manuel güncellenmez. Dosya yok/bozuksa Cell-3'teki fallback (37%) kullanılır.

### `data/deposit_rates.csv`

```csv
Tarih,Faiz_Orani_Yillik_Pct
2024-12-31,71.04
2026-05-16,44.88
```

Bankaların TL mevduatlara uyguladığı **ağırlıklı ortalama brüt yıllık faiz**. "Mevduat" benchmark'ı için kullanılır (politika faizi değil — TCMB ve banka oranı arasında 5-10 puan fark olur).

**Kaynak zinciri** (otomatik scrape, TTL 7 gün):

1. **World Bank Open Data** (`FR.INR.DPST`) — Türkiye yıllık brüt mevduat faizi (1978-2024).
2. **Hesapkurdu.com** — 8 banka için bugünkü ortalama spot.
3. CSV mevcut ama scrape fail → CSV kullanılır (uyarı basılır).
4. CSV yoksa → `fallback_policy_rate_series` (politika faizi) devreye girer + uyarı.

**Limitasyon (2025 boşluğu):** WorldBank yıllık veri 2024-12-31'de bitiyor, Hesapkurdu sadece bugün spot. Arada 12+ aylık boşluk olduğunda `_extend_deposit_rate_linear()` **lineer interpolasyon** ile ~180 günlük ara noktalar üretir (örn. 2025-06, 2025-12). Bu yaklaşık değerdir, gerçek TCMB verisi değildir; UserWarning basılır. Daha hassas 2025 değeri için CSV'ye manuel satır ekleyebilirsiniz (örn. TCMB EVDS'den 1-3 ay vadeli mevduat ortalaması).

### `data/portfolio.csv`

```csv
Varlık Adı,Alış Tarihi,Alış Fiyatı,Miktar,Komisyon
Gram Altin,01.01.2023,1823.50,0.5,0
```

### `data/transactions.csv`

```csv
Tarih,Varlık Adı,İşlem Türü,Fiyat,Miktar,Komisyon
01.01.2023,Gram Altin,ALIŞ,1823.5,0.5,0
```

Geçerli işlem türleri: `ALIŞ`, `SATIŞ`, `NAKIT_GIRIS`, `NAKIT_CIKIS`.

## Teknik notlar

- Tüm benchmark serileri seçilen başlangıç tarihinde `100` olacak şekilde normalize edilir.
- Fiyat serilerinde başlangıç öncesi eksik veriler geriye doldurulmaz; veri yoksa sahte 100 serisi üretilmez.
- yfinance fiyat cache'i `data/prices_cache.pkl` içinde tutulur (atomik yazma, 8 saatlik TTL).
- yfinance zaman dilimi cache'i proje içindeki yazılabilir cache dizinine alınır.
- Treemap hover'ında TL tutarlar Türkçe okunabilir biçimde gösterilir: `₺+764.911,1`.
- WAC komisyon simetrisi: ALIŞ ve SATIŞ işlemleri komisyonu birim başına dağıtır; `realized_pnl` gerçek ekonomik karı yansıtır.
- HTTP scraping 3 deneme + üstel backoff (2/4/8 sn) ile korunur; geçici 429/5xx otomatik yeniden denenir.
- CSV yazma işlemleri atomik (`mkstemp` + `os.replace`); eşzamanlı iki kullanıcıda veri bütünlüğü korunur.
- `TCMB_POLICY_RATE_PCT` her notebook Cell-5'te `tcmb_rates.csv` son satırından okunur; sabit değil.

Detaylı hesaplama notları için `docs/wiki/` klasöründeki wiki dosyalarına bakın.

Detaylı hesaplama notları için `docs/wiki/` klasöründeki wiki dosyalarına bakın.
