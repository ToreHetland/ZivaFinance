import streamlit as st
from pathlib import Path

st.set_page_config(page_title="My Finance – Brand Preview", page_icon="💼", layout="wide")
css_path = Path(__file__).parent / "myfinance.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

st.markdown('<div class="mf-container">', unsafe_allow_html=True)
st.markdown(
    '<div class="mf-card"><div class="mf-hero-wordmark">My Finance</div><div>Clarity. Control. Confidence.</div></div>',
    unsafe_allow_html=True,
)

c1, c2 = st.columns([2, 1])
with c1:
    st.markdown("### Buttons")
    st.markdown(
        """
    <div class="mf-card">
      <button class="mf-btn mf-btn-primary">Add Expense</button>&nbsp;
      <button class="mf-btn">AI Insight</button>&nbsp;
      <button class="mf-btn">Forecast</button>&nbsp;
      <button class="mf-btn">Reports</button>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("### KPI Tiles")
    st.markdown(
        """
    <div class="mf-card">
      <div class="mf-kpi"><span class="value">65,000 NOK</span><span class="label">Budget</span></div>
      <div class="mf-divider"></div>
      <div class="mf-kpi"><span class="value">48,300 NOK</span><span class="label">Spent</span></div>
      <div class="mf-divider"></div>
      <div class="mf-kpi"><span class="value">16,700 NOK</span><span class="label">Remaining</span></div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown("### Colors")
    st.markdown(
        """
    <div class="mf-card">
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <div style="border-radius:12px; background:#007BFF; height:70px;"></div><div>Blue<br/><code>#007BFF</code></div>
        <div style="border-radius:12px; background:#00B894; height:70px;"></div><div>Green<br/><code>#00B894</code></div>
        <div style="border-radius:12px; background:#AAAAAA; height:70px;"></div><div>Navy<br/><code>#AAAAAA</code></div>
        <div style="border-radius:12px; background:#FAFAFA; height:70px; border:1px solid #eee;"></div><div>White<br/><code>#FAFAFA</code></div>
        <div style="border-radius:12px; background:#FFD54F; height:70px;"></div><div>Gold<br/><code>#FFD54F</code></div>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)
