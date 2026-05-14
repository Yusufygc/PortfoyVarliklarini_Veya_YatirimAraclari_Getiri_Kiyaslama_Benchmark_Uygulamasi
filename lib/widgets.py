from datetime import datetime

import pandas as pd
import ipywidgets as widgets
from IPython.display import display


DATE_DISPLAY_FORMAT = "%d/%m/%Y"


def _coerce_date(value):
    if hasattr(value, "date"):
        return value.date()
    return value


def _format_date_display(value) -> str:
    return _coerce_date(value).strftime(DATE_DISPLAY_FORMAT)


def _create_date_text(description="Tarih:", value=None, style=None, layout=None):
    kwargs = {
        "description": description,
        "value": _format_date_display(value or datetime.today()),
        "placeholder": "GG/AA/YYYY",
        "style": style or {},
    }
    if layout is not None:
        kwargs["layout"] = layout
    return widgets.Text(**kwargs)


def _parse_date_input(widget: widgets.Text):
    try:
        parsed = datetime.strptime(widget.value.strip(), DATE_DISPLAY_FORMAT).date()
    except ValueError as exc:
        raise ValueError(f"{widget.description} GG/AA/YYYY formatinda olmali.") from exc

    min_date = getattr(widget, "_min_date", None)
    max_date = getattr(widget, "_max_date", None)
    if min_date and parsed < min_date:
        raise ValueError(f"{widget.description} en erken {_format_date_display(min_date)} olabilir.")
    if max_date and parsed > max_date:
        raise ValueError(f"{widget.description} en gec {_format_date_display(max_date)} olabilir.")
    return parsed


def create_date_range_picker(
    min_date: datetime,
    max_date: datetime,
    default_start: datetime,
    default_end: datetime,
) -> tuple:
    style = {"description_width": "80px"}
    layout = widgets.Layout(width="200px")

    start_picker = widgets.Text(
        description="Başlangıç:",
        value=_format_date_display(default_start),
        placeholder="GG/AA/YYYY",
        style=style,
        layout=layout,
    )
    start_picker._min_date = _coerce_date(min_date)
    start_picker._max_date = _coerce_date(max_date)

    end_picker = widgets.Text(
        description="Bitiş:",
        value=_format_date_display(default_end),
        placeholder="GG/AA/YYYY",
        style=style,
        layout=layout,
    )
    end_picker._min_date = _coerce_date(min_date)
    end_picker._max_date = _coerce_date(max_date)
    return start_picker, end_picker


def create_currency_toggle() -> widgets.ToggleButtons:
    return widgets.ToggleButtons(
        options=[("₺ TL (Nominal)", "TL"), ("$ USD", "USD"), ("Reel (TÜFE)", "REAL")],
        value="TL",
        description="Para Birimi:",
        style={"button_width": "120px", "description_width": "90px"},
    )


class AssetCheckboxSelector(widgets.HBox):
    def __init__(self, asset_names: list):
        self._asset_checkboxes = [
            widgets.Checkbox(
                value=True,
                description=name,
                indent=False,
                layout=widgets.Layout(width="150px", margin="0"),
            )
            for name in asset_names
        ]
        label = widgets.HTML(
            value="<b>Varliklar:</b>",
            layout=widgets.Layout(width="72px", margin="2px 0 0 0"),
        )
        grid = widgets.GridBox(
            children=self._asset_checkboxes,
            layout=widgets.Layout(
                grid_template_columns="repeat(2, 150px)",
                grid_gap="2px 8px",
                align_items="center",
            ),
        )
        super().__init__(
            [label, grid],
            layout=widgets.Layout(
                align_items="flex-start",
                gap="6px",
                padding="8px 0",
                width="390px",
            ),
        )

    @property
    def value(self) -> tuple:
        return tuple(cb.description for cb in self._asset_checkboxes if cb.value)

    @value.setter
    def value(self, selected_assets) -> None:
        selected = set(selected_assets or [])
        for cb in self._asset_checkboxes:
            cb.value = cb.description in selected


def create_asset_selector(asset_names: list) -> AssetCheckboxSelector:
    return AssetCheckboxSelector(asset_names)


def _get_selected_assets(asset_selector) -> list:
    if asset_selector is None:
        return None
    return list(asset_selector.value)


def _observe_asset_selector(asset_selector, handler) -> None:
    if asset_selector is None:
        return
    checkboxes = getattr(asset_selector, "_asset_checkboxes", None)
    if checkboxes is not None:
        for checkbox in checkboxes:
            checkbox.observe(handler, names="value")
        return
    asset_selector.observe(handler, names="value")


def _asset_selector_widget(asset_selector):
    if asset_selector is None:
        return None
    return asset_selector


def wire_dashboard(
    render_fn,
    output_widget: widgets.Output,
    start_picker: widgets.DatePicker,
    end_picker: widgets.DatePicker,
    currency_toggle: widgets.ToggleButtons,
    asset_selector: widgets.Widget = None,
) -> widgets.VBox:
    """
    Tüm kontrollere .observe() bağlar.
    render_fn(start_date, end_date, currency) çağrısı tüm grafikleri output_widget'a yazar.

    Returns: VBox (kontroller + output)
    """
    def _on_change(change):
        if change["name"] != "value":
            return
        try:
            start_date_value = _parse_date_input(start_picker)
            end_date_value = _parse_date_input(end_picker)
            start = datetime.combine(start_date_value, datetime.min.time())
            end = datetime.combine(end_date_value, datetime.min.time())
            if start >= end:
                raise ValueError("Başlangıç tarihi bitiş tarihinden önce olmalı.")
        except ValueError as exc:
            status_html.value = (
                '<div style="color:#f38ba8;font-size:12px;padding:2px 0;">'
                f"{exc}</div>"
            )
            return
        selected_assets = None
        if asset_selector is not None:
            selected_assets = _get_selected_assets(asset_selector)
            if not selected_assets:
                status_html.value = (
                    '<div style="color:#f38ba8;font-size:12px;padding:2px 0;">'
                    "En az bir varlik secilmeli.</div>"
                )
                return
        status_html.value = ""
        currency = currency_toggle.value
        with output_widget:
            output_widget.clear_output(wait=True)
            kwargs = {
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": end.strftime("%Y-%m-%d"),
                "currency": currency,
            }
            if asset_selector is not None:
                kwargs["selected_assets"] = selected_assets
            render_fn(**kwargs)

    start_picker.observe(_on_change, names="value")
    end_picker.observe(_on_change, names="value")
    currency_toggle.observe(_on_change, names="value")
    _observe_asset_selector(asset_selector, _on_change)

    date_controls = widgets.HBox(
        [start_picker, end_picker],
        layout=widgets.Layout(align_items="center", gap="16px"),
    )
    controls_children = [date_controls, currency_toggle]
    selector_widget = _asset_selector_widget(asset_selector)
    if selector_widget is not None:
        controls_children.append(selector_widget)
    controls = widgets.HBox(
        controls_children,
        layout=widgets.Layout(
            align_items="flex-start",
            gap="18px",
            padding="8px 0",
            flex_flow="row wrap",
        ),
    )
    status_html = widgets.HTML(value="")
    return widgets.VBox([controls, status_html, output_widget])


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
    date_picker = _create_date_text(
        description="Tarih:",
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
        try:
            tarih = _parse_date_input(date_picker)
        except ValueError as e:
            errors.append(str(e))
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
                "Tarih": tarih.strftime("%d.%m.%Y"),
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
        date_picker.value = _format_date_display(datetime.today())
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
