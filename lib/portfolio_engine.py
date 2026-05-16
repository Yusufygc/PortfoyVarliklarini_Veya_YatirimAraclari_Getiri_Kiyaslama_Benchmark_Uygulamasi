from datetime import datetime

import numpy as np
import pandas as pd

from constants import TROY_OZ_TO_GRAM, GRAM_SYMBOLS


def _scalar(val) -> float:
    """Extract scalar from a value that may be a pandas Series (duplicate index)."""
    if isinstance(val, pd.Series):
        return float(val.iloc[0])
    return float(val)


def compute_wac(transactions: pd.DataFrame) -> dict:
    """
    Her varlık için Ağırlıklı Ortalama Maliyet ve elde tutulan adet hesaplar.
    Kısmi satışta WAC sabit kalır (FIFO kullanılmaz).

    Returns:
        dict keyed by 'Varlık Adı':
            {"wac": float, "units": float, "realized_pnl": float}
    """
    state = {}
    for _, row in transactions.sort_values("Tarih").iterrows():
        asset = row["Varlık Adı"]
        islem = row["İşlem Türü"]
        if islem not in ("ALIŞ", "SATIŞ"):
            continue
        if asset not in state:
            state[asset] = {"wac": 0.0, "units": 0.0, "realized_pnl": 0.0}

        s = state[asset]
        if islem == "ALIŞ":
            total_cost = s["wac"] * s["units"] + (row["Fiyat"] + row["Komisyon"] / row["Miktar"]) * row["Miktar"]
            s["units"] += row["Miktar"]
            s["wac"] = total_cost / s["units"] if s["units"] > 0 else 0.0
        elif islem == "SATIŞ":
            # Komisyon ALIŞ'ta birim başına eklendiği için (line 36),
            # SATIŞ'ta da birim başına çıkarılmalı (simetri).
            qty = max(row["Miktar"], 1e-9)
            realized = (row["Fiyat"] - row["Komisyon"] / qty - s["wac"]) * row["Miktar"]
            s["realized_pnl"] += realized
            s["units"] = max(0.0, s["units"] - row["Miktar"])
            # WAC değişmez

    return state


def compute_portfolio_value_series(
    transactions: pd.DataFrame,
    prices: pd.DataFrame,
    fx_usdtry: pd.Series,
    symbol_map: dict,
) -> pd.DataFrame:
    """
    İlk işlem tarihinden bugüne günlük portföy değeri.

    Args:
        symbol_map: {"Varlık Adı": "yfinance_sembol", ...}
                    USD bazlı semboller (GC=F, SI=F) otomatik TL'ye çevrilir.
    Returns:
        DataFrame: index=Date, columns=[total_value_tl, total_value_usd, asset_values_tl, units_held]
    """
    usd_symbols = {"GC=F", "SI=F"}

    # yfinance bazen duplicate index döndürür — deduplicate et
    prices = prices.loc[~prices.index.duplicated(keep="first")]
    fx_usdtry = fx_usdtry[~fx_usdtry.index.duplicated(keep="first")]

    start_date = transactions["Tarih"].min()
    date_range = pd.date_range(start_date, datetime.today(), freq="B")

    # Kümülatif pozisyon günlük izle
    position_tracker = {}  # asset -> units (rolling)
    wac_tracker = {}       # asset -> wac (rolling)

    tx_sorted = transactions[transactions["İşlem Türü"].isin(["ALIŞ", "SATIŞ"])].sort_values("Tarih")

    records = []
    tx_idx = 0
    tx_list = tx_sorted.reset_index(drop=True)

    for date in date_range:
        # Bugüne kadar gerçekleşen işlemleri uygula
        while tx_idx < len(tx_list) and tx_list.loc[tx_idx, "Tarih"] <= date:
            row = tx_list.loc[tx_idx]
            asset = row["Varlık Adı"]
            if asset not in position_tracker:
                position_tracker[asset] = 0.0
                wac_tracker[asset] = 0.0

            if row["İşlem Türü"] == "ALIŞ":
                total_cost = (
                    wac_tracker[asset] * position_tracker[asset]
                    + (row["Fiyat"] + row["Komisyon"] / max(row["Miktar"], 1e-9)) * row["Miktar"]
                )
                position_tracker[asset] += row["Miktar"]
                wac_tracker[asset] = total_cost / position_tracker[asset] if position_tracker[asset] > 0 else 0.0
            elif row["İşlem Türü"] == "SATIŞ":
                position_tracker[asset] = max(0.0, position_tracker[asset] - row["Miktar"])

            tx_idx += 1

        # Günlük değer hesapla
        total_tl = 0.0
        asset_values = {}
        date_str = date.strftime("%Y-%m-%d")

        for asset, units in position_tracker.items():
            if units <= 0:
                continue
            sym = symbol_map.get(asset)
            if sym is None or sym not in prices.columns:
                continue

            price_date = _nearest_price(prices[sym], date)
            if price_date is None:
                continue

            price = _scalar(prices[sym].loc[price_date])
            if sym in usd_symbols:
                fx_date = _nearest_price(fx_usdtry, date)
                fx = _scalar(fx_usdtry.loc[fx_date]) if fx_date else 1.0
                price_tl = price * fx
                if sym in GRAM_SYMBOLS:
                    price_tl /= TROY_OZ_TO_GRAM
                value_tl = price_tl * units
            else:
                value_tl = price * units

            asset_values[asset] = value_tl
            total_tl += value_tl

        fx_today = _nearest_price(fx_usdtry, date)
        fx_rate = _scalar(fx_usdtry.loc[fx_today]) if fx_today else 1.0
        total_usd = total_tl / fx_rate if fx_rate > 0 else 0.0

        records.append({
            "date": date,
            "total_value_tl": total_tl,
            "total_value_usd": total_usd,
            "asset_values_tl": asset_values.copy(),
            "units_held": position_tracker.copy(),
        })

    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(
            columns=["total_value_tl", "total_value_usd", "asset_values_tl", "units_held"],
            index=pd.DatetimeIndex([], name="date"),
        )
    return df.set_index("date")


def compute_asset_contributions(
    transactions: pd.DataFrame,
    prices: pd.DataFrame,
    wac_state: dict,
    symbol_map: dict,
    start_date: str,
    end_date: str,
    fx_usdtry: pd.Series = None,
) -> pd.DataFrame:
    """
    Her varlığın P&L katkısını hesaplar (Brinson attribution).
    Returns: DataFrame [Varlık Adı, pnl_tl, pnl_pct, weight_pct, contribution_pct]
    """
    usd_symbols = {"GC=F", "SI=F"}
    end_dt = pd.Timestamp(end_date)
    start_dt = pd.Timestamp(start_date)

    rows = []
    total_portfolio_value = 0.0

    for asset, state in wac_state.items():
        units = state["units"]
        wac = state["wac"]
        realized_pnl = state.get("realized_pnl", 0.0)
        sym = symbol_map.get(asset)
        if sym is None and units > 0:
            continue

        value_tl = 0.0
        cost_tl = 0.0
        if units > 0:
            price_end = _nearest_price(prices[sym], end_dt) if sym in prices.columns else None
            if price_end is None:
                continue

            current_price = _scalar(prices[sym].loc[price_end])
            if sym in usd_symbols and fx_usdtry is not None:
                fx_date = _nearest_price(fx_usdtry, end_dt)
                fx = _scalar(fx_usdtry.loc[fx_date]) if fx_date else 1.0
                current_price_tl = current_price * fx
                if sym in GRAM_SYMBOLS:
                    current_price_tl /= TROY_OZ_TO_GRAM
                wac_tl = wac  # WAC zaten TL/gram cinsinden saklanır (alış anında kullanıcı gram fiyatı girer)
            else:
                current_price_tl = current_price
                wac_tl = wac

            value_tl = current_price_tl * units
            cost_tl = wac_tl * units
        elif realized_pnl == 0:
            continue

        pnl_tl = value_tl - cost_tl + realized_pnl
        pnl_pct = (pnl_tl / cost_tl * 100) if cost_tl > 0 else 0.0
        total_portfolio_value += value_tl

        rows.append({
            "Varlık Adı": asset,
            "pnl_tl": pnl_tl,
            "pnl_pct": pnl_pct,
            "value_tl": value_tl,
            "cost_tl": cost_tl,
        })

    if not rows:
        return pd.DataFrame(columns=["Varlık Adı", "pnl_tl", "pnl_pct", "weight_pct", "contribution_pct"])

    df = pd.DataFrame(rows)
    # Ağırlık: güncel piyasa değerine göre (portföy dağılımı)
    df["weight_pct"] = df["value_tl"] / total_portfolio_value * 100 if total_portfolio_value > 0 else 0.0
    # Katkı: maliyet ağırlığı × getiri (Brinson attribution)
    # Toplam katkı = portföy toplam getirisi olur
    total_cost = df["cost_tl"].sum()
    df["contribution_pct"] = (df["cost_tl"] / total_cost * df["pnl_pct"]) if total_cost > 0 else 0.0
    return df.drop(columns=["value_tl", "cost_tl"]).sort_values("contribution_pct", ascending=False).reset_index(drop=True)


def _nearest_price(series: pd.Series, date: pd.Timestamp):
    """En yakın önceki tarihi bulur (backfill)."""
    try:
        available = series.index[series.index <= date]
        if available.empty:
            return None
        return available[-1]
    except Exception:
        return None
