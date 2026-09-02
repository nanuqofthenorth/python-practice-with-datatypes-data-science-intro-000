"""Plotly chart builders.

Colors follow the validated categorical/sequential/status palette from the
dataviz skill (references/palette.md): fixed categorical hue order (never
cycled/reassigned), single-hue sequential ramps for magnitude, and status
colors reserved for good/warning/critical states. No dual-axis charts.

Every builder takes a `dark: bool` flag (from cfo.ui.is_dark_theme(), which
reads st.context.theme.type) and switches to the palette's dark steps.
Plotly figures are static JSON sent to the browser, so -- unlike native
Streamlit widgets -- they don't follow the page's CSS theme on their own;
without this, every chart would stay light-mode-colored even after the
rest of the app switches to dark.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go


@dataclass(frozen=True)
class _Palette:
    categorical: list[str]
    surface: str
    ink_primary: str
    ink_secondary: str
    ink_muted: str
    gridline: str
    baseline: str


# Fixed categorical order -- assign by position, never by rank or filter
# state. The dark column is the same eight hues stepped for the dark
# surface, not a separate palette (dataviz skill, references/palette.md).
_LIGHT = _Palette(
    categorical=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
    surface="#fcfcfb", ink_primary="#0b0b0b", ink_secondary="#52514e",
    ink_muted="#898781", gridline="#e1e0d9", baseline="#c3c2b7",
)
_DARK = _Palette(
    categorical=["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
    surface="#1a1a19", ink_primary="#ffffff", ink_secondary="#c3c2b7",
    ink_muted="#898781", gridline="#2c2c2a", baseline="#383835",
)

# Status colors are fixed -- never themed -- and identical in both modes
# (dataviz skill palette.md: "Status palette (fixed - never themed)").
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def _palette(dark: bool) -> _Palette:
    return _DARK if dark else _LIGHT


def _base_layout(dark: bool, **overrides) -> dict:
    p = _palette(dark)
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=p.surface,
        font=dict(family=FONT_FAMILY, color=p.ink_secondary, size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=p.ink_secondary)),
        xaxis=dict(gridcolor=p.gridline, zerolinecolor=p.baseline, linecolor=p.baseline, tickfont=dict(color=p.ink_muted)),
        yaxis=dict(gridcolor=p.gridline, zerolinecolor=p.baseline, linecolor=p.baseline, tickfont=dict(color=p.ink_muted)),
        hoverlabel=dict(bgcolor=p.surface, font=dict(family=FONT_FAMILY, color=p.ink_primary)),
    )
    layout.update(overrides)
    return layout


def _currency_axis() -> dict:
    return dict(tickprefix="$", tickformat=",.0f")


def _tint(hex_color: str, alpha: float = 0.16) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _empty_figure(text: str, dark: bool, height: int = 280) -> go.Figure:
    """A clean blank state: no traces means Plotly would otherwise draw its
    own default cartesian axes (arbitrary tick range, visible gridlines) --
    explicitly hide them instead of leaving that to chance."""
    p = _palette(dark)
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False, range=[0, 1]),
        annotations=[dict(
            text=text, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(color=p.ink_muted, size=13, family=FONT_FAMILY),
        )],
    )
    return fig


def health_gauge_chart(score: float | None, dark: bool = False) -> go.Figure:
    if score is None:
        return _empty_figure("Add accounts, transactions, and goals to calculate your score.", dark, height=240)

    p = _palette(dark)
    if score < 40:
        zone_color = STATUS["critical"]
    elif score < 70:
        zone_color = STATUS["warning"]
    else:
        zone_color = STATUS["good"]

    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0.08, 0.92], "y": [0, 1]},
        number={"suffix": "%", "font": {"size": 36, "color": p.ink_primary}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": p.ink_muted, "tickfont": {"color": p.ink_muted, "size": 11}},
            "bar": {"color": zone_color, "thickness": 0.32},
            "bgcolor": p.surface,
            "borderwidth": 0,
            "steps": [
                {"range": [0, 40], "color": _tint(STATUS["critical"])},
                {"range": [40, 70], "color": _tint(STATUS["warning"])},
                {"range": [70, 100], "color": _tint(STATUS["good"])},
            ],
        },
    ))
    fig.update_layout(**_base_layout(dark, height=240, margin=dict(l=45, r=45, t=30, b=10)))
    return fig


def net_worth_trend_chart(snapshots: pd.DataFrame, dark: bool = False) -> go.Figure:
    if snapshots.empty:
        return _empty_figure("Take a net worth snapshot to see your trend here.", dark)

    p = _palette(dark)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=snapshots["snapshot_date"], y=snapshots["net_worth"],
        mode="lines+markers", name="Net worth",
        line=dict(color=p.categorical[0], width=2),
        marker=dict(size=7, color=p.categorical[0]),
        fill="tozeroy", fillcolor=_tint(p.categorical[0], 0.08),
        hovertemplate="%{x}<br>Net worth: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(dark, showlegend=False, hovermode="x unified"))
    fig.update_yaxes(**_currency_axis())
    return fig


def income_vs_expenses_chart(cash_flow: pd.DataFrame, dark: bool = False) -> go.Figure:
    if cash_flow.empty:
        return _empty_figure("Add transactions to see income vs. expenses.", dark)

    p = _palette(dark)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cash_flow["month"], y=cash_flow["income"], mode="lines+markers", name="Income",
        line=dict(color=p.categorical[0], width=2), marker=dict(size=6),
        hovertemplate="%{x}<br>Income: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=cash_flow["month"], y=cash_flow["expenses"], mode="lines+markers", name="Expenses",
        line=dict(color=p.categorical[1], width=2), marker=dict(size=6),
        hovertemplate="%{x}<br>Expenses: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(dark, hovermode="x unified"))
    fig.update_yaxes(**_currency_axis())
    return fig


def spending_by_category_chart(spending: pd.DataFrame, dark: bool = False) -> go.Figure:
    if spending.empty:
        return _empty_figure("No expenses recorded for this period.", dark)

    p = _palette(dark)
    ordered = spending.sort_values("amount")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ordered["amount"], y=ordered["category"], orientation="h",
        marker=dict(color=p.categorical[0]),
        hovertemplate="%{y}: $%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(dark, showlegend=False, height=max(280, 32 * len(ordered))))
    fig.update_xaxes(**_currency_axis())
    return fig


def budget_vs_actual_chart(budget_df: pd.DataFrame, dark: bool = False) -> go.Figure:
    df = budget_df[(budget_df["budgeted"] > 0) | (budget_df["actual"] > 0)].sort_values("budgeted")
    if df.empty:
        return _empty_figure("Set budgets and add transactions to compare.", dark)

    p = _palette(dark)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["budgeted"], y=df["category"], orientation="h", name="Budgeted",
        marker=dict(color=p.categorical[0]),
        hovertemplate="%{y} budgeted: $%{x:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["actual"], y=df["category"], orientation="h", name="Actual",
        marker=dict(color=p.categorical[1]),
        hovertemplate="%{y} actual: $%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(dark, barmode="group", height=max(280, 46 * len(df))))
    fig.update_xaxes(**_currency_axis())
    return fig


def debt_payoff_chart(schedule: pd.DataFrame, dark: bool = False) -> go.Figure:
    if schedule.empty:
        return _empty_figure("Add debts to see a payoff timeline.", dark)

    p = _palette(dark)
    fig = go.Figure()
    debt_names = list(schedule["debt"].unique())[:8]
    for i, name in enumerate(debt_names):
        d = schedule[schedule["debt"] == name]
        fig.add_trace(go.Scatter(
            x=d["month"], y=d["balance"], mode="lines", name=name,
            line=dict(color=p.categorical[i % len(p.categorical)], width=2),
            hovertemplate=f"{name}<br>Month %{{x}}: $%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(**_base_layout(dark, hovermode="x unified"))
    fig.update_xaxes(title_text="Months from now")
    fig.update_yaxes(**_currency_axis())
    return fig
