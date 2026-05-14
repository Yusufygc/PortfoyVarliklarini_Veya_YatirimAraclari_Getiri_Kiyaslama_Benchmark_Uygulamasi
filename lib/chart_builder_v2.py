import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import ipywidgets as widgets
    from IPython.display import display
    HAS_WIDGETS = True
except ImportError:
    HAS_WIDGETS = False

BENCHMARK_COLORS = [
    "#F4A460", "#A9A9A9", "#4682B4", "#20B2AA", "#9370DB", "#CD853F"
]
PORTFOLIO_COLOR = "#E63946"
GAIN_COLOR = "#2DC653"
LOSS_COLOR = "#E63946"
TURKISH_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


def format_turkish_date(value) -> str:
    ts = pd.Timestamp(value)
    return f"{ts.day:02d} {TURKISH_MONTHS[ts.month - 1]} {ts.year}"


def format_turkish_period(value, freq: str) -> str:
    ts = pd.Timestamp(value)
    if freq == "ME":
        return f"{TURKISH_MONTHS[ts.month - 1]} {ts.year}"
    quarter = ((ts.month - 1) // 3) + 1
    return f"{quarter}. Çeyrek {ts.year}"


def _apply_turkish_month_axis(fig: go.Figure, dates) -> None:
    idx = pd.DatetimeIndex(pd.to_datetime(dates)).dropna()
    if idx.empty:
        return
    start = idx.min().replace(day=1)
    end = idx.max().replace(day=1)
    ticks = pd.date_range(start, end, freq="MS")
    if len(ticks) == 0:
        return
    step = max(1, len(ticks) // 12)
    ticks = ticks[::step]
    fig.update_xaxes(
        tickmode="array",
        tickvals=ticks,
        ticktext=[f"{TURKISH_MONTHS[t.month - 1]} {t.year}" for t in ticks],
    )


def build_performance_line_chart_v2(
    portfolio_series,
    benchmark_series: pd.DataFrame,
    currency_label: str,
    title: str = "Portföy vs Benchmark",
) -> go.Figure:
    """
    İyileştirilmiş performans grafiği:
    - Range selector butonları (1A, 3A, 6A, YBB, 1Y, Tümü)
    - Range slider (mini zaman çubuğu)
    - Başlangıç=100 referans çizgisi
    - Hover formatında işaret (+/-)
    """
    fig = go.Figure()

    for i, col in enumerate(benchmark_series.columns):
        s = benchmark_series[col].dropna()
        color = BENCHMARK_COLORS[i % len(BENCHMARK_COLORS)]
        customdata = pd.DataFrame({
            "date": [format_turkish_date(d) for d in s.index],
            "ret": (s.values - 100).round(2),
        }).values
        fig.add_trace(go.Scatter(
            x=s.index,
            y=s.values,
            name=col,
            line=dict(width=1.5, color=color),
            opacity=0.75,
            legendgroup=col,
            hovertemplate=(
                f"<b>{col}</b><br>"
                "Tarih: %{customdata[0]}<br>"
                f"Değer: %{{y:.1f}} ({currency_label})<br>"
                "Başlangıçtan: %{customdata[1]:+.2f}%<extra></extra>"
            ),
            customdata=customdata,
        ))

    if portfolio_series is not None:
        p = portfolio_series.dropna()
        customdata = pd.DataFrame({
            "date": [format_turkish_date(d) for d in p.index],
            "ret": (p.values - 100).round(2),
        }).values
        fig.add_trace(go.Scatter(
            x=p.index,
            y=p.values,
            name="Portföy",
            line=dict(width=3, color=PORTFOLIO_COLOR),
            opacity=1.0,
            legendgroup="Portföy",
            hovertemplate=(
                "<b>Portföy</b><br>"
                "Tarih: %{customdata[0]}<br>"
                f"Değer: %{{y:.1f}} ({currency_label})<br>"
                "Başlangıçtan: %{customdata[1]:+.2f}%<extra></extra>"
            ),
            customdata=customdata,
        ))

    fig.add_hline(
        y=100,
        line=dict(color="#6c7086", width=1, dash="dot"),
        annotation_text="Başlangıç (100)",
        annotation_position="bottom right",
        annotation_font=dict(size=10, color="#6c7086"),
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        xaxis=dict(
            title="Tarih",
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1A", step="month", stepmode="backward"),
                    dict(count=3, label="3A", step="month", stepmode="backward"),
                    dict(count=6, label="6A", step="month", stepmode="backward"),
                    dict(count=1, label="YBB", step="year", stepmode="todate"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(step="all", label="Tümü"),
                ],
                bgcolor="#313244",
                activecolor="#585b70",
                font=dict(color="#cdd6f4", size=11),
            ),
            rangeslider=dict(visible=True, bgcolor="#1e1e2e", thickness=0.06),
            type="date",
        ),
        yaxis_title=f"Normalize Getiri (Başlangıç=100, {currency_label})",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_dark",
        height=580,
    )
    all_dates = benchmark_series.index
    if portfolio_series is not None:
        all_dates = all_dates.union(portfolio_series.index)
    _apply_turkish_month_axis(fig, all_dates)
    return fig


def build_rolling_returns_chart(
    series_df: pd.DataFrame,
    windows: list = None,
) -> go.Figure:
    """
    Her varlık için n-günlük kümülatif getiri (yuvarlanan pencere).
    windows: pencere boyutları gün cinsinden, örn. [30, 90]
    """
    if windows is None:
        windows = [30, 90]

    all_colors = [PORTFOLIO_COLOR] + BENCHMARK_COLORS
    fig = make_subplots(
        rows=len(windows),
        cols=1,
        shared_xaxes=True,
        subplot_titles=[f"{w}-Günlük Kümülatif Getiri (%)" for w in windows],
        vertical_spacing=0.1,
    )

    for row_idx, window in enumerate(windows, start=1):
        for col_idx, col in enumerate(series_df.columns):
            s = series_df[col].dropna()
            rolling_ret = (s / s.shift(window) - 1) * 100
            color = all_colors[col_idx % len(all_colors)]
            customdata = [format_turkish_date(d) for d in rolling_ret.index]

            fig.add_trace(go.Scatter(
                x=rolling_ret.index,
                y=rolling_ret.values,
                name=col,
                line=dict(width=1.5, color=color),
                showlegend=(row_idx == 1),
                legendgroup=col,
                hovertemplate=(
                    f"<b>{col}</b><br>"
                    "Tarih: %{customdata}<br>"
                    f"{window}g Getiri: %{{y:+.1f}}%<extra></extra>"
                ),
                customdata=customdata,
            ), row=row_idx, col=1)

        fig.add_hline(y=0, line=dict(color="#6c7086", width=1, dash="dot"), row=row_idx, col=1)
        fig.update_yaxes(title_text="Getiri (%)", row=row_idx, col=1)

    fig.update_layout(
        title=dict(text="Yuvarlanan Getiri Analizi", font=dict(size=16)),
        hovermode="x unified",
        template="plotly_dark",
        height=380 * len(windows),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    _apply_turkish_month_axis(fig, series_df.index)
    return fig


def build_drawdown_chart(series_df: pd.DataFrame) -> go.Figure:
    """
    Her varlık için tepe noktasından düşüş (drawdown).
    Portföy serisi varsa alan dolgusuyla vurgulanır.
    """
    all_colors = [PORTFOLIO_COLOR] + BENCHMARK_COLORS
    fig = go.Figure()

    for col_idx, col in enumerate(series_df.columns):
        s = series_df[col].dropna()
        drawdown = (s - s.cummax()) / s.cummax() * 100
        color = all_colors[col_idx % len(all_colors)]
        is_portfolio = (col == "Portföy")
        customdata = [format_turkish_date(d) for d in drawdown.index]

        fig.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            name=col,
            line=dict(width=3 if is_portfolio else 1.5, color=color),
            fill="tozeroy" if is_portfolio else None,
            fillcolor="rgba(230,57,70,0.12)" if is_portfolio else None,
            opacity=1.0 if is_portfolio else 0.7,
            hovertemplate=(
                f"<b>{col}</b><br>"
                "Tarih: %{customdata}<br>"
                "Drawdown: %{y:.1f}%<extra></extra>"
            ),
            customdata=customdata,
        ))

    fig.add_hline(y=0, line=dict(color="#6c7086", width=1, dash="dot"))

    fig.update_layout(
        title=dict(text="Maksimum Drawdown — Tepe'den Düşüş (%)", font=dict(size=16)),
        xaxis_title="Tarih",
        yaxis_title="Drawdown (%)",
        hovermode="x unified",
        template="plotly_dark",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    _apply_turkish_month_axis(fig, series_df.index)
    return fig


def build_correlation_heatmap(series_df: pd.DataFrame) -> go.Figure:
    """Günlük getiri korelasyon matrisi — kırmızı(-1) → nötr(0) → yeşil(+1)."""
    corr = series_df.pct_change().dropna().corr()
    labels = list(corr.columns)
    z = corr.values.tolist()

    fig = go.Figure(go.Heatmap(
        z=z,
        x=labels,
        y=labels,
        zmin=-1,
        zmax=1,
        colorscale=[
            [0.0, "#E63946"],
            [0.5, "#313244"],
            [1.0, "#2DC653"],
        ],
        text=[[f"{v:.2f}" for v in row] for row in z],
        texttemplate="%{text}",
        textfont=dict(size=11, color="#cdd6f4"),
        hovertemplate="<b>%{y} × %{x}</b><br>Korelasyon: %{z:.2f}<extra></extra>",
        colorbar=dict(title="Korelasyon", tickfont=dict(color="#cdd6f4")),
    ))

    fig.update_layout(
        title=dict(text="Varlık Getiri Korelasyonu (Günlük)", font=dict(size=16)),
        template="plotly_dark",
        height=max(420, 62 * len(labels) + 100),
        xaxis=dict(tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
    )
    return fig


def build_period_bar_chart(
    series_df: pd.DataFrame,
    freq: str = "ME",
) -> go.Figure:
    """
    Dönemsel getiri karşılaştırması — gruplanmış çubuk grafik.
    freq: "ME" (aylık) veya "QE" (çeyreklik)
    """
    period_returns = series_df.resample(freq).last().pct_change().dropna() * 100
    all_colors = [PORTFOLIO_COLOR] + BENCHMARK_COLORS
    fig = go.Figure()

    for col_idx, col in enumerate(period_returns.columns):
        s = period_returns[col]
        color = all_colors[col_idx % len(all_colors)]

        fig.add_trace(go.Bar(
            x=[format_turkish_period(d, freq) for d in s.index],
            y=s.values.round(2),
            name=col,
            marker_color=color,
            opacity=0.85,
            hovertemplate=(
                f"<b>{col}</b><br>"
                "Dönem: %{x}<br>"
                "Getiri: %{y:+.2f}%<extra></extra>"
            ),
        ))

    freq_label = "Aylık" if freq == "ME" else "Çeyreklik"
    fig.add_hline(y=0, line=dict(color="#6c7086", width=1, dash="dot"))
    fig.update_layout(
        title=dict(text=f"{freq_label} Getiri Karşılaştırması", font=dict(size=16)),
        xaxis_title="Dönem",
        yaxis_title="Getiri (%)",
        barmode="group",
        hovermode="x unified",
        template="plotly_dark",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def format_turkish_lira(value, decimals: int = 1) -> str:
    sign = "+" if value >= 0 else "-"
    formatted = f"{abs(float(value)):,.{decimals}f}"
    return sign + formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def build_treemap(contributions: pd.DataFrame) -> go.Figure:
    """
    Varlık P&L katkı haritası.
    contributions: Varlık Adı, pnl_tl, pnl_pct, weight_pct, contribution_pct sütunları içermeli.
    """
    df = contributions.copy()
    df["pnl_pct"]         = df["pnl_pct"].round(2)
    df["weight_pct"]      = df["weight_pct"].round(2)
    df["contribution_pct"] = df["contribution_pct"].round(2)
    df["pnl_tl_display"] = df["pnl_tl"].apply(format_turkish_lira)
    abs_values = df["pnl_tl"].abs().tolist()

    fig = go.Figure(go.Treemap(
        labels=df["Varlık Adı"].tolist(),
        parents=[""] * len(df),
        values=abs_values,
        customdata=df[["pnl_tl_display", "pnl_pct", "weight_pct", "contribution_pct"]].values,
        texttemplate="<b>%{label}</b><br>%{customdata[1]:+.2f}%",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Kar/Zarar (TL): \u20ba%{customdata[0]}<br>"
            "Kar/Zarar (%): %{customdata[1]:+.2f}%<br>"
            "Ağırlık: %{customdata[2]:.2f}%<br>"
            "Katkı: %{customdata[3]:+.2f}%<extra></extra>"
        ),
        marker=dict(
            colors=df["pnl_pct"].tolist(),
            colorscale=[
                [0.0, "#E63946"],
                [0.5, "#313244"],
                [1.0, "#2DC653"],
            ],
            cmid=0,
            showscale=True,
            colorbar=dict(title="K/Z %", tickfont=dict(color="#cdd6f4")),
        ),
    ))

    fig.update_layout(
        title=dict(text="Varlık Kar/Zarar Katkı Haritası", font=dict(size=16)),
        template="plotly_dark",
        height=450,
    )
    return fig


def build_risk_return_scatter(series_df: pd.DataFrame) -> go.Figure:
    """
    Risk-getiri dağılımı: x=yıllık volatilite, y=toplam getiri.
    Portföy varsa yıldız sembolüyle öne çıkarılır.
    """
    daily_ret = series_df.pct_change().dropna()
    total_returns = ((series_df.iloc[-1] / series_df.iloc[0] - 1) * 100).round(2)
    annual_vol = (daily_ret.std() * (252 ** 0.5) * 100).round(2)
    all_colors = [PORTFOLIO_COLOR] + BENCHMARK_COLORS

    fig = go.Figure()

    for col_idx, col in enumerate(series_df.columns):
        is_portfolio = (col == "Portföy")
        color = PORTFOLIO_COLOR if is_portfolio else BENCHMARK_COLORS[col_idx % len(BENCHMARK_COLORS)]

        fig.add_trace(go.Scatter(
            x=[annual_vol[col]],
            y=[total_returns[col]],
            name=col,
            mode="markers+text",
            marker=dict(
                size=20 if is_portfolio else 13,
                color=color,
                symbol="star" if is_portfolio else "circle",
                line=dict(width=2, color="#cdd6f4") if is_portfolio else dict(width=0),
            ),
            text=[col],
            textposition="top center",
            textfont=dict(size=10, color="#cdd6f4"),
            hovertemplate=(
                f"<b>{col}</b><br>"
                "Yıllık Volatilite: %{x:.2f}%<br>"
                "Toplam Getiri: %{y:+.2f}%<extra></extra>"
            ),
        ))

    fig.add_hline(y=0, line=dict(color="#6c7086", width=1, dash="dot"),
                  annotation_text="Sıfır Getiri", annotation_position="bottom right",
                  annotation_font=dict(size=10, color="#6c7086"))

    fig.update_layout(
        title=dict(text="Risk-Getiri Dağılımı (Yıllık Volatilite vs Toplam Getiri)", font=dict(size=16)),
        xaxis_title="Yıllık Volatilite (%)",
        yaxis_title="Toplam Getiri (%)",
        template="plotly_dark",
        height=500,
        showlegend=False,
    )
    return fig


def build_asset_filter_widget(
    benchmark_df: pd.DataFrame,
    portfolio_series=None,
    currency_label: str = "TL",
) -> "widgets.VBox":
    """
    Combobox (Dropdown) + interaktif performans grafiği.
    'Tümü' seçilince tüm varlıklar gösterilir; tek varlık seçilince sadece o görünür.
    Grafik çizgileri solid (kesikli değil).
    """
    if not HAS_WIDGETS:
        raise ImportError("ipywidgets kurulu değil: pip install ipywidgets")

    options = ["Tümü"] + list(benchmark_df.columns)

    dropdown = widgets.Dropdown(
        options=options,
        value="Tümü",
        description="Varlık:",
        style={"description_width": "60px"},
        layout=widgets.Layout(width="260px"),
    )

    out = widgets.Output()

    def _render(selected):
        out.clear_output(wait=True)
        if selected == "Tümü":
            filtered = benchmark_df
        else:
            filtered = benchmark_df[[selected]]

        title_suffix = "Tümü" if selected == "Tümü" else selected
        fig = build_performance_line_chart_v2(
            portfolio_series=portfolio_series,
            benchmark_series=filtered,
            currency_label=currency_label,
            title=f"Performans Karşılaştırması — {title_suffix}",
        )
        with out:
            display(fig)

    def _on_change(change):
        if change["name"] == "value":
            _render(change["new"])

    dropdown.observe(_on_change, names="value")
    _render("Tümü")

    return widgets.VBox(
        [dropdown, out],
        layout=widgets.Layout(width="100%"),
    )
