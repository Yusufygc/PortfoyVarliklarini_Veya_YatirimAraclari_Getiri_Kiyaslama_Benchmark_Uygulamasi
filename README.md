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

Yeni bir Colab notebook açın, ilk hücreye:

```python
!git clone https://github.com/Yusufygc/PortfoyVarliklarini_Veya_YatirimAraclari_Getiri_Kiyaslama_Benchmark_Uygulamasi.git BenchmarkTakip
%cd BenchmarkTakip
!pip install -r requirements.txt
```

Sonra repo içindeki `BenchmarkKarsilastirma.ipynb` veya `PortfolyoBenchmark.ipynb` dosyalarını Colab'da açın (`File → Open notebook → GitHub` veya Drive'a kopyala). Notebook hücreleri Colab'ı otomatik algılar (`IN_COLAB` flag) ve `lib/` klasörünü `sys.path`'e ekler.

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
├── lib/
│   ├── data_loader.py
│   ├── benchmark_engine.py
│   ├── chart_builder.py
│   ├── chart_builder_v2.py
│   ├── portfolio_engine.py
│   └── widgets.py
├── data/
│   ├── cpi_turkey.csv
│   ├── tcmb_rates.csv
│   ├── portfolio.csv
│   └── transactions.csv
├── docs/wiki/
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

Mevduat serisi için kullanılır. Dosya yoksa sistem varsayılan sabit faiz oranıyla mevduat endeksi üretir.

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
- yfinance fiyat cache'i `data/prices_cache.pkl` içinde tutulur.
- yfinance zaman dilimi cache'i proje içindeki yazılabilir cache dizinine alınır.
- Treemap hover'ında TL tutarlar Türkçe okunabilir biçimde gösterilir: `₺+764.911,1`.

Detaylı hesaplama notları için `docs/wiki/` klasöründeki wiki dosyalarına bakın.
