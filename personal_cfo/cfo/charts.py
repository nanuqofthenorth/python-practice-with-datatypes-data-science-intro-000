"""Plotly chart builders.

Colors follow the validated categorical/sequential/status palette from the
dataviz skill (references/palette.md): fixed categorical hue order (never
cycled/reassigned), single-hue sequential ramps for magnitude, and status
colors reserved for good/warning/critical states. No dual-axis charts.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# Fixed categorical order -- assign by position, never by rank or filter state.
CATEGORICAL = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95"]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def _base_layout(**overrides) -> dict:
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=SURFACE,
        font=dict(family=FONT_FAMILY, color=INK_SECONDARY, size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=INK_SECONDARY)),
        xaxis=dict(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BASELINE, tickfont=dict(color=INK_MUTED)),
        yaxis=dict(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BASELINE, tickfont=dict(color=INK_MUTED)),
        hoverlabel=dict(bgcolor=SURFACE, font=dict(family=FONT_FAMILY, color=INK_PRIMARY)),
    )
    layout.update(overrides)
    return layout


def _currency_axis() -> dict:
    return dict(tickprefix="$", tickformat=",.0f")


def net_worth_trend_chart(snapshots: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if snapshots.empty:
        fig.update_layout(**_base_layout(annotations=[_empty_state_annotation("Take a net worth snapshot to see your trend here.")]))
        return fig

    fig.add_trace(go.Scatter(
        x=snapshots["snapshot_date"], y=snapshots["net_worth"],
        mode="lines+markers", name="Net worth",
        line=dict(color=CATEGORICAL[0], width=2),
        marker=dict(size=7, color=CATEGORICAL[0]),
        fill="tozeroy", fillcolor="rgba(42,120,214,0.08)",
        hovertemplate="%{x}<br>Net worth: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(showlegend=False, hovermode="x unified"))
    fig.update_yaxes(**_currency_axis())
    return fig


def income_vs_expenses_chart(cash_flow: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if cash_flow.empty:
        fig.update_layout(**_base_layout(annotations=[_empty_state_annotation("Add transactions to see income vs. expenses.")]))
        return fig

    fig.add_trace(go.Scatter(
        x=cash_flow["month"], y=cash_flow["income"], mode="lines+markers", name="Income",
        line=dict(color=CATEGORICAL[0], width=2), marker=dict(size=6),
        hovertemplate="%{x}<br>Income: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=cash_flow["month"], y=cash_flow["expenses"], mode="lines+markers", name="Expenses",
        line=dict(color=CATEGORICAL[1], width=2), marker=dict(size=6),
        hovertemplate="%{x}<br>Expenses: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(hovermode="x unified"))
    fig.update_yaxes(**_currency_axis())
    return fig


def spending_by_category_chart(spending: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if spending.empty:
        fig.update_layout(**_base_layout(annotations=[_empty_state_annotation("No expenses recorded for this period.")]))
        return fig

    ordered = spending.sort_values("amount")
    fig.add_trace(go.Bar(
        x=ordered["amount"], y=ordered["category"], orientation="h",
        marker=dict(color=CATEGORICAL[0]),
        hovertemplate="%{y}: $%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(showlegend=False, height=max(280, 32 * len(ordered))))
    fig.update_xaxes(**_currency_axis())
    return fig


def budget_vs_actual_chart(budget_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    df = budget_df[(budget_df["budgeted"] > 0) | (budget_df["actual"] > 0)].sort_values("budgeted")
    if df.empty:
        fig.update_layout(**_base_layout(annotations=[_empty_state_annotation("Set budgets and add transactions to compare.")]))
        return fig

    fig.add_trace(go.Bar(
        x=df["budgeted"], y=df["category"], orientation="h", name="Budgeted",
        marker=dict(color=CATEGORICAL[0]),
        hovertemplate="%{y} budgeted: $%{x:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["actual"], y=df["category"], orientation="h", name="Actual",
        marker=dict(color=CATEGORICAL[1]),
        hovertemplate="%{y} actual: $%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(barmode="group", height=max(280, 46 * len(df))))
    fig.update_xaxes(**_currency_axis())
    return fig


def debt_payoff_chart(schedule: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if schedule.empty:
        fig.update_layout(**_base_layout(annotations=[_empty_state_annotation("Add debts to see a payoff timeline.")]))
        return fig

    debt_names = list(schedule["debt"].unique())[:8]
    for i, name in enumerate(debt_names):
        d = schedule[schedule["debt"] == name]
        fig.add_trace(go.Scatter(
            x=d["month"], y=d["balance"], mode="lines", name=name,
            line=dict(color=CATEGORICAL[i % len(CATEGORICAL)], width=2),
            hovertemplate=f"{name}<br>Month %{{x}}: $%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(**_base_layout(hovermode="x unified", xaxis=dict(title="Months from now")))
    fig.update_yaxes(**_currency_axis())
    return fig


def _empty_state_annotation(text: str) -> dict:
    return dict(
        text=text, xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(color=INK_MUTED, size=13),
    )
