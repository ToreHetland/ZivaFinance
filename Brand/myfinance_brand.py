"""
My Finance Brand Tokens and Helpers (Professional Minimalism)
"""

BRAND = "My Finance"
TAGLINE = "Clarity. Control. Confidence."

palette = {
    "blue": "#007BFF",
    "green": "#00B894",
    "navy": "#AAAAAA",
    "white": "#FAFAFA",
    "gold": "#FFD54F",
}

css = r""":root {
  --mf-blue: #007BFF;
  --mf-green: #00B894;
  --mf-navy: #AAAAAA;
  --mf-white: #FAFAFA;
  --mf-gold: #FFD54F;
  --mf-gradient: linear-gradient(90deg, #007BFF 0%, #00B894 100%);
  --mf-font-head: "Poppins", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mf-font-body: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

html, body { background: var(--mf-white); color: var(--mf-navy); font-family: var(--mf-font-body); }
.mf-container { max-width: 1100px; margin: 0 auto; padding: 24px; }
.mf-hero-wordmark { font-family: var(--mf-font-head); font-weight: 800; font-size: 56px; line-height:1.1; background:linear-gradient(90deg, #007BFF 0%, #00B894 100%); -webkit-background-clip:text; background-clip:text; color:transparent; }

.mf-btn { display:inline-flex; align-items:center; justify-content:center; padding:10px 16px; border:1px solid rgba(0,0,0,0.1); border-radius:12px; background:#fff; color:var(--mf-navy); font-weight:600; cursor:pointer; transition: border-color .15s, box-shadow .15s, transform .02s; }
.mf-btn:hover { border-color: rgba(0,0,0,0.18); box-shadow:0 6px 16px rgba(0,0,0,0.06); }
.mf-btn:active { transform: translateY(1px); }
.mf-btn-primary { background: var(--mf-gradient); color:#fff; border:none; }
.mf-card { background:#fff; border:1px solid rgba(0,0,0,0.06); border-radius:16px; padding:18px; }
.mf-kpi { display:flex; align-items:baseline; gap:8px; font-family: var(--mf-font-head); }
.mf-kpi .value { font-size:28px; font-weight:700; }
.mf-kpi .label { font-size:13px; opacity:.75; font-weight:500; }
.mf-pill { display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; background: rgba(0,0,0,0.04); font-weight:600; color: var(--mf-navy); }
.mf-divider { height:1px; background: rgba(0,0,0,0.06); margin:18px 0; }"""
streamlit_theme = r"""[theme]
primaryColor = "#007BFF"
backgroundColor = "#FAFAFA"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#AAAAAA"
font = "sans serif"""
dalle_prompts = r"""# My Finance – DALL·E Prompts (Professional Minimalism)

## 1) Logo (main identity)
Create a minimalist logo for a personal-finance and AI-insights app called "My Finance".
Symbolize clarity, control, and trust — e.g., an upward arc, bar-chart, or abstract coin.
Use a subtle gradient blue (#007BFF) to green (#00B894) on a white background.
Typography: Poppins SemiBold. Style: modern fintech, flat and professional.

## 2) App Icon
Create a circular app icon for "My Finance" showing a stylized rising line or bar graph in blue-green gradient.
White background, no text, minimal glow.

## 3) Dashboard Interface
Design a modern dashboard for "My Finance" with widgets for Budget Overview, AI Forecast, Spending by Category, and Goals.
Use white background, blue-green accents, rounded cards, subtle shadows.
Typography Poppins/Inter. Clean, professional fintech style.

## 4) Buttons & Icons
Design a cohesive set of buttons and line icons for "My Finance".
Buttons: rounded corners, minimal shadows, blue-green gradient for primary actions, white with navy text for secondary actions.
Icons: flat, white on gradient or navy on white."""


def as_streamlit_config():
    return streamlit_theme


def prompts():
    return dalle_prompts


def write_files(out_dir: str = "./myfinance_brand"):
    import os, json, pathlib

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "myfinance.css").write_text(css, encoding="utf-8")
    (out / "streamlit_theme.toml").write_text(streamlit_theme, encoding="utf-8")
    (out / "colors.json").write_text(json.dumps(palette, indent=2), encoding="utf-8")
    (out / "dalle_prompts.txt").write_text(dalle_prompts, encoding="utf-8")
    return str(out.resolve())
