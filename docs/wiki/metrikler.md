# Metrikler

Kaynak: [[index]] - [[mimari]] - [[normalizasyon]] - [[maliyet_hesabi]]

## Dashboard Getiri Endeksi

Benchmark dashboard'da her varlik `baslangic=100` endeksine cevrilir. Bu, farkli birimlerdeki varliklari ayni grafikte karsilastirmayi saglar.

| Mod | Soru | Yorum |
|-----|------|-------|
| TL | Param TL olarak kac kat artti? | Nominal TL performansi |
| USD | Param dolar bazinda kac kat artti? | Kur etkisinden arindirilmis dolar performansi |
| Reel/TUFE | Param enflasyonu yendikten sonra kac kat artti? | Satin alma gucu performansi |

## Reel Getiri

Reel getiri nominal TL getirinin enflasyon oranina bolunmus halidir.

```text
CPI_orani = CPI_t / CPI_baslangic
Reel_deger = Nominal_TL_deger / CPI_orani
```

`Reel endeks = 100` ise varlik enflasyon kadar artmistir. `100` uzeri reel kazanc, `100` alti reel kayip anlamina gelir.

## USD Bazli Getiri

USD modunda TL bazli varliklar USDTRY ile bolunur:

```text
USD_deger = TL_deger / USDTRY
```

Gram altin ve gram gumus ise zaten USD/troy ons geldigi icin yalnizca gram bazina cevrilir:

```text
USD/gram = USD/troy_oz / 31.1035
```

## TWRR

Portfoy tarafinda nakit giris/cikislardan bagimsiz performans olcmek icin TWRR kullanilir.

```text
sub_return = (V_end - V_start - CF) / (V_start + weighted_CF)
TWRR = (1+r1) * (1+r2) * ... * (1+rn) - 1
```

## Varlik Katki Analizi

```text
katki_pct = agirlik_pct / 100 * pnl_pct
```

Cikti DataFrame kolonlari:

```text
Varlik Adi, pnl_tl, pnl_pct, weight_pct, contribution_pct
```

UI etiketleri Turkce kullanilir: Kar/Zarar, K/Z, Ort. Maliyet.

## Ilgili

[[normalizasyon]] - [[maliyet_hesabi]] - [[veri_kaynaklari]]
