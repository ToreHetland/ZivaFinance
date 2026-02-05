# components/insights_forecast.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from core.db_operations import load_data_db
from config.config import format_currency
from config.i18n import t

lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

# ============================================================
# Public entry
# ============================================================


def render_forecast_and_radar():
    """
    Forecast next months for Income / Expense / Net and show a Financial Health Radar.
    Works from the `transactions` table only.
    """
    st.header("🔮 Forecast & 🎯 Financial Health Radar")

    tx = load_data_db("transactions")
    if tx.empty:
        st.info("No transactions found. Add transactions to see forecasts and radar.")
        return

    # ---------- Prep ----------
    df = tx.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["type"] = df["type"].where(df["type"].isin(["Income", "Expense"]), "Expense")
    df["month"] = df["date"].dt.to_period("M").astype(str)

    # Min months to forecast reliably
    months_order = sorted(df["month"].unique().tolist())
    if len(months_order) < 3:
        st.warning("Need at least 3 months of data for a basic forecast.")
        return

    # ---------- Controls ----------
    colA, colB, colC = st.columns([1, 1, 1])
    with colA:
        horizon = st.selectbox("Forecast Horizon (months)", [3, 4, 5, 6, 9, 12], index=1)
    with colB:
        inc_growth = st.slider(
            "Income Trend Adjust (%)", -30, 30, 0, help="Apply a growth tweak to forecast income."
        )
    with colC:
        exp_growth = st.slider(
            "Expense Trend Adjust (%)", -30, 30, 0, help="Apply a growth tweak to forecast expense."
        )

    # ---------- Monthly actuals ----------
    monthly = df.groupby(["month", "type"])["amount"].sum().unstack(fill_value=0.0).reset_index()
    for col in ["Income", "Expense"]:
        if col not in monthly.columns:
            monthly[col] = 0.0
    monthly["Net"] = monthly["Income"] - monthly["Expense"]
    monthly = monthly.sort_values("month")

    # ---------- Simple linear forecast ----------
    # We avoid extra dependencies; use polyfit on time index
    def _lin_forecast(series: pd.Series, months: list[str], steps: int, pct_adjust: float = 0.0):
        # x = 0..n-1; y = series values
        y = series.values.astype(float)
        x = np.arange(len(y))
        # If constant or too short, fall back to simple mean
        if len(y) < 2 or np.allclose(y, y.mean()):
            base = float(np.maximum(0.0, y.mean()))
            fc = np.full(steps, base)
        else:
            m, b = np.polyfit(x, y, 1)  # slope, intercept
            x_future = np.arange(len(y), len(y) + steps)
            fc = m * x_future + b
            fc = np.where(fc < 0, 0.0, fc)

        if pct_adjust != 0:
            fc = fc * (1.0 + pct_adjust / 100.0)
        # Build labels
        last = pd.Period(months[-1]).asfreq("M")
        labels = [(last + i + 1).strftime("%Y-%m") for i in range(steps)]
        return labels, fc

    inc_labels, inc_fc = _lin_forecast(
        monthly["Income"], monthly["month"].tolist(), horizon, inc_growth
    )
    exp_labels, exp_fc = _lin_forecast(
        monthly["Expense"], monthly["month"].tolist(), horizon, exp_growth
    )
    net_fc = inc_fc - exp_fc
    fc_df = pd.DataFrame({"month": inc_labels, "Income": inc_fc, "Expense": exp_fc, "Net": net_fc})

    # ---------- Charts: History + Forecast ----------
    st.subheader("📈 Monthly Income / Expense — History vs Forecast")
    fig1 = go.Figure()
    # history
    fig1.add_trace(go.Bar(name="Actual Income", x=monthly["month"], y=monthly["Income"]))
    fig1.add_trace(go.Bar(name="Actual Expense", x=monthly["month"], y=monthly["Expense"]))
    # forecast
    fig1.add_trace(
        go.Scatter(
            name="Forecast Income",
            x=fc_df["month"],
            y=fc_df["Income"],
            mode="lines+markers",
            line=dict(dash="dot"),
        )
    )
    fig1.add_trace(
        go.Scatter(
            name="Forecast Expense",
            x=fc_df["month"],
            y=fc_df["Expense"],
            mode="lines+markers",
            line=dict(dash="dot"),
        )
    )
    fig1.update_layout(
        barmode="group",
        title="Income & Expense — Actual vs Forecast",
        xaxis_title="Month",
        yaxis_title="Amount",
    )
    st.plotly_chart(
        fig,
        config={"responsive": True, "displaylogo": False, "scrollZoom": False, "editable": False},
    )

    st.subheader("⚖️ Net Balance — History vs Forecast")
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(name="Actual Net", x=monthly["month"], y=monthly["Net"], mode="lines+markers")
    )
    fig2.add_trace(
        go.Scatter(
            name="Forecast Net",
            x=fc_df["month"],
            y=fc_df["Net"],
            mode="lines+markers",
            line=dict(dash="dot"),
        )
    )
    fig2.update_layout(
        title="Net — Actual vs Forecast",
        xaxis_title="Month",
        yaxis_title="Amount",
        hovermode="x unified",
    )
    st.plotly_chart(
        fig,
        config={"responsive": True, "displaylogo": False, "scrollZoom": False, "editable": False},
    )

    # ---------- Export ----------
    with st.expander("⬇️ Export Forecast"):
        st.dataframe(fc_df, hide_index=True)
        st.download_button(
            "Download CSV",
            data=fc_df.to_csv(index=False).encode("utf-8"),
            file_name=f"forecast_{inc_labels[0]}_to_{inc_labels[-1]}.csv",
            mime="text/csv",
        )

    st.markdown("---")
    st.subheader("🎯 Financial Health Radar")

    # ---------- Radar Metrics ----------
    # Window = last 6–12 months (prefer 12 if available)
    window = min(12, len(monthly))
    win_df = monthly.tail(window).reset_index(drop=True)

    # 1) Savings Rate (% of income retained as net) — average
    total_income = win_df["Income"].sum()
    total_net = win_df["Net"].sum()
    savings_rate = (total_net / total_income * 100) if total_income > 0 else 0

    # 2) Budget Adherence proxy (if no budget table here): lower Expense/Income ratio is "better"
    # Scale: 100 when expenses are <= 60% of income; 0 when >= 100%
    exp_ratio = (win_df["Expense"].sum() / total_income) if total_income > 0 else 1.0
    adherence = _scale_inverse(exp_ratio, good_threshold=0.6, bad_threshold=1.0)

    # 3) Income Stability (lower std dev => better). Normalize across window using coefficient of variation.
    inc_mean = win_df["Income"].mean() if len(win_df) > 0 else 0.0
    inc_std = win_df["Income"].std(ddof=0) if len(win_df) > 0 else 0.0
    inc_cv = (inc_std / inc_mean) if inc_mean > 0 else 1.0
    income_stability = _scale_inverse(inc_cv, good_threshold=0.10, bad_threshold=0.40)

    # 4) Expense Volatility (lower std dev => better). CV again.
    exp_mean = win_df["Expense"].mean() if len(win_df) > 0 else 0.0
    exp_std = win_df["Expense"].std(ddof=0) if len(win_df) > 0 else 0.0
    exp_cv = (exp_std / exp_mean) if exp_mean > 0 else 1.0
    expense_volatility = _scale_inverse(exp_cv, good_threshold=0.10, bad_threshold=0.40)

    # 5) Liquidity Proxy — average monthly Net vs average Expense (higher net vs expense is better)
    avg_net = win_df["Net"].mean()
    avg_exp = exp_mean
    liquidity = _scale_direct(
        avg_net / avg_exp if avg_exp > 0 else 0.0, good_threshold=0.25, great_threshold=0.60
    )

    metrics = {
        "Savings Rate": _clip01(savings_rate / 100.0) * 100.0,  # already percentage; scale to 0–100
        "Budget Adherence": adherence * 100.0,
        "Income Stability": income_stability * 100.0,
        "Expense Stability": expense_volatility * 100.0,
        "Liquidity": liquidity * 100.0,
    }

    # ---------- Radar ----------
    figR = go.Figure()
    cats = list(metrics.keys())
    vals = list(metrics.values())
    # close the radar
    cats_closed = cats + [cats[0]]
    vals_closed = vals + [vals[0]]

    figR.add_trace(go.Scatterpolar(r=vals_closed, theta=cats_closed, fill="toself", name="Score"))
    figR.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        title="Financial Health Radar (0–100)",
    )
    st.plotly_chart(
        fig,
        config={"responsive": True, "displaylogo": False, "scrollZoom": False, "editable": False},
    )

    # ---------- Metric Cards ----------
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, (label, value) in zip([c1, c2, c3, c4, c5], metrics.items()):
        _metric_card(col, label, f"{value:.0f}/100")

    with st.expander("ℹ️ How scores are computed"):
        st.markdown(
            """
            - **Savings Rate:** Average net / income over the last months.  
            - **Budget Adherence (proxy):** Lower expense/income ratio = higher score.  
            - **Income Stability:** Lower month-to-month variation in income = higher score.  
            - **Expense Stability:** Lower month-to-month variation in expenses = higher score.  
            - **Liquidity:** Average net relative to average expenses.  
            """
        )


# ============================================================
# Helpers (scaling & UI)
# ============================================================


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _scale_inverse(x: float, good_threshold: float, bad_threshold: float) -> float:
    """
    Map x to [0,1] where lower is better.
    <= good_threshold -> 1.0
    >= bad_threshold  -> 0.0
    Linear in between.
    """
    if x <= good_threshold:
        return 1.0
    if x >= bad_threshold:
        return 0.0
    # interpolate
    t = (x - good_threshold) / (bad_threshold - good_threshold)
    return _clip01(1.0 - t)


def _scale_direct(x: float, good_threshold: float, great_threshold: float) -> float:
    """
    Map x to [0,1] where higher is better.
    <= 0 -> 0
    >= great_threshold -> 1
    Between good and great, ramp up; below good, partial credit.
    """
    if x <= 0:
        return 0.0
    if x >= great_threshold:
        return 1.0
    if x >= good_threshold:
        # between good and great
        t = (x - good_threshold) / (great_threshold - good_threshold)
        return _clip01(0.6 + 0.4 * t)  # 0.6 at good, up to 1.0 at great
    # below good
    return _clip01(x / good_threshold * 0.6)  # scale up to 0.6 at good


def _metric_card(container, label: str, value: str):
    with container:
        st.markdown(
            f"""
            <div style='background:#ffffff;border:1px solid #e8e8e8;border-radius:12px;padding:0.9rem;text-align:center;
                       box-shadow:0 2px 6px rgba(0,0,0,0.06);'>
                <div style='font-size:0.9rem;color:#666'>{label}</div>
                <div style='font-size:1.4rem;font-weight:700;color:#333'>{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
