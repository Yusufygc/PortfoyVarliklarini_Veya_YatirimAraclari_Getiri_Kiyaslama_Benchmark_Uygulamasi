import pandas as pd
import plotly.graph_objects as go

try:
    import ipywidgets as widgets
    HAS_WIDGETS = True
except ImportError:
    HAS_WIDGETS = False

BENCHMARK_COLORS = [
    "#F4A460", "#A9A9A9", "#4682B4", "#20B2AA", "#9370DB", "#CD853F"
]
PORTFOLIO_COLOR = "#E63946"
GAIN_COLOR = "#2DC653"
LOSS_COLOR = "#E63946"


def build_performance_line_chart(
    portfolio_series,
    benchmark_series: pd.DataFrame,
    currency_label: str,
    title: str = "Portföy vs Benchmark",
) -> go.Figure:
    """
    Portfolio: linewidth=3, opacity=1.
    Benchmark'lar: width=1, opacity=0.55, dashed.
    Hover: tarih, değer, başlangıçtan % değişim.
    .show() çağrılmaz — Figure döndürür.
    """
    fig = go.Figure()

    # Benchmark'lar önce (arka planda)
    for i, col in enumerate(benchmark_series.columns):
        s = benchmark_series[col].dropna()
        color = BENCHMARK_COLORS[i % len(BENCHMARK_COLORS)]
        fig.add_trace(go.Scatter(
            x=s.index,
            y=s.values,
            name=col,
            line=dict(width=1, dash="dash", color=color),
            opacity=0.6,
            hovertemplate=(
                f"<b>{col}</b><br>"
                "Tarih: %{x|%d.%m.%Y}<br>"
                f"Değer: %{{y:.1f}} ({currency_label})<br>"
                "Başlangıçtan: %{customdata:.1f}%<extra></extra>"
            ),
            customdata=(s.values - 100),
        ))

    # Portföy üste (opsiyonel)
    if portfolio_series is not None:
        p = portfolio_series.dropna()
        fig.add_trace(go.Scatter(
            x=p.index,
            y=p.values,
            name="Portföy",
            line=dict(width=3, color=PORTFOLIO_COLOR),
            opacity=1.0,
            hovertemplate=(
                "<b>Portföy</b><br>"
                "Tarih: %{x|%d.%m.%Y}<br>"
                f"Değer: %{{y:.1f}} ({currency_label})<br>"
                "Başlangıçtan: %{customdata:.1f}%<extra></extra>"
            ),
            customdata=(p.values - 100),
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        xaxis_title="Tarih",
        yaxis_title=f"Normalize Getiri (Başlangıç=100, {currency_label})",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_dark",
        height=500,
    )
    return fig


def build_donut_chart(
    asset_names: list,
    current_weights: list,
    current_values_tl: list,
) -> go.Figure:
    """hole=0.55. Hover: TL değer + ağırlık %."""
    if abs(sum(current_weights) - 1.0) > 1e-6:
        total = sum(current_weights)
        current_weights = [w / total for w in current_weights]

    fig = go.Figure(go.Pie(
        labels=asset_names,
        values=current_weights,
        hole=0.55,
        customdata=current_values_tl,
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Ağırlık: %{percent}<br>"
            "Değer: ₺%{customdata:,.0f}<extra></extra>"
        ),
        textinfo="label+percent",
    ))
    fig.update_layout(
        title="Portföy Dağılımı",
        template="plotly_dark",
        height=400,
        showlegend=False,
    )
    return fig


def build_kpi_cards(contributions: pd.DataFrame, n: int = 3):
    """
    ipywidgets HBox: en çok kazanan n + en çok kaybeden n varlık.
    Inline CSS kullanır (Colab'da harici stylesheet çalışmaz).
    """
    if not HAS_WIDGETS:
        raise ImportError("ipywidgets kurulu değil: pip install ipywidgets")

    sorted_df = contributions.sort_values("pnl_pct", ascending=False)
    gainers = sorted_df.head(n)
    losers = sorted_df.tail(n).iloc[::-1]

    def make_card(row, color):
        return widgets.HTML(value=f"""
        <div style="
            background:#1e1e2e;border:1px solid {color};border-radius:8px;
            padding:12px 16px;margin:4px;min-width:140px;text-align:center;
        ">
            <div style="color:#cdd6f4;font-size:12px;font-weight:bold;">{row['Varlık Adı']}</div>
            <div style="color:{color};font-size:20px;font-weight:bold;margin-top:4px;">
                {'▲' if row['pnl_pct'] >= 0 else '▼'} {abs(row['pnl_pct']):.1f}%
            </div>
            <div style="color:#a6adc8;font-size:11px;margin-top:2px;">
                ₺{row['pnl_tl']:+,.0f}
            </div>
        </div>
        """)

    cards = []
    for _, row in gainers.iterrows():
        cards.append(make_card(row, GAIN_COLOR))
    for _, row in losers.iterrows():
        cards.append(make_card(row, LOSS_COLOR))

    return widgets.HBox(cards, layout=widgets.Layout(flex_wrap="wrap"))


def build_summary_table(contributions: pd.DataFrame) -> go.Figure:
    """go.Table: varlık, P&L (TL), P&L (%), ağırlık, katkı. Alternatif satır rengi."""
    df = contributions.copy()

    def fmt_pct(v):
        return f"{v:+.2f}%"

    def fmt_tl(v):
        return f"₺{v:+,.0f}"

    fig = go.Figure(go.Table(
        header=dict(
            values=["<b>Varlık</b>", "<b>P&L (TL)</b>", "<b>P&L %</b>", "<b>Ağırlık %</b>", "<b>Katkı %</b>"],
            fill_color="#313244",
            font=dict(color="#cdd6f4", size=12),
            align="center",
            line_color="#45475a",
        ),
        cells=dict(
            values=[
                df["Varlık Adı"],
                [fmt_tl(v) for v in df["pnl_tl"]],
                [fmt_pct(v) for v in df["pnl_pct"]],
                [f"{v:.1f}%" for v in df["weight_pct"]],
                [fmt_pct(v) for v in df["contribution_pct"]],
            ],
            fill_color=[
                ["#1e1e2e" if i % 2 == 0 else "#181825" for i in range(len(df))]
            ],
            font=dict(color="#cdd6f4", size=11),
            align=["left", "right", "right", "right", "right"],
            line_color="#45475a",
        ),
    ))
    fig.update_layout(
        title="Varlık Bazlı Performans",
        template="plotly_dark",
        height=max(250, 40 * len(df) + 80),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig
