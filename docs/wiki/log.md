# Log — BenchmarkTakip

Yeni girdiler en üste eklenir.

---

## [2026-05-14] DOCS | TL/USD/Reel karsilastirma ve CPI kullanim dokumantasyonu

Wiki ve README, benchmark modlarini kullanici gozunden aciklayacak sekilde guncellendi. TL modu "Param TL olarak kac kat artti?", USD modu "Param dolar bazinda kac kat artti?", Reel/TUFE modu "Param enflasyonu yendikten sonra kac kat artti?" sorulariyla anlatildi. CPI/TUFE verisinin `data/cpi_turkey.csv` icindeki endeks seviyesiyle kullanildigi, eksik kapsam icin `ensure_cpi_coverage()` mekanizmasinin EVDS ve DBnomics kaynaklarini denedigi, manuel veri girisinde aylik enflasyon yuzdesi yerine `CPI_Endeks` seviyesinin yazilmasi gerektigi belgelendi.

## [2026-05-13] DOCS+FIX | Colab repo kullanım yolu ve renderer ayarı

`BenchmarkKarsilastirma.ipynb` ve `PortfolyoBenchmark.ipynb`: Colab'da `output.enable_custom_widget_manager()` ve `pio.renderers.default = "colab"` ayarlanır. Notebook'lar `PROJECT_ROOT` adaylarından repo içindeki `lib/` klasörünü bulur; veri klasörü sırası `PORTFOLIO_DATA_DIR` → `/content/drive/MyDrive/PortfolioProject/` → repo `data/`. `README.md`: GitHub preview'ın notebook'u çalıştırmadığı, interaktif widget/Plotly çıktılarının Colab'da çalıştırılması gerektiği ve önerilen `git clone` / `%cd` akışı belgelendi.

## [2026-05-13] FIX | Tarih formatı, Türkçe ay etiketleri ve portföy getiri mantığı

`widgets.py` ve `portfoy_dashboard.py`: dashboard tarih aralığı kontrolleri `DatePicker` yerine `GG/AA/YYYY` metin alanı ve validasyon kullanır; iki notebook UI helper'ı bağımsız kalır. `chart_builder.py` / `chart_builder_v2.py`: grafik hover ve eksen/dönem etiketleri Türkçe ay adları kullanır; `build_period_bar_chart` çeyrek etiketleri artık `1. Çeyrek 2026` formatında ve `%q` kullanılmaz. `portfoy_dashboard.py`: `compute_portfolio_performance_index` günlük dış nakit akışını ayrıştıran TL/USD/REAL uyumlu performans endeksi üretir. `portfolio_engine.py`: katkı/Kar-Zarar hesaplarına `realized_pnl` dahil edilir. `data_loader.py`: TCMB CSV yoksa sabit yıllık faiz oranı serisi döner; mevduat endeksi yine `build_deposit_series()` içinde üretilir.

Ek düzeltme: İşlem giriş formlarındaki tüm tarih alanları da `GG/AA/YYYY` metin alanına çevrildi; notebook output snapshot'ları eski UI/grafik göstermemesi için temizlendi. Portföy grafiği net nakit bakiyesi yerine ALIŞ/SATIŞ akışından arındırılmış varlık performansı olarak hesaplanır; NAKIT_GIRIS/CIKIS grafiği yapay biçimde büyütmez.

## [2026-05-13] FIX | KPI kartları duplicate çakışma; P&L→K/Z, WAC→Ort. Maliyet Türkçe rename

`chart_builder.py`: `build_kpi_cards` gainers/losers artık pnl_pct≥0 / <0 ile ayrılıyor (az varlıkta head+tail overlap → çift kart sorunu giderildi). Tablo başlıkları P&L (TL)/P&L % → K/Z (TL)/K/Z %, başlık "Varlık Bazlı Kar/Zarar". `chart_builder_v2.py`: treemap hover ve colorbar P&L → Kar/Zarar / K/Z, başlık güncellendi. `portfoy_dashboard.py`: portfolio viewer sütunları WAC (TL) → Ort. Maliyet (TL), K/Z → Kar/Zarar.

## [2026-05-13] FIX | Portföy motorunda GC=F/SI=F gram dönüşümü; PortfolyoBenchmark SYMBOLS "Gram Altin/Gumus" rename

`portfolio_engine.py`: `compute_portfolio_value_series` ve `compute_asset_contributions` içinde GC=F/SI=F için `/ TROY_OZ_TO_GRAM` eklendi (önceki hata: 10 gr altın ~₺960K hesaplıyordu). `portfoy_dashboard.py`: `create_portfolio_viewer` aynı gram dönüşümü; `create_transaction_form_v3` form fiyat/miktar label'ı seçili varlığa göre dinamik (`Fiyat (TL/gr):` / `Miktar (gr):`). `data_loader.py`: `load_transactions_csv` içinde otomatik legacy rename `Altin→Gram Altin`, `Gumus→Gram Gumus`. `PortfolyoBenchmark.ipynb` Hücre 3: SYMBOLS anahtarları `"Gram Altin"/"Gram Gumus"` olarak güncellendi (BenchmarkKarsilastirma ile tutarlı).

## [2026-05-12] FIX+REFACTOR | yfinance duplicate index fix; portfoy_dashboard.py ayrıştırma; TCMB oranı güncelleme

`portfolio_engine.py`: `_scalar()` helper eklendi (duplicate index'li Series'ten float çekme), `compute_portfolio_value_series` ve `compute_asset_contributions`'da kullanıldı; input deduplicate eklendi. `lib/portfoy_dashboard.py` yeni dosya: notebook'a özgü widget/dashboard kodu (`widgets.py` yerine geçer) — `extract_stock_symbols`, `create_transaction_form_v3`, `create_portfolio_viewer`, `compute_portfolio_performance_index` ve diğer 10 fonksiyon. `PortfolyoBenchmark.ipynb`: imports `portfoy_dashboard`'a taşındı, `TCMB_POLICY_RATE_PCT` 42.5→37 güncellendi, `load_all()` boş transactions ve hisse sembolü auto-extraction'ı işler. Wiki: `stack.md` portfoy_dashboard modülü eklendi, `veri_kaynaklari.md` duplicate index fix ve TCMB oranı güncellendi.

## [2026-05-12] FEATURE | Analiz grafikleri eklendi — chart_builder_v2

`lib/chart_builder_v2.py` oluşturuldu: 8 fonksiyon (performans line chart v2, asset filter widget, rolling returns, drawdown, korelasyon heatmap, dönemsel bar, treemap, risk-getiri scatter). `BenchmarkKarsilastirma.ipynb` 7 hücreden 19 hücreye genişletildi (Cell 8-19 yeni analiz bölümü). `GrafikTest.ipynb` test notebook eklendi. Dönem Sonu tablosu hücreleri ortalandı. Yüzde değerleri Plotly'e verilmeden `.round(2)` ile yuvarlanır. Orijinal Cell 1-7 ve `chart_builder.py` korundu. Wiki: `stack.md` güncellendi.

## [2026-05-11] BUILD | Tüm proje dosyaları implement edildi

lib/ (data_loader, portfolio_engine, benchmark_engine, chart_builder, widgets), data/ CSV şablonları (transactions, portfolio, cpi_turkey, tcmb_rates), BenchmarkTakip.ipynb (6 hücre dashboard), BenchmarkTakip_Tests.ipynb (8 test). Wiki stub sayfaları tamamlandı: veri_kaynaklari, normalizasyon, maliyet_hesabi, metrikler, stack, depolama.

## [2026-05-11] INIT | Wiki ve CLAUDE.md oluşturuldu

Plans.md analiz edildi. CLAUDE.md, `docs/wiki/index.md`, `docs/wiki/log.md` ve `docs/wiki/mimari.md` oluşturuldu. Proje henüz kod içermiyor; Plans.md mimari taslak belgesidir.
