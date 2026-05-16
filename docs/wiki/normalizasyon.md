# Normalizasyon

Kaynak: [[index]] - [[mimari]] - [[metrikler]]

## Kisa Yorum

- TL modunda: "Param TL olarak kac kat artti?"
- USD modunda: "Param dolar bazinda kac kat artti?"
- Reel/TUFE modunda: "Param enflasyonu yendikten sonra kac kat artti?"

Tum grafiklerde seri baslangici `100` kabul edilir. `150` degeri secilen baslangica gore yaklasik `%50` artisi, `80` degeri yaklasik `%20` kaybi anlatir.

## Temel Algoritma

```python
normalized = price_series / price_at_start_date * 100
```

- `start_date` is gunu degilse en yakin sonraki mevcut veri baz alinir.
- Veri yoksa sahte geri doldurma yapilmaz.
- Baz deger sifirsa normalizasyon yapilmaz.

## Para Birimi Modlari

| Mod | Ne olculur? | Donusum |
|-----|-------------|---------|
| TL | Nominal TL getirisi | USD bazli varliklar TL'ye cevrilir |
| USD | Dolar bazli getiri | TL bazli varliklar USDTRY ile USD'ye cevrilir |
| Reel/TUFE | Enflasyon sonrasi satin alma gucu | Nominal TL seri `CPI_t / CPI_baslangic` oranina bolunur |

## Gram Altin ve Gram Gumus

`GC=F` ve `SI=F` yfinance tarafinda USD/troy ons fiyatidir. 1 troy ons = `31.1035` gram.

```text
TL/gram  = USD/troy_oz * USDTRY / 31.1035
USD/gram = USD/troy_oz / 31.1035
```

USD modunda gram altin/gumus zaten USD bazli oldugu icin USDTRY ile carpilmaz; yalnizca gram donusumu yapilir. Sabit `31.1035` boleni getiri oranini degistirmez, ama birimi dogru ifade eder.

## Reel/TUFE Hesabi

Reel modda once her varlik nominal TL bazina getirilir. Sonra TUFE endeksiyle deflate edilir:

```text
Reel_Deger_t = Nominal_TL_Deger_t / (CPI_t / CPI_baslangic)
Reel_Endeks_t = Reel_Deger_t / Reel_Deger_baslangic * 100
```

Ornek:

```text
Varlik 100 TL -> 300 TL oldu.
CPI 1000 -> 1500 oldu.
Nominal artis = 3.0 kat
Fiyat seviyesi = 1.5 kat
Reel artis = 3.0 / 1.5 = 2.0 kat
Reel endeks = 200
```

## Mevduat

Mevduat once nominal TL bilesik endeks olarak uretilir.

- TL modunda: nominal TL endeks kullanilir.
- USD modunda: mevduat TL endeksi USDTRY ile USD bazina cevrilip yeniden normalize edilir.
- Reel/TUFE modunda: mevduat TL endeksi CPI ile deflate edilip yeniden normalize edilir.

## Ilgili

[[metrikler]] - [[veri_kaynaklari]] - [[maliyet_hesabi]]
