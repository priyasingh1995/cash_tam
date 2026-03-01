"""
Shared color scheme for all dashboards (Organic, TAM).
Use DASHBOARD_CSS in each app and CHART_COLOR_SCALE / PIE_SEQUENCES for Plotly.
"""

import re

def _credit_score_sort_key(label):
    """Order: 1) No score  2) <500  3) 500-600  4) 600-700  5) 700-800  6) 800+"""
    s = str(label).strip()
    if not s:
        return 9999
    lower = s.lower()
    if lower in ("no score", "na", "n/a", "nan"):
        return -2   # 1. No score first
    if "<500" in lower or (s.startswith("<") and "500" in s):
        return -1   # 2. <500 before 500-600
    m = re.match(r"(\d+)", s)
    return int(m.group(1)) if m else 9999  # 3–6: 500, 600, 700, 800 for 500-600, 600-700, 700-800, 800+

def sort_credit_scores_ascending(labels):
    """Return list of credit score labels sorted: No score first, then <500, then 500-600, 600-700, 700-800, 800+, etc."""
    return sorted(set(str(x) for x in labels if x is not None and str(x).strip()), key=_credit_score_sort_key)

def sort_df_by_credit_score_ascending(df, dimension_cols):
    """Sort dataframe so Credit score column (if present) is ascending by score. Other dims unchanged."""
    if df.empty or "Credit score" not in df.columns:
        return df
    out = df.copy()
    out["_score_order"] = out["Credit score"].map(_credit_score_sort_key)
    by = ["_score_order"] + [c for c in dimension_cols if c in out.columns and c != "Credit score"]
    return out.sort_values(by).drop(columns=["_score_order"], errors="ignore")

# Primary blue (totals, accents, borders)
BLUE_PRIMARY = "#2563eb"
BLUE_PRIMARY_DARK = "#1d4ed8"
BLUE_BG_LIGHT = "#eff6ff"
BLUE_BG_MID = "#dbeafe"
BLUE_BORDER = "#93c5fd"
BLUE_TEXT = "#0d47a1"
BLUE_LINK = "#1565c0"

# Slate/neutral (product tiles, labels, tables)
SLATE_BG = "#fafafa"
SLATE_BG_MID = "#f1f5f9"
SLATE_BORDER = "#e2e8f0"
SLATE_ACCENT = "#94a3b8"
SLATE_LABEL = "#64748b"
SLATE_VALUE = "#475569"
SLATE_DARK = "#1e293b"

# Comparison UI (banner + segment pills) — same blue/slate family
COMPARE_BG_START = BLUE_BG_LIGHT
COMPARE_BG_END = BLUE_BG_MID
COMPARE_BORDER = BLUE_PRIMARY
COMPARE_SEGMENT_BG = "#e8eaf6"
COMPARE_SEGMENT_TEXT = "#283593"
COMPARE_VS_TEXT = SLATE_DARK

# Tables
TABLE_HEADER_BG = "#f0f0f0"
TABLE_ROW_BG = "#fafafa"
TABLE_TOTAL_BG = "#e2e8f0"
TABLE_BORDER = "#ccc"

# Tabs (use blue to match palette)
TAB_BG = "#e0e7ff"
TAB_BG_END = "#c7d2fe"
TAB_SELECTED = "#6366f1"
TAB_SELECTED_END = "#4f46e5"

# Sidebar
SIDEBAR_BG = "#f8fafc"
SIDEBAR_BORDER = "#e2e8f0"
SIDEBAR_HEADER_BG = "linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%)"
SIDEBAR_SECTION_BG = "#ffffff"
SIDEBAR_SECTION_BORDER = "#e2e8f0"

# Buttons
BTN_PRIMARY_BG = "linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%)"
BTN_PRIMARY_HOVER = "linear-gradient(180deg, #3b82f6 0%, #2563eb 100%)"
BTN_PRIMARY_TEXT = "#ffffff"
BTN_BORDER_RADIUS = "8px"
BTN_BOX_SHADOW = "0 2px 4px rgba(37, 99, 235, 0.25)"
BTN_HOVER_SHADOW = "0 4px 12px rgba(37, 99, 235, 0.35)"

# Plotly
CHART_COLOR_SCALE = "Blues"
PIE_VEHICLE_CLASS = "Set3"
PIE_CREDIT_SCORE = "Pastel2"
PIE_TICKET_SIZE = "Set2"

# Stacked bar (Left % / Right %) — use blue shades
STACKED_LEFT = "#2563eb"
STACKED_RIGHT = "#7dd3fc"

DASHBOARD_CSS = f"""
<style>
    /* ----- Force light theme: app and sidebar ----- */
    section[data-testid="stSidebar"] > div {{
        background-color: {SIDEBAR_BG} !important;
    }}
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown span,
    section[data-testid="stSidebar"] label {{
        color: {SLATE_DARK} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
        color: {SLATE_LABEL} !important;
    }}
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] [data-baseweb="select"] {{
        background-color: #ffffff !important;
        color: {SLATE_DARK} !important;
        border-color: {SLATE_BORDER} !important;
    }}
    /* Main app area light background */
    .stApp {{
        background-color: #ffffff !important;
    }}
    [data-testid="stAppViewContainer"] {{
        background-color: #ffffff !important;
    }}
    [data-testid="stAppViewContainer"] main {{
        background-color: #ffffff !important;
        color: {SLATE_DARK} !important;
    }}

    [data-testid="stMetricValue"] {{
        font-size: 1.5rem;
        font-weight: 700;
        color: {SLATE_DARK};
        letter-spacing: -0.02em;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 0.8rem;
        font-weight: 600;
        color: {SLATE_LABEL};
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    div[data-testid="metric-container"] {{
        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        border: 1px solid {SLATE_BORDER};
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border-left: 4px solid {BLUE_PRIMARY};
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }}
    div[data-testid="metric-container"]:hover {{
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.12);
    }}
    .key-number-total, .key-number-total-blue {{
        background: linear-gradient(145deg, {BLUE_BG_LIGHT} 0%, {BLUE_BG_MID} 100%) !important;
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        border: 1px solid {BLUE_BORDER};
        box-shadow: 0 1px 3px rgba(37, 99, 235, 0.2);
        border-left: 4px solid {BLUE_PRIMARY};
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }}
    .key-number-total .knt-label, .key-number-total-blue .knt-label {{
        font-size: 0.8rem;
        font-weight: 700;
        color: {BLUE_PRIMARY_DARK};
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    .key-number-total .knt-value, .key-number-total-blue .knt-value {{
        font-size: 1.5rem;
        font-weight: 800;
        color: {SLATE_DARK};
        letter-spacing: -0.02em;
    }}
    .key-number-product {{
        background: linear-gradient(145deg, {SLATE_BG} 0%, {SLATE_BG_MID} 100%) !important;
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        border: 1px solid {SLATE_BORDER};
        border-left: 4px solid {SLATE_ACCENT};
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }}
    .key-number-product .knp-label {{
        font-size: 0.75rem;
        font-weight: 500;
        color: {SLATE_LABEL};
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    .key-number-product .knp-value {{
        font-size: 1.35rem;
        font-weight: 600;
        color: {SLATE_VALUE};
    }}
    .key-number-orange {{
        background: linear-gradient(145deg, {BLUE_BG_LIGHT} 0%, {BLUE_BG_MID} 100%) !important;
        padding: 1.25rem 1.5rem;
        border-radius: 1rem;
        border: 2px solid {BLUE_BORDER};
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2), inset 0 1px 0 rgba(255,255,255,0.5);
        border-left: 5px solid {BLUE_PRIMARY};
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
        font-family: inherit;
    }}
    .key-number-orange .kno-label {{
        font-size: 0.8rem;
        font-weight: 700;
        color: {BLUE_PRIMARY_DARK};
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }}
    .key-number-orange .kno-value {{
        font-size: 2.1rem;
        font-weight: 800;
        color: {SLATE_DARK};
        letter-spacing: -0.02em;
    }}
    .key-numbers-mau-tam-row {{ margin-top: 1.5rem; height: 0.5rem; }}
    .key-numbers-row-spacer {{ margin-top: 1.25rem; height: 0.25rem; }}
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: 0.5rem; }}
    div[data-testid="stTabs"] [data-baseweb="tab"] {{
        background: linear-gradient(135deg, {TAB_BG} 0%, {TAB_BG_END} 100%);
        border-radius: 0.5rem;
        padding: 0.5rem 1.2rem;
        font-weight: 600;
    }}
    div[data-testid="stTabs"] [aria-selected="true"] {{
        background: linear-gradient(135deg, {TAB_SELECTED} 0%, {TAB_SELECTED_END} 100%);
        color: white;
    }}

    /* ----- Sidebar panel ----- */
    section[data-testid="stSidebar"] > div {{
        background: {SIDEBAR_BG} !important;
        border-right: 1px solid {SIDEBAR_BORDER} !important;
        box-shadow: 2px 0 12px rgba(0,0,0,0.04) !important;
        padding: 1rem 0.75rem 1.5rem 0.75rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 0.5rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {{
        padding: 0.5rem 0 !important;
    }}
    section[data-testid="stSidebar"] h1 {{
        background: {SIDEBAR_HEADER_BG} !important;
        color: {BLUE_PRIMARY_DARK} !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        padding: 0.75rem 1rem !important;
        margin: -1rem -1rem 0.5rem -1rem !important;
        border-radius: 0 0 10px 0 !important;
        letter-spacing: 0.02em !important;
    }}
    section[data-testid="stSidebar"] h2 {{
        color: {SLATE_DARK} !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        padding: 0.6rem 0 0.25rem 0 !important;
        margin-top: 0.75rem !important;
        border-bottom: 2px solid {SLATE_BORDER} !important;
        padding-bottom: 0.4rem !important;
    }}
    section[data-testid="stSidebar"] label {{
        font-weight: 600 !important;
        color: {SLATE_LABEL} !important;
        font-size: 0.85rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSelectbox"], section[data-testid="stSidebar"] [data-testid="stMultiSelect"] {{
        margin-bottom: 0.25rem !important;
    }}
    section[data-testid="stSidebar"] .stCaptionContainer {{
        color: {SLATE_LABEL} !important;
        font-size: 0.8rem !important;
    }}
    section[data-testid="stSidebar"] hr {{
        margin: 0.75rem 0 !important;
        border-color: {SLATE_BORDER} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div {{
        flex-wrap: wrap !important;
        gap: 0.35rem !important;
        background: {SLATE_BG} !important;
        padding: 0.4rem !important;
        border-radius: 10px !important;
        border: 1px solid {SLATE_BORDER} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stRadio"] label {{
        background: transparent !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.75rem !important;
        margin: 0 !important;
        transition: all 0.2s ease !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{
        background: {BLUE_BG_LIGHT} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radio"][aria-checked="true"] {{
        background: {BTN_PRIMARY_BG} !important;
        color: white !important;
        border-radius: 8px !important;
    }}

    /* ----- Buttons (sidebar + main) ----- */
    div[data-testid="stButton"] > button {{
        background: {BTN_PRIMARY_BG} !important;
        color: {BTN_PRIMARY_TEXT} !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: {BTN_BORDER_RADIUS} !important;
        padding: 0.5rem 1rem !important;
        box-shadow: {BTN_BOX_SHADOW} !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stButton"] > button:hover {{
        background: {BTN_PRIMARY_HOVER} !important;
        box-shadow: {BTN_HOVER_SHADOW} !important;
        transform: translateY(-1px);
    }}
    div[data-testid="stButton"] > button:active {{
        transform: translateY(0);
    }}
</style>
"""

# Inline styles for Comparison (use in st.markdown with .format() if needed)
COMPARE_BANNER_STYLE = (
    f"background: linear-gradient(135deg, {COMPARE_BG_START} 0%, {COMPARE_BG_END} 100%); "
    f"padding: 0.75rem 1.25rem; border-radius: 8px; border-left: 4px solid {COMPARE_BORDER}; margin-bottom: 1rem;"
)
COMPARE_SEGMENT_PILL_STYLE = (
    f"background: {COMPARE_SEGMENT_BG}; padding: 6px 10px; border-radius: 6px; font-weight: 700; color: {COMPARE_SEGMENT_TEXT};"
)
