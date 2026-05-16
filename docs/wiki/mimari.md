# Mimari

Kaynak: [[index]] → Plans.md

## 3 Katman

```
[Raw Sources] → [Hesaplama Motoru] → [Görselleştirme]
   yfinance         pandas logic          plotly/ipywidgets
   Drive CSV        TWRR, normalize       Colab dashboard
```

### Katman 1: Veri Toplama

- `yfinance`: `GC=F` (Altın), `SI=F` (Gümüş), `USDTRY=X`, `EURTRY=X`, `XU100.IS` (BIST100)
- Kişisel portföy: Drive'dan CSV okuma (`Varlık | Alış Tarihi | Fiyat | Miktar | Komisyon`)
- Mevduat: TCMB EVDS API veya statik bileşik faiz sentetik eğrisi

### Katman 2: Hesaplama Motoru

- **Normalizasyon:** Tüm seriler başlangıç=100 bazına çekilir. Detay: [[normalizasyon]]
- **Maliyet:** Ağırlıklı Ortalama Maliyet. Detay: [[maliyet_hesabi]]
- **Metrikler:** TWRR, katkı analizi, TL/USD/TÜFE boyutları. Detay: [[metrikler]]

### Katman 3: Görselleştirme

- Ana grafik: Çizgi grafik — portföy kalın çizgi, benchmark'lar ince/transparan
- Dağılım: Donut chart (mevcut portföy ağırlıkları)
- KPI kartları: En çok kazandıran/kaybettiren 3 varlık
- İsteğe bağlı: Currency Toggle (TL / USD görünüm)

## Depolama ve Taşınabilirlik

- Colab başında: `drive.mount('/content/drive')`
- Sabit yol: `/content/drive/MyDrive/PortfolioProject/`
- İlk hücre: `!pip install yfinance plotly ipywidgets`

## İlgili Sayfalar

[[veri_kaynaklari]] · [[stack]] · [[metrikler]] · [[normalizasyon]] · [[maliyet_hesabi]]
