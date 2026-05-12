# BenchmarkTakip

Kişisel yatırım portföyünü finansal benchmark'larla karşılaştıran interaktif Jupyter dashboard'u.
Google Colab ve yerel Jupyter ortamlarında çalışır.

---

## Özellikler

### Benchmark Karşılaştırması

| Varlık | Kaynak | Birim |
|--------|--------|-------|
| Gram Altın | yfinance `GC=F` | USD/troy oz → TL/gram |
| Gram Gümüş | yfinance `SI=F` | USD/troy oz → TL/gram |
| Dolar/TL | yfinance `USDTRY=X` | TL |
| Euro/TL | yfinance `EURTRY=X` | TL |
| BIST100 | yfinance `XU100.IS` | TL (puan) |
| Mevduat | TCMB politika faizi | Bileşik faiz eğrisi |

### Ana Dashboard (`BenchmarkKarsilastirma.ipynb`)

**İnteraktif kontroller:**
- Tarih aralığı seçici (başlangıç / bitiş DatePicker)
- Para birimi toggle: **TL** (nominal) · **USD** · **Reel** (TÜFE deflate)

**Grafikler ve Analiz Hücreleri:**

| Hücre | İçerik |
|-------|--------|
| 1-7 | Kurulum, veri yükleme, ana dashboard (orijinal) |
| 8 | Analiz bölümü başlığı |
| 9 | `analysis_df` — paylaşılan analiz veri seti |
| 10-11 | Performans line chart v2 — solid çizgi, range selector, combobox varlık filtresi |
| 12-13 | Drawdown grafiği — tepe'den düşüş % |
| 14-15 | Korelasyon ısı haritası — günlük getiri Pearson matrisi |
| 16-17 | Dönemsel bar chart — aylık + çeyreklik getiri |
| 18-19 | Treemap + Risk-Getiri scatter |

### Analiz Grafikleri (`chart_builder_v2.py`)

| Fonksiyon | Açıklama |
|-----------|----------|
| `build_performance_line_chart_v2` | Solid çizgi, 1A/3A/6A/YBB/1Y/Tümü butonları, range slider, başlangıç=100 referans |
| `build_asset_filter_widget` | Dropdown combobox — seçilen varlık için grafik anlık yenilenir |
| `build_rolling_returns_chart` | 30g ve 90g yuvarlanan kümülatif getiri |
| `build_drawdown_chart` | Tepe'den düşüş; portföy varsa kırmızı dolgulu alan |
| `build_correlation_heatmap` | Pearson korelasyon matrisi; kırmızı(−1) → nötr(0) → yeşil(+1) |
| `build_period_bar_chart` | Aylık (`ME`) veya çeyreklik (`QE`) gruplanmış çubuk |
| `build_treemap` | P&L büyüklük haritası; renk = yüzde getiri |
| `build_risk_return_scatter` | x=yıllık volatilite, y=toplam getiri; portföy ★ sembolü |

---

## Proje Yapısı

```
BenchmarkTakip/
├── BenchmarkKarsilastirma.ipynb   # Ana dashboard (19 hücre)
├── BenchmarkVeriTest.ipynb        # Veri doğrulama testleri
├── PortfolyoBenchmark.ipynb       # Portföy vs benchmark (geliştirme aşamasında)
│
├── lib/
│   ├── data_loader.py             # yfinance fetch, 12s cache, CSV yükleyiciler
│   ├── benchmark_engine.py        # Normalizasyon, TL/USD/REAL dönüşüm, mevduat serisi
│   ├── chart_builder.py           # Orijinal Plotly grafik fonksiyonları
│   ├── chart_builder_v2.py        # Gelişmiş analiz grafikleri (8 fonksiyon)
│   ├── portfolio_engine.py        # TWRR, WAC maliyet hesabı
│   └── widgets.py                 # ipywidgets kontrolleri ve dashboard wiring
│
├── data/
│   ├── portfolio.csv              # Portföy pozisyonları (Varlık Adı, Alış Tarihi, Fiyat, Miktar, Komisyon)
│   ├── transactions.csv           # İşlem geçmişi (ALIŞ, SATIŞ, NAKİT_GİRİŞ, NAKİT_ÇIKIŞ)
│   ├── cpi_turkey.csv             # TÜİK CPI endeksi (aylık, Tarih + CPI_Endeks)
│   └── tcmb_rates.csv             # TCMB politika faizi (opsiyonel; yoksa sabit oran kullanılır)
│
├── docs/wiki/                     # Mimari kararlar, hesaplama yöntemleri, değişiklik logu
└── requirements.txt
```

---

## Kurulum

### Google Colab

GitHub notebook preview dosyayı çalıştırmaz; `ipywidgets` ve interaktif Plotly grafikleri GitHub'da metin temsili olarak görünebilir. Grafikleri görmek için notebook'u Colab'da çalıştırın.

Önerilen akış:

```python
!git clone https://github.com/KULLANICI_ADINIZ/BenchmarkTakip.git
%cd BenchmarkTakip
```

Sonra `BenchmarkKarsilastirma.ipynb` veya `PortfolyoBenchmark.ipynb` dosyasını Colab'da açıp hücreleri sırayla çalıştırın. Notebook'lar repo kökündeki `lib/` klasörünü otomatik bulur. Veri klasörü için öncelik:

1. `PORTFOLIO_DATA_DIR` ortam değişkeni
2. Colab'da varsa `/content/drive/MyDrive/PortfolioProject/`
3. Repo içindeki `data/`

Notebook'ların ilk hücresi bağımlılıkları otomatik kurar:

```python
import subprocess, sys
REQUIRED = ["yfinance", "plotly", "ipywidgets"]
for pkg in REQUIRED:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])
```

Google Drive bağlama (Colab'da otomatik):

```python
from google.colab import drive
drive.mount("/content/drive")
```

Kalıcı portföy verisi istiyorsanız `transactions.csv`, `cpi_turkey.csv` ve `tcmb_rates.csv` dosyalarını `/content/drive/MyDrive/PortfolioProject/` altında tutun ya da `PORTFOLIO_DATA_DIR` ile farklı bir klasör seçin.

### Yerel Jupyter

```bash
pip install -r requirements.txt
jupyter notebook BenchmarkKarsilastirma.ipynb
```

---

## Teknik Notlar

### Normalizasyon

Tüm varlıklar `başlangıç = 100` bazına normalize edilir:

```
normalize(fiyat, t0) = fiyat_t / fiyat_t0 × 100
```

Farklı birimler (TL/gram, dolar, BIST puanı) doğrudan karşılaştırılabilir hale gelir.

### Gram Dönüşümü

`GC=F` ve `SI=F` troy ons fiyatı verir:

```
TL/gram = USD/troy_oz × USDTRY ÷ 31.1035
```

### Para Birimi Modları

| Mod | Açıklama |
|-----|----------|
| **TL** | Nominal TL değeri |
| **USD** | TL bazlı seriler ÷ USDTRY; USD bazlı seriler ÷ 31.1035 |
| **REAL** | TL nominal → TÜFE CPI ile deflate (satın alma gücü) |

### Mevduat Serisi

```python
günlük_oran = (1 + yıllık_faiz / 100) ** (1/365) - 1
kümülatif   = (1 + günlük_oran).cumprod() × 100
```

Gerçek zamanlı API yok. Öncelik sırası: `tcmb_rates.csv` → sabit `TCMB_POLICY_RATE_PCT` (varsayılan: %37).

### Cache

yfinance verisi `data/prices_cache.pkl` içinde saklanır. Maksimum yaş: 12 saat.
Süre dolduğunda veya yeni semboller talep edildiğinde otomatik yenilenir.

### Maliyet Hesabı

Ağırlıklı Ortalama Maliyet (WAC) yöntemi kullanılır — FIFO/LIFO değil.
Kısmi satışta WAC değişmez; yalnızca birim sayısı azalır.

### Yüzde Değeri Gösterimi

Plotly hovertemplate format specifier'ları unified hover modunda güvenilmez olduğundan
yüzde değerleri Plotly'e verilmeden Python'da `.round(2)` ile yuvarlanır.

---

## Veri Şemaları

### `portfolio.csv`

```
Varlık Adı | Alış Tarihi | Alış Fiyatı | Miktar | Komisyon
Altin      | 01.01.2023  | 1823.50     | 0.5    | 0
```

### `transactions.csv`

```
Tarih      | Varlık Adı | İşlem Türü   | Fiyat  | Miktar | Komisyon
01.01.2023 | Altin      | ALIŞ         | 1823.5 | 0.5    | 0
```

Geçerli `İşlem Türü` değerleri: `ALIŞ` · `SATIŞ` · `NAKIT_GIRIS` · `NAKIT_CIKIS`

### `cpi_turkey.csv`

```
Tarih      | CPI_Endeks
01.01.2023 | 1285.43
```

### `tcmb_rates.csv` (opsiyonel)

```
Tarih      | Faiz_Orani_Yillik_Pct
01.01.2023 | 42.5
```
