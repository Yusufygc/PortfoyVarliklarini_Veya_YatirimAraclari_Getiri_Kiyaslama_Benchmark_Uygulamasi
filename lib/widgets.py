from datetime import datetime

import pandas as pd
import ipywidgets as widgets
from IPython.display import display


def create_date_range_picker(
    min_date: datetime,
    max_date: datetime,
    default_start: datetime,
    default_end: datetime,
) -> tuple:
    style = {"description_width": "80px"}
    layout = widgets.Layout(width="200px")

    start_picker = widgets.DatePicker(
        description="Başlangıç:",
        value=default_start.date(),
        min=min_date.date(),
        max=max_date.date(),
        style=style,
        layout=layout,
    )
    end_picker = widgets.DatePicker(
        description="Bitiş:",
        value=default_end.date(),
        min=min_date.date(),
        max=max_date.date(),
        style=style,
        layout=layout,
    )
    return start_picker, end_picker


def create_currency_toggle() -> widgets.ToggleButtons:
    return widgets.ToggleButtons(
        options=[("₺ TL (Nominal)", "TL"), ("$ USD", "USD"), ("Reel (TÜFE)", "REAL")],
        value="TL",
        description="Para Birimi:",
        style={"button_width": "120px", "description_width": "90px"},
    )


def wire_dashboard(
    render_fn,
    output_widget: widgets.Output,
    start_picker: widgets.DatePicker,
    end_picker: widgets.DatePicker,
    currency_toggle: widgets.ToggleButtons,
) -> widgets.VBox:
    """
    Tüm kontrollere .observe() bağlar.
    render_fn(start_date, end_date, currency) çağrısı tüm grafikleri output_widget'a yazar.

    Returns: VBox (kontroller + output)
    """
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


def create_transaction_form(
    asset_names: list,
    transactions_path: str,
    on_save_callback=None,
) -> widgets.VBox:
    """
    İnteraktif işlem giriş formu.
    Validasyon → CSV'ye append → on_save_callback() çağrısı.

    Returns: VBox (form + geçmiş tablosu)
    """
    _CARD = "background:#1e1e2e;border:1px solid #313244;border-radius:8px;padding:16px;margin:8px 0;"
    _LABEL = "color:#cdd6f4;font-size:13px;font-weight:bold;margin-bottom:8px;"

    w_style = {"description_width": "130px"}
    w_layout = widgets.Layout(width="320px")

    asset_dd = widgets.Dropdown(
        options=asset_names,
        description="Varlık:",
        style=w_style, layout=w_layout,
    )
    islem_dd = widgets.Dropdown(
        options=[("Alış (ALIŞ)", "ALIŞ"), ("Satış (SATIŞ)", "SATIŞ")],
        description="İşlem Türü:",
        style=w_style, layout=w_layout,
    )
    date_picker = widgets.DatePicker(
        description="Tarih:",
        value=datetime.today().date(),
        style=w_style, layout=w_layout,
    )
    price_input = widgets.FloatText(
        description="Fiyat (TL):",
        value=0.0, min=0.0,
        style=w_style, layout=w_layout,
    )
    qty_input = widgets.FloatText(
        description="Miktar (adet):",
        value=1.0, min=0.0,
        style=w_style, layout=w_layout,
    )
    comm_input = widgets.FloatText(
        description="Komisyon (TL):",
        value=0.0, min=0.0,
        style=w_style, layout=w_layout,
    )

    save_btn = widgets.Button(
        description="Kaydet",
        button_style="success",
        icon="check",
        layout=widgets.Layout(width="140px", height="36px"),
    )
    clear_btn = widgets.Button(
        description="Temizle",
        button_style="warning",
        icon="times",
        layout=widgets.Layout(width="140px", height="36px"),
    )
    status_html = widgets.HTML(value="")

    history_output = widgets.Output()

    def _refresh_history():
        history_output.clear_output(wait=True)
        with history_output:
            try:
                df = pd.read_csv(transactions_path)
                df = df.sort_values("Tarih", ascending=False).head(20)
                display(df.style.set_properties(**{"font-size": "11px"}))
            except Exception:
                print("Henüz işlem yok.")

    def _on_save(_):
        errors = []
        if not date_picker.value:
            errors.append("Tarih boş olamaz.")
        if price_input.value <= 0:
            errors.append("Fiyat 0'dan büyük olmalı.")
        if qty_input.value <= 0:
            errors.append("Miktar 0'dan büyük olmalı.")

        if errors:
            status_html.value = (
                f'<div style="color:#f38ba8;font-size:12px;margin-top:6px;">'
                + "<br>".join(errors)
                + "</div>"
            )
            return

        try:
            new_row = pd.DataFrame([{
                "Tarih": date_picker.value.strftime("%d.%m.%Y"),
                "Varlık Adı": asset_dd.value,
                "İşlem Türü": islem_dd.value,
                "Fiyat": price_input.value,
                "Miktar": qty_input.value,
                "Komisyon": comm_input.value,
            }])
            import os
            write_header = not os.path.exists(transactions_path)
            new_row.to_csv(transactions_path, mode="a", header=write_header, index=False)

            status_html.value = (
                f'<div style="color:#a6e3a1;font-size:12px;margin-top:6px;">'
                f"Kaydedildi: <b>{asset_dd.value}</b> {islem_dd.value} "
                f"{qty_input.value} adet @ {price_input.value:.2f} TL"
                "</div>"
            )
            _refresh_history()
            if on_save_callback:
                on_save_callback()
        except Exception as e:
            status_html.value = (
                f'<div style="color:#f38ba8;font-size:12px;margin-top:6px;">'
                f"Hata: {e}</div>"
            )

    def _on_clear(_):
        price_input.value = 0.0
        qty_input.value = 1.0
        comm_input.value = 0.0
        date_picker.value = datetime.today().date()
        status_html.value = ""

    save_btn.on_click(_on_save)
    clear_btn.on_click(_on_clear)

    form_box = widgets.VBox([
        widgets.HTML(f'<div style="{_LABEL}">Yeni İşlem Ekle</div>'),
        asset_dd, islem_dd, date_picker,
        price_input, qty_input, comm_input,
        widgets.HBox([save_btn, clear_btn], layout=widgets.Layout(gap="8px")),
        status_html,
    ], layout=widgets.Layout(**{k: v for k, v in {"padding": "16px"}.items()}))

    history_label = widgets.HTML(
        f'<div style="{_LABEL}">Son İşlemler (en fazla 20)</div>'
    )

    _refresh_history()

    return widgets.VBox([
        widgets.HTML(f'<div style="{_CARD}">'),
        form_box,
        history_label,
        history_output,
    ])
