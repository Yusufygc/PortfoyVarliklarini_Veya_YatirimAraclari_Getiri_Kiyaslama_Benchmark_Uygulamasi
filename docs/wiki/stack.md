# Teknoloji Stack

Kaynak: [[index]] · [[mimari]]

## Bağımlılıklar

| Kütüphane | Kullanım | Kurulum |
|-----------|----------|---------|
| `yfinance` | Fiyat verisi çekimi | `pip install yfinance` |
| `pandas` | Veri manipülasyonu | Colab'da mevcut |
| `plotly` | İnteraktif grafikler | `pip install plotly` |
| `ipywidgets` | UI kontrolleri | `pip install ipywidgets` |
| `pickle` | yfinance cache | stdlib |
| `sqlite3` | (opsiyonel v2) | stdlib |

## Neden matplotlib değil plotly?

Zoom, hover, tooltip — kullanıcı veri noktasını görebilir. `matplotlib` statik, Colab'da etkileşimsiz.

## Colab Kurulum Hücresi

```python
import subprocess, sys
REQUIRED = ["yfinance", "plotly", "ipywidgets"]
for pkg in REQUIRED:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])
```

`!pip install` yerine bu pattern kullanılıyor — verbose output bastırılır, tekrar çalıştırılabilir.

Colab'da interaktif çıktı için notebook import hücresi `google.colab.output.enable_custom_widget_manager()` ve `plotly.io.renderers.default = "colab"` ayarlar. GitHub notebook preview kernel çalıştırmadığı için `ipywidgets` ve Plotly çıktıları orada statik/eksik görünebilir; gerçek kullanım Colab'da hücreleri çalıştırarak yapılır.

GitHub'dan çekilen repo için `PROJECT_ROOT` otomatik bulunur. Sıra: mevcut çalışma dizini, `/content/BenchmarkTakip`, `/content/drive/MyDrive/PortfolioProject`. Veri klasörü sırası: `PORTFOLIO_DATA_DIR`, Drive'daki `PortfolioProject`, repo `data/`.

## Grafik Kütüphanesi — chart_builder_v2.py

`lib/chart_builder_v2.py` orijinal `chart_builder.py`'ye dokunmadan yeni fonksiyonlar ekler.

### Fonksiyonlar

| Fonksiyon | Çıktı | Açıklama |
|-----------|-------|----------|
| `build_performance_line_chart_v2` | `go.Figure` | Solid çizgi, range selector (1A/3A/6A/YBB/1Y/Tümü), range slider, başlangıç=100 referans çizgisi |
| `build_asset_filter_widget` | `ipywidgets.VBox` | Dropdown combobox → seçilen varlık için line chart yenilenir |
| `build_rolling_returns_chart` | `go.Figure` | n-günlük kümülatif getiri (varsayılan: 30g + 90g pencere) |
| `build_drawdown_chart` | `go.Figure` | Tepe'den düşüş %; portföy varsa kırmızı dolgulu alan |
| `build_correlation_heatmap` | `go.Figure` | Günlük getiri Pearson korelasyon matrisi; kırmızı(−1)→yeşil(+1) |
| `build_period_bar_chart` | `go.Figure` | Aylık (`freq="ME"`) veya çeyreklik (`freq="QE"`) gruplanmış çubuk |
| `build_treemap` | `go.Figure` | Kar/Zarar büyüklük haritası; renk = yüzde getiri; requires contributions DataFrame |
| `build_risk_return_scatter` | `go.Figure` | x=yıllık volatilite, y=toplam getiri; portföy ★ sembolü |

### Tasarım Kararları

- Tüm fonksiyonlar `go.Figure` döndürür, `.show()` çağırmaz — notebook hücresinde `display()` caller'a bırakılır.
- Yüzde değerleri Plotly'e verilmeden önce Python'da `.round(2)` ile yuvarlanır — Plotly format specifier (`:.2f`) unified hover modunda güvenilmez.
- `build_asset_filter_widget`: `ipywidgets.Dropdown` + `Output` + `.observe()` pattern; orijinal `widgets.py` ile aynı yaklaşım.
- Kesikli çizgi (`dash="dash"`) kullanılmaz — tüm benchmark serileri solid.
- Tarih eksenleri ve dönemsel bar etiketleri Türkçe ay adları kullanır (`Ocak 2026`, `1. Çeyrek 2026`). Python `strftime("%q")` kullanılmaz.
- Template: `plotly_dark` (tutarlılık).

### BenchmarkKarsilastirma.ipynb Entegrasyonu

Cell 5'e `from chart_builder_v2 import ...` eklendi. Cell 8-19 yeni analiz hücreleri:
`analysis_df` (Cell 9) → filter widget (11) → drawdown (13) → korelasyon (15) → dönemsel bar (17) → treemap + scatter (19).
Orijinal Cell 1-7 (mevcut dashboard) dokunulmadı.

## Dashboard Modülü — portfoy_dashboard.py

`lib/portfoy_dashboard.py` — PortfolyoBenchmark.ipynb'ye özgü UI kodu. `BenchmarkKarsilastirma.ipynb`'den import edilmez.

### Fonksiyonlar

| Fonksiyon | Açıklama |
|-----------|----------|
| `extract_stock_symbols(transactions, known_assets)` | transactions'taki bilinen varlıklar dışındakileri BIST hissesi sayar, `{"ASELS": "ASELS.IS"}` dict döner |
| `validate_stock_symbol(symbol)` | yfinance üzerinden sembol geçerliliği kontrol eder (ALIŞ sırasında çağrılır) |
| `compute_balance(transactions)` | Nakit bakiye — NAKIT_GIRIS eksi NAKIT_CIKIS ve tüm alım maliyetleri |
| `compute_position(transactions)` | Her varlık için net adet (alım − satım) |
| `validate_transaction(...)` | İşlem formu gönderilmeden önce kural kontrolü (negatif bakiye, sıfır miktar, vb.) |
| `create_portfolio_viewer(...)` | Pozisyon tablosu — sütunlar: Varlık, Miktar, Ort. Maliyet (TL), Güncel Fiyat, Değer, Kar/Zarar (TL/%) |
| `create_transaction_form_v3(...)` | İşlem girişi formu (hisse auto-complete + validation) |
| `create_date_range_picker(...)` | `GG/AA/YYYY` metin alanlı tarih aralığı kontrolü |
| `create_currency_toggle()` | TL/USD toggle widgeti |
| `wire_dashboard(...)` | Widget sinyallerini render fonksiyonuna bağlar |
| `compute_portfolio_performance_index(...)` | Portföy için dış nakit akışından arındırılmış başlangıç=100 getiri serisi |

### Tasarım Kararı

`widgets.py` yerine `portfoy_dashboard.py` — notebook'a özgü mantık paylaşılan `lib/` modüllerini kirletmesin. `_scalar()` ve `_nearest_price()` `portfolio_engine`'den import edilir.

Dashboard tarih aralığı ve işlem giriş formu tarih kontrolleri `DatePicker` değil `GG/AA/YYYY` formatında `Text` widget kullanır. `BenchmarkKarsilastirma.ipynb` dashboard helper'ını `widgets.py` üzerinden, `PortfolyoBenchmark.ipynb` ise bağımsız olarak `portfoy_dashboard.py` üzerinden alır.

## İlgili

[[veri_kaynaklari]] · [[depolama]] · [[mimari]]
