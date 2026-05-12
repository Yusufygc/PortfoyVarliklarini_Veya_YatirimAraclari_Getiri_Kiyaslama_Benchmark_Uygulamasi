"""
PortfolyoBenchmark.ipynb — notebook-specific dashboard code.
Imports shared calculations from lib/*.py (data_loader, portfolio_engine, etc.)
Do NOT import this from BenchmarkKarsilastirma.ipynb.
"""
from datetime import datetime
import warnings

import pandas as pd
import plotly.graph_objects as go
import ipywidgets as widgets
from IPython.display import display

from data_loader import load_transactions_csv
from portfolio_engine import _scalar, _nearest_price
from benchmark_engine import TROY_OZ_TO_GRAM, GRAM_SYMBOLS

# ── Config ───────────────────────────────────────────────────────────────────

STOCK_SUFFIX = ".IS"       # yfinance BIST suffix
NAKIT_TYPES = {"NAKIT_GIRIS", "NAKIT_CIKIS"}
LOT_ASSETS = {"BIST100"}   # v2 backward compat


# ── Business logic ────────────────────────────────────────────────────────────

def extract_stock_symbols(transactions: pd.DataFrame, known_assets) -> dict:
    """
    transactions'taki varlıklardan known_assets ve nakit işlemler dışındakileri hisse say.
    Returns: {"ASELS": "ASELS.IS", "EREGL": "EREGL.IS", ...}
    """
    if len(transactions) == 0:
        return {}
    tx_assets = set(
        transactions[~transactions["İşlem Türü"].isin(NAKIT_TYPES)]["Varlık Adı"]
    )
    stocks = tx_assets - set(known_assets)
    return {s: f"{s}{STOCK_SUFFIX}" for s in stocks}


def validate_stock_symbol(symbol: str) -> tuple:
    """
    yfinance üzerinden sembol geçerliliği kontrol eder (ALIŞ sırasında).
    Returns: (is_valid: bool, error_msg: str)
    """
    import yfinance as yf
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = yf.Ticker(f"{symbol}{STOCK_SUFFIX}").history(period="5d")
        if hist.empty:
            return False, f"'{symbol}' geçersiz sembol veya veri yok."
        return True, ""
    except Exception as e:
        return False, f"Sembol doğrulanamadı: {e}"


def is_stock(asset: str, known_assets) -> bool:
    """True → asset hisse (lot bazlı), False → sabit varlık (fraksiyonel)."""
    return asset not in known_assets and asset not in NAKIT_TYPES


def compute_balance(transactions: pd.DataFrame) -> float:
    """Nakit bakiye = NAKIT_GIRIS - ALIŞ maliyetleri + SATIŞ gelirleri."""
    balance = 0.0
    for _, row in transactions.iterrows():
        t = row["İşlem Türü"]
        if t == "NAKIT_GIRIS":
            balance += row["Fiyat"] * row["Miktar"]
        elif t == "NAKIT_CIKIS":
            balance -= row["Fiyat"] * row["Miktar"]
        elif t == "ALIŞ":
            balance -= row["Fiyat"] * row["Miktar"] + row["Komisyon"]
        elif t == "SATIŞ":
            balance += row["Fiyat"] * row["Miktar"] - row["Komisyon"]
    return balance


def compute_position(transactions: pd.DataFrame) -> dict:
    """Her varlık için mevcut pozisyon (ALIŞ - SATIŞ)."""
    position = {}
    for _, row in transactions.sort_values("Tarih").iterrows():
        asset = row["Varlık Adı"]
        t = row["İşlem Türü"]
        if t == "ALIŞ":
            position[asset] = position.get(asset, 0.0) + row["Miktar"]
        elif t == "SATIŞ":
            position[asset] = max(0.0, position.get(asset, 0.0) - row["Miktar"])
    return position


def validate_transaction(asset, islem_type, fiyat, miktar, komisyon, transactions: pd.DataFrame,
                          known_assets=None) -> list:
    """
    İşlem kurallarını doğrular.
    known_assets: sabit varlıklar kümesi (is_stock tespiti için). None ise LOT_ASSETS kullanılır.
    Returns: list of error strings (empty list = valid).
    """
    errors = []

    if islem_type in NAKIT_TYPES:
        if fiyat <= 0:
            errors.append("Fiyat 0'dan büyük olmalı.")
        if miktar <= 0:
            errors.append("Miktar 0'dan büyük olmalı.")
        return errors

    stock = is_stock(asset, known_assets) if known_assets else (asset in LOT_ASSETS)

    if islem_type == "ALIŞ":
        if stock and miktar != int(miktar):
            errors.append(f"{asset} tam lot (tam sayı) olmalı. Girilen: {miktar}")
        cost = fiyat * miktar + komisyon
        balance = compute_balance(transactions)
        if cost > balance:
            errors.append(
                f"Yetersiz bakiye. Gerekli: ₺{cost:,.2f} | Mevcut: ₺{balance:,.2f}"
            )

    elif islem_type == "SATIŞ":
        if stock and miktar != int(miktar):
            errors.append(f"{asset} tam lot (tam sayı) olmalı. Girilen: {miktar}")
        held = compute_position(transactions).get(asset, 0.0)
        if miktar > held:
            errors.append(
                f"Yetersiz pozisyon. Satılmak istenen: {miktar:g} | Mevcut: {held:g}"
            )

    return errors


# ── Portfolio Viewer ──────────────────────────────────────────────────────────

def create_portfolio_viewer(transactions, prices, wac_state, symbol_map, fx_usdtry, refresh_callback=None):
    """
    Mevcut pozisyonları, WAC, güncel fiyat ve K/Z gösteren interaktif tablo.
    refresh_callback: Yenile butonuna basıldığında çağrılır (load_all gibi).
    """
    USD_SYMBOLS = {"GC=F", "SI=F"}
    GRAM_ASSET_SYMBOLS = GRAM_SYMBOLS
    output = widgets.Output()

    def _render():
        output.clear_output(wait=True)
        with output:
            position = compute_position(transactions)
            balance = compute_balance(transactions)
            rows = []

            for asset, units in position.items():
                if units <= 0:
                    continue
                sym = symbol_map.get(asset)
                wac = wac_state.get(asset, {}).get("wac", 0.0) if wac_state else 0.0

                current_price_tl = None
                if sym and not prices.empty and sym in prices.columns:
                    price_date = _nearest_price(prices[sym], pd.Timestamp.today())
                    if price_date is not None:
                        p = _scalar(prices[sym].loc[price_date])
                        if sym in USD_SYMBOLS:
                            fx_date = _nearest_price(fx_usdtry, pd.Timestamp.today())
                            fx = _scalar(fx_usdtry.loc[fx_date]) if fx_date else 1.0
                            current_price_tl = p * fx
                            if sym in GRAM_ASSET_SYMBOLS:
                                current_price_tl /= TROY_OZ_TO_GRAM
                        else:
                            current_price_tl = p

                value_tl = current_price_tl * units if current_price_tl else None
                cost_tl = wac * units
                pnl_tl = (value_tl - cost_tl) if value_tl is not None else None
                pnl_pct = (pnl_tl / cost_tl * 100) if (pnl_tl is not None and cost_tl > 0) else None

                rows.append({
                    "Varlık": asset,
                    "Miktar": f"{units:g}",
                    "Ort. Maliyet (TL)": f"₺{wac:,.2f}",
                    "Güncel Fiyat": f"₺{current_price_tl:,.2f}" if current_price_tl else "—",
                    "Değer (TL)": f"₺{value_tl:,.0f}" if value_tl else "—",
                    "Kar/Zarar (TL)": f"₺{pnl_tl:+,.0f}" if pnl_tl is not None else "—",
                    "Kar/Zarar %": f"{pnl_pct:+.2f}%" if pnl_pct is not None else "—",
                })

            if not rows:
                print("Henüz portföyde varlık yok.")
                return

            cols = ["Varlık", "Miktar", "Ort. Maliyet (TL)", "Güncel Fiyat", "Değer (TL)", "Kar/Zarar (TL)", "Kar/Zarar %"]
            col_values = [[r[c] for r in rows] for c in cols]
            n = len(rows)
            fill_colors = [["#1e1e2e" if i % 2 == 0 else "#181825" for i in range(n)] for _ in cols]

            fig = go.Figure(go.Table(
                header=dict(
                    values=[f"<b>{c}</b>" for c in cols],
                    fill_color="#313244",
                    font=dict(color="#cdd6f4", size=12),
                    align="center",
                    line_color="#45475a",
                ),
                cells=dict(
                    values=col_values,
                    fill_color=fill_colors,
                    font=dict(color="#cdd6f4", size=11),
                    align=["left", "right", "right", "right", "right", "right", "right"],
                    line_color="#45475a",
                ),
            ))
            fig.update_layout(
                title=f"Portföy Durumu | Nakit Bakiye: ₺{balance:,.2f}",
                template="plotly_dark",
                height=max(250, 40 * n + 100),
                margin=dict(l=0, r=0, t=40, b=0),
            )
            display(fig)

    refresh_btn = widgets.Button(
        description="Yenile",
        button_style="info",
        icon="refresh",
        layout=widgets.Layout(width="100px", height="32px"),
    )

    def _on_refresh(_):
        if refresh_callback:
            refresh_callback()
        _render()

    refresh_btn.on_click(_on_refresh)
    _render()

    return widgets.VBox([
        widgets.HBox([
            widgets.HTML(
                '<div style="color:#cdd6f4;font-size:14px;font-weight:bold;padding:4px 8px;">'
                "Portföy Durumu</div>"
            ),
            refresh_btn,
        ]),
        output,
    ])


# ── 3-Column Transaction Form (v3) ────────────────────────────────────────────

def create_transaction_form_v3(non_stock_assets, transactions_path, on_save_callback=None,
                               wac_state_getter=None, reset_callback=None):
    """
    3 sütunlu işlem giriş formu:
      Sol   — Sabit varlıklar (Altin, Gumus, DOLAR, EURO) fraksiyonel alım/satım
      Orta  — BIST hisseleri (serbest sembol) tam lot alım/satım + fiyat doğrulama
      Sağ   — Sermaye yönetimi (NAKIT_GIRIS / NAKIT_CIKIS)

    wac_state_getter: () -> dict  pozisyon özeti için WAC getter
    reset_callback:   () -> None  portföy sıfırlandıktan sonra çağrılır
    """
    _COL_W = "320px"
    _HDR = "color:#89b4fa;font-size:13px;font-weight:bold;margin-bottom:10px;border-bottom:1px solid #313244;padding-bottom:6px;"
    _LABEL_S = "color:#cdd6f4;font-size:13px;font-weight:bold;margin-bottom:8px;"
    _BTN_ROW = widgets.Layout(gap="6px", justify_content="center", width="100%")
    w_s = {"description_width": "110px"}
    w_l = widgets.Layout(width=_COL_W)

    # ── Shared state ──────────────────────────────────────────────────────────

    known_assets = set(non_stock_assets) | {"BIST100"}

    balance_html = widgets.HTML(value="")
    history_output = widgets.Output()
    positions_output = widgets.Output()

    def _load_tx():
        import os
        try:
            if os.path.exists(transactions_path):
                return load_transactions_csv(transactions_path)
        except Exception:
            pass
        return pd.DataFrame(
            columns=["Tarih", "Varlık Adı", "İşlem Türü", "Fiyat", "Miktar", "Komisyon"]
        )

    def _refresh_balance():
        tx = _load_tx()
        bal = compute_balance(tx)
        color = "#a6e3a1" if bal >= 0 else "#f38ba8"
        balance_html.value = (
            f'<div style="background:#1e1e2e;border:1px solid {color};border-radius:6px;'
            f'padding:10px 18px;margin-bottom:10px;display:inline-block;">'
            f'<span style="color:#a6adc8;font-size:11px;">Nakit Bakiye</span><br>'
            f'<span style="color:{color};font-size:22px;font-weight:bold;">₺{bal:,.2f}</span>'
            f'</div>'
        )

    def _refresh_history():
        history_output.clear_output(wait=True)
        with history_output:
            try:
                tx = _load_tx()
                if len(tx) == 0:
                    print("Henüz işlem yok.")
                    return
                df = tx.sort_values("Tarih", ascending=False).head(20)
                display(df.style.set_properties(**{"font-size": "11px"}))
            except Exception:
                print("Henüz işlem yok.")

    def _refresh_positions():
        positions_output.clear_output(wait=True)
        with positions_output:
            tx = _load_tx()
            pos = compute_position(tx)
            active = {a: u for a, u in pos.items() if u > 0}
            if not active:
                display(widgets.HTML(
                    '<div style="color:#6c7086;font-size:12px;padding:6px 0;">Portföyde henüz varlık yok.</div>'
                ))
                return
            ws = wac_state_getter() if wac_state_getter else {}
            items_html = ""
            for asset, units in active.items():
                w = ws.get(asset, {}).get("wac", 0.0) if ws else 0.0
                wac_str = (
                    f' &nbsp;<span style="color:#a6adc8;">WAC ₺{w:,.2f}</span>'
                    if w > 0 else ""
                )
                items_html += (
                    f'<span style="background:#313244;border-radius:4px;padding:4px 10px;'
                    f'margin:2px 4px 2px 0;display:inline-block;color:#cdd6f4;font-size:12px;">'
                    f'<b>{asset}</b> &nbsp;{units:g}{wac_str}</span>'
                )
            display(widgets.HTML(
                f'<div style="padding:4px 0;line-height:2.2;">{items_html}</div>'
            ))

    def _save_row(asset, islem_type, tarih, fiyat, miktar, komisyon, status_w):
        import os
        new_row = pd.DataFrame([{
            "Tarih": tarih.strftime("%d.%m.%Y"),
            "Varlık Adı": asset,
            "İşlem Türü": islem_type,
            "Fiyat": fiyat,
            "Miktar": miktar,
            "Komisyon": komisyon,
        }])
        write_header = not os.path.exists(transactions_path)
        new_row.to_csv(transactions_path, mode="a", header=write_header, index=False)
        status_w.value = (
            '<div style="color:#a6e3a1;font-size:12px;margin-top:6px;">'
            f"✓ <b>{asset}</b> {islem_type} {miktar:g} @ ₺{fiyat:.2f}"
            "</div>"
        )
        _refresh_balance()
        _refresh_history()
        if on_save_callback:
            on_save_callback()
        _refresh_positions()

    def _show_errors(errors, status_w):
        status_w.value = (
            '<div style="color:#f38ba8;font-size:12px;margin-top:6px;">'
            + "<br>".join(errors) + "</div>"
        )

    # ── Sol panel — sabit varlıklar ───────────────────────────────────────────

    v_asset_dd = widgets.Dropdown(
        options=list(non_stock_assets),
        description="Varlık:",
        style=w_s, layout=w_l,
    )
    v_islem_dd = widgets.Dropdown(
        options=[("Alış", "ALIŞ"), ("Satış", "SATIŞ")],
        description="İşlem:",
        style=w_s, layout=w_l,
    )
    v_date = widgets.DatePicker(
        description="Tarih:",
        value=datetime.today().date(),
        style=w_s, layout=w_l,
    )
    v_price = widgets.FloatText(description="Fiyat (TL):", value=0.0, style=w_s, layout=w_l)
    v_qty = widgets.FloatText(description="Miktar:", value=1.0, style=w_s, layout=w_l)
    v_comm = widgets.FloatText(description="Komisyon (TL):", value=0.0, style=w_s, layout=w_l)
    v_status = widgets.HTML(value="")
    v_save = widgets.Button(description="Kaydet", button_style="success", icon="check",
                            layout=widgets.Layout(width="130px", height="34px"))
    v_clear = widgets.Button(description="Temizle", button_style="warning", icon="times",
                             layout=widgets.Layout(width="130px", height="34px"))

    _GRAM_ASSETS = {"Gram Altin", "Gram Gumus"}

    def _v_update_labels(change=None):
        if v_asset_dd.value in _GRAM_ASSETS:
            v_price.description = "Fiyat (TL/gr):"
            v_qty.description = "Miktar (gr):"
        else:
            v_price.description = "Fiyat (TL):"
            v_qty.description = "Miktar:"

    v_asset_dd.observe(_v_update_labels, names="value")
    _v_update_labels()

    def _v_save(_):
        errs = []
        if not v_date.value:
            errs.append("Tarih boş.")
        if v_price.value <= 0:
            errs.append("Fiyat > 0 olmalı.")
        if v_qty.value <= 0:
            errs.append("Miktar > 0 olmalı.")
        if errs:
            _show_errors(errs, v_status)
            return
        tx = _load_tx()
        biz = validate_transaction(v_asset_dd.value, v_islem_dd.value,
                                   v_price.value, v_qty.value, v_comm.value, tx, known_assets)
        if biz:
            _show_errors(biz, v_status)
            return
        try:
            _save_row(v_asset_dd.value, v_islem_dd.value, v_date.value,
                      v_price.value, v_qty.value, v_comm.value, v_status)
        except Exception as e:
            _show_errors([str(e)], v_status)

    def _v_clear(_):
        v_price.value = 0.0
        v_qty.value = 1.0
        v_comm.value = 0.0
        v_date.value = datetime.today().date()
        v_status.value = ""

    v_save.on_click(_v_save)
    v_clear.on_click(_v_clear)

    left_panel = widgets.VBox([
        widgets.HTML(f'<div style="{_HDR}">📦 Varlık Alım / Satım</div>'),
        v_asset_dd, v_islem_dd, v_date,
        v_price, v_qty, v_comm,
        widgets.HBox([v_save, v_clear], layout=_BTN_ROW),
        v_status,
    ], layout=widgets.Layout(padding="0"))

    # ── Orta panel — hisse ───────────────────────────────────────────────────

    h_ticker = widgets.Text(
        description="Hisse:",
        placeholder="ASELS, EREGL...",
        style=w_s, layout=w_l,
    )
    h_islem_dd = widgets.Dropdown(
        options=[("Alış", "ALIŞ"), ("Satış", "SATIŞ")],
        description="İşlem:",
        style=w_s, layout=w_l,
    )
    h_date = widgets.DatePicker(
        description="Tarih:",
        value=datetime.today().date(),
        style=w_s, layout=w_l,
    )
    h_price = widgets.FloatText(description="Fiyat (TL):", value=0.0, style=w_s, layout=w_l)
    h_lot = widgets.IntText(description="Lot (adet):", value=1, style=w_s, layout=w_l)
    h_comm = widgets.FloatText(description="Komisyon (TL):", value=0.0, style=w_s, layout=w_l)
    h_status = widgets.HTML(value="")
    h_save = widgets.Button(description="Kaydet", button_style="success", icon="check",
                            layout=widgets.Layout(width="130px", height="34px"))
    h_clear = widgets.Button(description="Temizle", button_style="warning", icon="times",
                             layout=widgets.Layout(width="130px", height="34px"))

    def _normalize_ticker(t: str) -> str:
        return t.strip().upper()

    def _h_save(_):
        ticker = _normalize_ticker(h_ticker.value)
        errs = []
        if not ticker:
            errs.append("Hisse sembolü boş olamaz.")
        if not h_date.value:
            errs.append("Tarih boş.")
        if h_price.value <= 0:
            errs.append("Fiyat > 0 olmalı.")
        if h_lot.value <= 0:
            errs.append("Lot > 0 olmalı.")
        if errs:
            _show_errors(errs, h_status)
            return

        if h_islem_dd.value == "ALIŞ":
            h_status.value = (
                '<div style="color:#cba6f7;font-size:12px;margin-top:6px;">⏳ Sembol doğrulanıyor...</div>'
            )
            valid, err_msg = validate_stock_symbol(ticker)
            if not valid:
                _show_errors([err_msg], h_status)
                return

        tx = _load_tx()
        biz = validate_transaction(ticker, h_islem_dd.value,
                                   h_price.value, float(h_lot.value), h_comm.value, tx, known_assets)
        if biz:
            _show_errors(biz, h_status)
            return
        try:
            _save_row(ticker, h_islem_dd.value, h_date.value,
                      h_price.value, float(h_lot.value), h_comm.value, h_status)
        except Exception as e:
            _show_errors([str(e)], h_status)

    def _h_clear(_):
        h_ticker.value = ""
        h_price.value = 0.0
        h_lot.value = 1
        h_comm.value = 0.0
        h_date.value = datetime.today().date()
        h_status.value = ""

    h_save.on_click(_h_save)
    h_clear.on_click(_h_clear)

    mid_panel = widgets.VBox([
        widgets.HTML(f'<div style="{_HDR}">📈 Hisse Alım / Satım</div>'),
        h_ticker, h_islem_dd, h_date,
        h_price, h_lot, h_comm,
        widgets.HBox([h_save, h_clear], layout=_BTN_ROW),
        h_status,
    ], layout=widgets.Layout(padding="0"))

    # ── Sağ panel — sermaye ───────────────────────────────────────────────────

    s_islem_dd = widgets.Dropdown(
        options=[("Para Yatır", "NAKIT_GIRIS"), ("Para Çek", "NAKIT_CIKIS")],
        description="İşlem:",
        style=w_s, layout=w_l,
    )
    s_date = widgets.DatePicker(
        description="Tarih:",
        value=datetime.today().date(),
        style=w_s, layout=w_l,
    )
    s_tutar = widgets.FloatText(description="Tutar (TL):", value=0.0, style=w_s, layout=w_l)
    s_status = widgets.HTML(value="")
    s_save = widgets.Button(description="Kaydet", button_style="success", icon="check",
                            layout=widgets.Layout(width="130px", height="34px"))
    s_clear = widgets.Button(description="Temizle", button_style="warning", icon="times",
                             layout=widgets.Layout(width="130px", height="34px"))

    def _s_save(_):
        if s_tutar.value <= 0:
            _show_errors(["Tutar > 0 olmalı."], s_status)
            return
        if not s_date.value:
            _show_errors(["Tarih boş."], s_status)
            return

        islem = s_islem_dd.value
        if islem == "NAKIT_CIKIS":
            tx = _load_tx()
            bal = compute_balance(tx)
            if s_tutar.value > bal:
                _show_errors([f"Yetersiz bakiye. Çekilmek istenen: ₺{s_tutar.value:,.2f} | Mevcut: ₺{bal:,.2f}"], s_status)
                return

        try:
            _save_row("NAKIT", islem, s_date.value, s_tutar.value, 1.0, 0.0, s_status)
            s_status.value = (
                '<div style="color:#a6e3a1;font-size:12px;margin-top:6px;">'
                f"✓ {('Yatırıldı' if islem == 'NAKIT_GIRIS' else 'Çekildi')}: ₺{s_tutar.value:,.2f}"
                "</div>"
            )
        except Exception as e:
            _show_errors([str(e)], s_status)

    def _s_clear(_):
        s_tutar.value = 0.0
        s_date.value = datetime.today().date()
        s_status.value = ""

    s_save.on_click(_s_save)
    s_clear.on_click(_s_clear)

    right_panel = widgets.VBox([
        widgets.HTML(f'<div style="{_HDR}">💰 Sermaye Yönetimi</div>'),
        s_islem_dd, s_date, s_tutar,
        widgets.HBox([s_save, s_clear], layout=_BTN_ROW),
        s_status,
    ], layout=widgets.Layout(padding="0"))

    # ── Sütun stillerini uygula ───────────────────────────────────────────────

    def _styled(panel):
        return widgets.VBox(
            [panel],
            layout=widgets.Layout(
                border="1px solid #313244",
                border_radius="8px",
                background_color="#1e1e2e",
                padding="14px",
                min_width="280px",
                flex="1",
            ),
        )

    three_cols = widgets.HBox(
        [_styled(left_panel), _styled(mid_panel), _styled(right_panel)],
        layout=widgets.Layout(gap="8px", flex_wrap="wrap"),
    )

    # ── Portföy sıfırlama ─────────────────────────────────────────────────────

    reset_status = widgets.HTML(value="")
    reset_btn = widgets.Button(
        description="Portföyü Sıfırla",
        button_style="danger",
        icon="trash",
        layout=widgets.Layout(width="180px", height="34px"),
    )
    confirm_btn = widgets.Button(
        description="Evet, Sil",
        button_style="danger",
        icon="warning",
        layout=widgets.Layout(width="130px", height="34px", display="none"),
    )
    cancel_btn = widgets.Button(
        description="İptal",
        button_style="info",
        icon="times",
        layout=widgets.Layout(width="100px", height="34px", display="none"),
    )

    def _on_reset_click(_):
        reset_status.value = (
            '<div style="color:#f38ba8;font-size:12px;padding:4px 0;">'
            "⚠️ Tüm işlemler kalıcı olarak silinecek. Emin misin?"
            "</div>"
        )
        confirm_btn.layout.display = ""
        cancel_btn.layout.display = ""
        reset_btn.layout.display = "none"

    def _on_confirm(_):
        import os
        if os.path.exists(transactions_path):
            os.remove(transactions_path)
        reset_status.value = (
            '<div style="color:#a6e3a1;font-size:12px;padding:4px 0;">✓ Portföy sıfırlandı.</div>'
        )
        confirm_btn.layout.display = "none"
        cancel_btn.layout.display = "none"
        reset_btn.layout.display = ""
        _refresh_balance()
        _refresh_history()
        _refresh_positions()
        if reset_callback:
            reset_callback()

    def _on_cancel(_):
        reset_status.value = ""
        confirm_btn.layout.display = "none"
        cancel_btn.layout.display = "none"
        reset_btn.layout.display = ""

    reset_btn.on_click(_on_reset_click)
    confirm_btn.on_click(_on_confirm)
    cancel_btn.on_click(_on_cancel)

    reset_section = widgets.VBox([
        widgets.HTML(
            '<div style="border-top:1px solid #45475a;margin-top:10px;padding-top:8px;">'
            '<span style="color:#f38ba8;font-size:11px;font-weight:bold;">⚠ TEHLİKELİ BÖLGE</span></div>'
        ),
        widgets.HBox(
            [reset_btn, confirm_btn, cancel_btn],
            layout=widgets.Layout(gap="6px", align_items="center"),
        ),
        reset_status,
    ])

    # İlk render
    _refresh_balance()
    _refresh_history()
    _refresh_positions()

    return widgets.VBox([
        widgets.HTML(
            '<div style="color:#89dceb;font-size:13px;font-weight:bold;margin-bottom:6px;">📊 Mevcut Pozisyonlar</div>'
        ),
        positions_output,
        balance_html,
        three_cols,
        reset_section,
        widgets.HTML(f'<div style="{_LABEL_S}">Son İşlemler (en fazla 20)</div>'),
        history_output,
    ])


# ── v2 Form (backward compat) ─────────────────────────────────────────────────

def create_transaction_form_v2(asset_names, transactions_path, on_save_callback=None):
    """Tek sütunlu gelişmiş form. Bakiye takibi + lot validasyonu."""
    _CARD = "background:#1e1e2e;border:1px solid #313244;border-radius:8px;padding:16px;margin:8px 0;"
    _LABEL = "color:#cdd6f4;font-size:13px;font-weight:bold;margin-bottom:8px;"
    w_style = {"description_width": "130px"}
    w_layout = widgets.Layout(width="320px")

    asset_dd = widgets.Dropdown(options=asset_names, description="Varlık:", style=w_style, layout=w_layout)
    islem_dd = widgets.Dropdown(
        options=[("Alış (ALIŞ)", "ALIŞ"), ("Satış (SATIŞ)", "SATIŞ"),
                 ("Para Yatır (NAKIT_GIRIS)", "NAKIT_GIRIS"), ("Para Çek (NAKIT_CIKIS)", "NAKIT_CIKIS")],
        description="İşlem Türü:", style=w_style, layout=w_layout,
    )
    date_picker = widgets.DatePicker(description="Tarih:", value=datetime.today().date(),
                                     style=w_style, layout=w_layout)
    price_input = widgets.FloatText(description="Fiyat (TL):", value=0.0, style=w_style, layout=w_layout)
    qty_float = widgets.FloatText(description="Miktar:", value=1.0, style=w_style, layout=w_layout)
    qty_int = widgets.IntText(description="Miktar (lot):", value=1, style=w_style, layout=w_layout)
    qty_box = widgets.VBox([qty_float])
    comm_input = widgets.FloatText(description="Komisyon (TL):", value=0.0, style=w_style, layout=w_layout)
    balance_html = widgets.HTML(value="")
    status_html = widgets.HTML(value="")
    history_output = widgets.Output()

    def _load_tx():
        import os
        try:
            if os.path.exists(transactions_path):
                return load_transactions_csv(transactions_path)
        except Exception:
            pass
        return pd.DataFrame(columns=["Tarih", "Varlık Adı", "İşlem Türü", "Fiyat", "Miktar", "Komisyon"])

    def _refresh_balance():
        tx = _load_tx()
        bal = compute_balance(tx)
        color = "#a6e3a1" if bal >= 0 else "#f38ba8"
        balance_html.value = (
            f'<div style="background:#1e1e2e;border:1px solid {color};border-radius:6px;'
            f'padding:8px 14px;margin-bottom:8px;display:inline-block;">'
            f'<span style="color:#a6adc8;font-size:11px;">Nakit Bakiye</span><br>'
            f'<span style="color:{color};font-size:18px;font-weight:bold;">₺{bal:,.2f}</span></div>'
        )

    def _refresh_history():
        history_output.clear_output(wait=True)
        with history_output:
            try:
                tx = _load_tx()
                if len(tx) == 0:
                    print("Henüz işlem yok.")
                    return
                display(tx.sort_values("Tarih", ascending=False).head(20)
                        .style.set_properties(**{"font-size": "11px"}))
            except Exception:
                print("Henüz işlem yok.")

    def _update_qty(change=None):
        if asset_dd.value in LOT_ASSETS and islem_dd.value in ("ALIŞ", "SATIŞ"):
            qty_box.children = [qty_int]
        else:
            qty_box.children = [qty_float]

    def _get_miktar():
        if asset_dd.value in LOT_ASSETS and islem_dd.value in ("ALIŞ", "SATIŞ"):
            return float(qty_int.value)
        return qty_float.value

    asset_dd.observe(_update_qty, names="value")
    islem_dd.observe(_update_qty, names="value")

    save_btn = widgets.Button(description="Kaydet", button_style="success", icon="check",
                              layout=widgets.Layout(width="140px", height="36px"))
    clear_btn = widgets.Button(description="Temizle", button_style="warning", icon="times",
                               layout=widgets.Layout(width="140px", height="36px"))

    def _on_save(_):
        import os
        errs = []
        if not date_picker.value:
            errs.append("Tarih boş olamaz.")
        if price_input.value <= 0:
            errs.append("Fiyat 0'dan büyük olmalı.")
        miktar = _get_miktar()
        if miktar <= 0:
            errs.append("Miktar 0'dan büyük olmalı.")
        if errs:
            status_html.value = '<div style="color:#f38ba8;font-size:12px;margin-top:6px;">' + "<br>".join(errs) + "</div>"
            return
        tx = _load_tx()
        biz = validate_transaction(asset_dd.value, islem_dd.value, price_input.value, miktar, comm_input.value, tx)
        if biz:
            status_html.value = '<div style="color:#f38ba8;font-size:12px;margin-top:6px;">' + "<br>".join(biz) + "</div>"
            return
        try:
            new_row = pd.DataFrame([{"Tarih": date_picker.value.strftime("%d.%m.%Y"), "Varlık Adı": asset_dd.value,
                                     "İşlem Türü": islem_dd.value, "Fiyat": price_input.value,
                                     "Miktar": miktar, "Komisyon": comm_input.value}])
            new_row.to_csv(transactions_path, mode="a", header=not os.path.exists(transactions_path), index=False)
            status_html.value = (
                '<div style="color:#a6e3a1;font-size:12px;margin-top:6px;">'
                f"Kaydedildi: <b>{asset_dd.value}</b> {islem_dd.value} {miktar:g} @ ₺{price_input.value:.2f}</div>"
            )
            _refresh_balance()
            _refresh_history()
            if on_save_callback:
                on_save_callback()
        except Exception as e:
            status_html.value = f'<div style="color:#f38ba8;font-size:12px;margin-top:6px;">Hata: {e}</div>'

    def _on_clear(_):
        price_input.value = 0.0
        qty_float.value = 1.0
        qty_int.value = 1
        comm_input.value = 0.0
        date_picker.value = datetime.today().date()
        status_html.value = ""

    save_btn.on_click(_on_save)
    clear_btn.on_click(_on_clear)
    _refresh_balance()
    _refresh_history()

    return widgets.VBox([
        widgets.HTML(f'<div style="{_CARD}">'),
        widgets.VBox([
            widgets.HTML(f'<div style="{_LABEL}">Yeni İşlem Ekle</div>'),
            balance_html, asset_dd, islem_dd, date_picker,
            price_input, qty_box, comm_input,
            widgets.HBox([save_btn, clear_btn], layout=widgets.Layout(gap="8px")),
            status_html,
        ], layout=widgets.Layout(padding="16px")),
        widgets.HTML(f'<div style="{_LABEL}">Son İşlemler (en fazla 20)</div>'),
        history_output,
    ])


# ── Shared widget helpers (widgets.py'den bağımsız — sadece bu notebook için) ─

def create_date_range_picker(min_date, max_date, default_start, default_end):
    style = {"description_width": "80px"}
    layout = widgets.Layout(width="200px")
    start_picker = widgets.DatePicker(
        description="Başlangıç:", value=default_start.date(),
        min=min_date.date(), max=max_date.date(), style=style, layout=layout,
    )
    end_picker = widgets.DatePicker(
        description="Bitiş:", value=default_end.date(),
        min=min_date.date(), max=max_date.date(), style=style, layout=layout,
    )
    return start_picker, end_picker


def create_currency_toggle():
    return widgets.ToggleButtons(
        options=[("₺ TL (Nominal)", "TL"), ("$ USD", "USD"), ("Reel (TÜFE)", "REAL")],
        value="TL",
        description="Para Birimi:",
        style={"button_width": "120px", "description_width": "90px"},
    )


def wire_dashboard(render_fn, output_widget, start_picker, end_picker, currency_toggle):
    def _on_change(change):
        if change["name"] != "value":
            return
        start = datetime.combine(start_picker.value, datetime.min.time())
        end = datetime.combine(end_picker.value, datetime.min.time())
        if start >= end:
            return
        currency = currency_toggle.value
        with output_widget:
            output_widget.clear_output(wait=True)
            render_fn(
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                currency=currency,
            )

    start_picker.observe(_on_change, names="value")
    end_picker.observe(_on_change, names="value")
    currency_toggle.observe(_on_change, names="value")

    controls = widgets.HBox(
        [start_picker, end_picker, currency_toggle],
        layout=widgets.Layout(align_items="center", gap="16px", padding="8px 0"),
    )
    return widgets.VBox([controls, output_widget])


# ── Portfolio Performance Index ───────────────────────────────────────────────

def compute_portfolio_performance_index(
    portfolio_values: pd.DataFrame,
    transactions: pd.DataFrame,
    currency: str = "TL",
) -> pd.Series:
    """
    Net Değer / Kümülatif Mevduat × 100.

    Net Değer  = varlık değeri + nakit bakiye (her gün sonu)
    Mevduat    = kümülatif NAKIT_GIRIS - NAKIT_CIKIS (net yatırılan sermaye)

    Returns: pd.Series index=portfolio_values.index, values=index başlangıç~100
    """
    value_col = "total_value_tl" if currency != "USD" else "total_value_usd"

    tx_sorted = transactions.sort_values("Tarih").reset_index(drop=True)
    tx_list = tx_sorted
    n_tx = len(tx_list)
    tx_idx = 0

    cash = 0.0
    deposits = 0.0  # kümülatif net yatırım (NAKIT_GIRIS - NAKIT_CIKIS)

    result = {}

    for date in portfolio_values.index:
        # O tarihe kadar gerçekleşen işlemleri işle
        while tx_idx < n_tx and tx_list.loc[tx_idx, "Tarih"] <= date:
            row = tx_list.loc[tx_idx]
            t = row["İşlem Türü"]
            fiyat = float(row["Fiyat"])
            miktar = float(row["Miktar"])
            komisyon = float(row["Komisyon"])
            if t == "NAKIT_GIRIS":
                cash += fiyat * miktar
                deposits += fiyat * miktar
            elif t == "NAKIT_CIKIS":
                cash -= fiyat * miktar
                deposits -= fiyat * miktar
            elif t == "ALIŞ":
                cash -= fiyat * miktar + komisyon
            elif t == "SATIŞ":
                cash += fiyat * miktar - komisyon
            tx_idx += 1

        asset_value = portfolio_values.loc[date, value_col]
        net_worth = asset_value + cash
        result[date] = (net_worth / deposits * 100) if deposits > 0 else float("nan")

    return pd.Series(result, name="Portföy")
