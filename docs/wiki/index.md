# Wiki Index - BenchmarkTakip

**Read this first.** All project knowledge lives here.

---

## Kisa Yorum

- TL modunda: "Param TL olarak kac kat artti?"
- USD modunda: "Param dolar bazinda kac kat artti?"
- Reel/TUFE modunda: "Param enflasyonu yendikten sonra kac kat artti?"

## Mimari

- [[mimari]] - 3-katman sistem tasarimi: veri toplama, hesaplama motoru, gorsellestirme
- [[veri_kaynaklari]] - yfinance sembolleri, TUFE/CPI kaynaklari, mevduat ve cache stratejisi
- [[depolama]] - veri klasoru, CSV semalari, yfinance ve CPI cache davranisi

## Hesaplama Motoru

- [[normalizasyon]] - baslangic=100 algoritmasi, TL/USD/Reel donusumleri
- [[maliyet_hesabi]] - WAC formulu, kismi satis davranisi, FIFO neden kullanilmaz
- [[metrikler]] - TWRR, katki analizi, TL/USD/Reel boyutlari

## Teknoloji

- [[stack]] - pandas, plotly, ipywidgets, yfinance; chart_builder fonksiyonlari ve tasarim kararlari

## Kararlar

- WAC secildi; coklu alimlarda toplam performansi tutarli olcer.
- Plotly secildi; notebook/Colab icinde hover, zoom ve interaktif filtre gerekir.
- Reel/TUFE modunda CPI endeks seviyesi kullanilir; aylik enflasyon yuzdesi dogrudan kullanilmaz.
- Mevduat once nominal TL endeks olarak uretilir, USD/Reel modlarinda ilgili baza cevrilir.
