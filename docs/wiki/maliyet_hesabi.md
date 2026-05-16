# Maliyet Hesabı — WAC

Kaynak: [[index]] · [[mimari]]

## Yöntem: Ağırlıklı Ortalama Maliyet (WAC)

FIFO veya LIFO kullanılmaz. WAC seçildi çünkü çoklu alım tarihlerinde toplam pozisyon performansını en doğru ölçer.

## Formül

```
WAC = (önceki_WAC × önceki_adet + yeni_fiyat × yeni_adet) / toplam_adet
```

## Kısmi Satış Davranışı

**WAC satışta değişmez.** Sadece tutulan adet azalır.

```
Gerçekleşen P&L = (satış_fiyatı - WAC) × satılan_adet - komisyon
Gerçekleşmemiş P&L = (güncel_fiyat - WAC) × tutulan_adet
```

## Uygulama: `portfolio_engine.compute_wac()`

```python
compute_wac(transactions: pd.DataFrame) -> dict
# {asset_name: {"wac": float, "units": float, "realized_pnl": float}}
```

## Test Senaryoları

| Senaryo | Beklenti |
|---------|----------|
| 2 alım farklı fiyat | WAC = ağırlıklı ortalama |
| Kısmi satış | WAC değişmez, units azalır |
| Tam satış | units=0, WAC=son_değer |

## İlgili

[[metrikler]] · [[normalizasyon]] · [[veri_kaynaklari]]
