"""
TAM (Total Addressable Market) Interactive Dashboard
Production-ready Streamlit app with filters, aggregation, and Plotly charts.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TAM Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
# KPI tiles (Total all segments) and chart styling
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: -0.02em;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    div[data-testid="metric-container"] {
        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border-left: 4px solid #6366f1;
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }
    div[data-testid="metric-container"]:hover {
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.12);
    }
    .key-number-total {
        background: linear-gradient(145deg, #eef2ff 0%, #e0e7ff 100%) !important;
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        border: 1px solid #c7d2fe;
        box-shadow: 0 1px 3px rgba(79, 70, 229, 0.15);
        border-left: 4px solid #4f46e5;
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }
    .key-number-total .knt-label {
        font-size: 0.8rem;
        font-weight: 700;
        color: #3730a3;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .key-number-total .knt-value {
        font-size: 1.5rem;
        font-weight: 800;
        color: #1e293b;
        letter-spacing: -0.02em;
    }
    .key-number-total-blue {
        background: linear-gradient(145deg, #eff6ff 0%, #dbeafe 100%) !important;
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        border: 1px solid #93c5fd;
        box-shadow: 0 1px 3px rgba(37, 99, 235, 0.2);
        border-left: 4px solid #2563eb;
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }
    .key-number-total-blue .knt-label {
        font-size: 0.8rem;
        font-weight: 700;
        color: #1d4ed8;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .key-number-total-blue .knt-value {
        font-size: 1.5rem;
        font-weight: 800;
        color: #1e293b;
        letter-spacing: -0.02em;
    }
    .key-number-product {
        background: linear-gradient(145deg, #fafafa 0%, #f1f5f9 100%) !important;
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #94a3b8;
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }
    .key-number-product .knp-label {
        font-size: 0.75rem;
        font-weight: 500;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .key-number-product .knp-value {
        font-size: 1.35rem;
        font-weight: 600;
        color: #475569;
    }
    .key-number-orange {
        background: linear-gradient(145deg, #ecfdf5 0%, #d1fae5 100%) !important;
        padding: 1.25rem 1.5rem;
        border-radius: 1rem;
        border: 2px solid #6ee7b7;
        box-shadow: 0 4px 12px rgba(5, 150, 105, 0.2), inset 0 1px 0 rgba(255,255,255,0.5);
        border-left: 5px solid #059669;
        height: 6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
        font-family: inherit;
    }
    .key-number-orange .kno-label {
        font-size: 0.8rem;
        font-weight: 700;
        color: #047857;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .key-number-orange .kno-value {
        font-size: 2.1rem;
        font-weight: 800;
        color: #064e3b;
        letter-spacing: -0.02em;
    }
    .key-numbers-mau-tam-row {
        margin-top: 1.5rem;
        height: 0.5rem;
    }
    .key-numbers-row-spacer {
        margin-top: 1.25rem;
        height: 0.25rem;
    } [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] {
        background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
        border-radius: 0.5rem;
        padding: 0.5rem 1.2rem;
        font-weight: 600;
    }
    div[data-testid="stTabs"] [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_PATH = "TAM Cash Final - Base inorganic.csv"
DIMENSION_COLS = ["Vehicle Class", "Credit score", "Loan type", "Ticket size"]
NUMERIC_AGG_COLS = ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]
# Total base is fixed per (Vehicle Class, Credit score). Sum it once per such segment when aggregating.
BASE_LEVEL_DIMS = ["Vehicle Class", "Credit score"]
AGG_DICT = {
    "Total base": "first",
    "Count of loans opened": "sum",
    "Loan amount (INR Cr)": "sum",
}
METRIC_OPTIONS = {
    "Incidence Rate": "new_incidence_rate",
    "Loan Amount per User (INR)": "loan_amt_per_user",
    "TAM (Cr)": "tam_cr",
}
DEFAULT_GROUPBY = ["Vehicle Class", "Loan type"]
DEFAULT_METRIC = "TAM (Cr)"
DEFAULT_MAU = 2_000_000
DEFAULT_TOP_N = 15

# ---------------------------------------------------------------------------
# Cached data load
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Support updated CSV column names (rename to expected names)
    rename = {
        "vehicle_class": "Vehicle Class",
        "score_band": "Credit score",
        "loan_type": "Loan type",
        "ticket_bucket": "Ticket size",
        "base_size_scrub": "Total base",
        "avg_loans_opened": "Count of loans opened",
        "avg_amount_inr_cr": "Loan amount (INR Cr)",
        "avg_ticket_size_inr": "Average ticket size (INR)",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    # Coerce numeric columns
    for col in ["Total base", "Count of loans opened", "Loan amount (INR Cr)", "Average ticket size (INR)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Total base", "Count of loans opened", "Loan amount (INR Cr)"])


def compute_derived(df: pd.DataFrame, mau: float, total_base_ref: float | None = None) -> pd.DataFrame:
    """Add Incidence Rate, Loan Amount per User, TAM. Safe division.
    When total_base_ref is set, TAM uses effective MAU: MAU * (segment base / total_base_ref) so segment TAMs sum to overall TAM.
    """
    out = df.copy()
    base = out["Total base"].replace(0, pd.NA)
    out["new_incidence_rate"] = (out["Count of loans opened"] / base).fillna(0)
    out["loan_amt_per_user"] = (out["Loan amount (INR Cr)"] / base).fillna(0)
    if total_base_ref and total_base_ref != 0:
        # TAM = MAU * (segment Loan amount / total_base_ref) so segment TAMs add up to overall TAM
        out["tam_cr"] = (mau * out["Loan amount (INR Cr)"] / total_base_ref).fillna(0)
    else:
        out["tam_cr"] = mau * out["loan_amt_per_user"]
    return out


def aggregate_df(
    df: pd.DataFrame,
    group_cols: list[str],
    mau: float,
    total_base_ref: float | None = None,
) -> pd.DataFrame:
    if not group_cols:
        step1 = (
            df.groupby(BASE_LEVEL_DIMS, dropna=False)
            .agg(AGG_DICT)
            .reset_index()
        )
        step2 = step1[NUMERIC_AGG_COLS].sum().to_frame().T
        ref = total_base_ref if total_base_ref and total_base_ref != 0 else float(step2["Total base"].iloc[0])
        return compute_derived(step2, mau, total_base_ref=ref)
    # First aggregate to group_cols + base level so Total base is taken once per (Vehicle Class, Credit score)
    extra = [d for d in BASE_LEVEL_DIMS if d not in group_cols]
    by_cols = group_cols + extra
    step1 = (
        df.groupby(by_cols, dropna=False)
        .agg(AGG_DICT)
        .reset_index()
    )
    # Then aggregate to group_cols only: sum everything (Total base = sum of segment bases per group)
    step2 = (
        step1.groupby(group_cols, dropna=False)[NUMERIC_AGG_COLS]
        .sum()
        .reset_index()
    )
    ref = total_base_ref if total_base_ref and total_base_ref != 0 else step2["Total base"].sum()
    agg = compute_derived(step2, mau, total_base_ref=ref)
    return agg


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def fmt_pct(x):
    if pd.isna(x):
        return ""
    return f"{float(x) * 100:.2f}%"


def fmt_tam(x):
    if pd.isna(x):
        return ""
    return f"{float(x):.2f}"


def fmt_base(x):
    if pd.isna(x):
        return ""
    return f"{int(x):,}"


def view_total_base(df: pd.DataFrame) -> float:
    """Total base for the current view: sum of Total base once per (Vehicle Class, Credit score)."""
    step = (
        df.groupby(BASE_LEVEL_DIMS, dropna=False)
        .agg(AGG_DICT)
        .reset_index()
    )
    return step["Total base"].sum()


def base_split(df: pd.DataFrame, dim: str) -> pd.DataFrame:
    """Aggregate base data by one dimension (Total base once per segment)."""
    extra = [d for d in BASE_LEVEL_DIMS if d != dim]
    by_cols = [dim] + extra
    step1 = df.groupby(by_cols, dropna=False).agg(AGG_DICT).reset_index()
    step2 = step1.groupby(dim, dropna=False)[NUMERIC_AGG_COLS].sum().reset_index()
    return step2


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
try:
    raw_df = load_data(CSV_PATH)
except FileNotFoundError:
    st.error(f"CSV file not found: {CSV_PATH}")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Filters & Settings")
if st.sidebar.button("Reload data from file", help="Use after updating the CSV"):
    st.cache_data.clear()
    st.rerun()

# 1) Filters (multi-select) — All if nothing selected
st.sidebar.subheader("Filters")
filter_vehicle = st.sidebar.multiselect(
    "Vehicle Class",
    options=sorted(raw_df["Vehicle Class"].dropna().unique().tolist()),
    default=[],
    key="filter_vehicle",
)
filter_credit = st.sidebar.multiselect(
    "Credit score",
    options=sorted(raw_df["Credit score"].dropna().unique().tolist()),
    default=[],
    key="filter_credit",
)
filter_loan = st.sidebar.multiselect(
    "Loan type",
    options=sorted(raw_df["Loan type"].dropna().unique().tolist()),
    default=[],
    key="filter_loan",
)
filter_ticket = st.sidebar.multiselect(
    "Ticket size",
    options=sorted(raw_df["Ticket size"].dropna().unique().tolist()),
    default=[],
    key="filter_ticket",
)

# Apply filters
filtered_df = raw_df.copy()
if filter_vehicle:
    filtered_df = filtered_df[filtered_df["Vehicle Class"].isin(filter_vehicle)]
if filter_credit:
    filtered_df = filtered_df[filtered_df["Credit score"].isin(filter_credit)]
if filter_loan:
    filtered_df = filtered_df[filtered_df["Loan type"].isin(filter_loan)]
if filter_ticket:
    filtered_df = filtered_df[filtered_df["Ticket size"].isin(filter_ticket)]

# 2) Group-by (multi-select, 1 or 2)
st.sidebar.subheader("Group by")
group_by = st.sidebar.multiselect(
    "Aggregation dimensions (choose 1 or 2)",
    options=DIMENSION_COLS,
    default=DEFAULT_GROUPBY,
    key="group_by",
)
if len(group_by) > 2:
    st.sidebar.warning("Please select at most 2 dimensions. Using first two.")
    group_by = group_by[:2]

# 3) Sort table by (all three metrics shown; this sets default order)
st.sidebar.subheader("Sort table by")
sort_by_metric = st.sidebar.selectbox(
    "Default sort order for table and segments",
    options=list(METRIC_OPTIONS.keys()),
    index=list(METRIC_OPTIONS.keys()).index(DEFAULT_METRIC),
    key="sort_metric",
)
selected_metric_col = METRIC_OPTIONS[sort_by_metric]
selected_metric_label = sort_by_metric

# 4) MAU input
st.sidebar.subheader("MAU")
mau = st.sidebar.number_input(
    "MAU (Monthly Active Users)",
    min_value=1,
    value=DEFAULT_MAU,
    step=10000,
    key="mau",
)

# Top N segments for bar chart
st.sidebar.subheader("Charts")
top_n = st.sidebar.slider(
    "Max segments in bar chart",
    min_value=5,
    max_value=50,
    value=DEFAULT_TOP_N,
    key="top_n",
)
st.sidebar.subheader("Crosstab TAM")
ct_row = st.sidebar.selectbox("TAM crosstab row", options=DIMENSION_COLS, index=0, key="ct_row")
ct_col_options = [c for c in DIMENSION_COLS if c != ct_row]
ct_col = st.sidebar.selectbox("TAM crosstab column", options=ct_col_options, index=0, key="ct_col")
st.sidebar.subheader("Crosstab Loan per User")
lapu_row = st.sidebar.selectbox("Loan per user crosstab row", options=DIMENSION_COLS, index=0, key="lapu_row")
lapu_col_options = [c for c in DIMENSION_COLS if c != lapu_row]
lapu_col = st.sidebar.selectbox("Loan per user crosstab column", options=lapu_col_options, index=0, key="lapu_col")

# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
view_base = view_total_base(filtered_df)
agg_df = aggregate_df(filtered_df, group_by, mau, total_base_ref=view_base)
if agg_df.empty:
    st.warning("No data after filters. Relax filters or check data.")
    st.stop()

# Segment label: "All" when no group-by, else dimension(s)
if not group_by:
    agg_df["_segment"] = "All"
elif len(group_by) == 1:
    agg_df["_segment"] = agg_df[group_by[0]].astype(str)
else:
    agg_df["_segment"] = (
        agg_df[group_by[0]].astype(str) + " | " + agg_df[group_by[1]].astype(str)
    )

# Sort by selected metric descending for table and bar
agg_df = agg_df.sort_values(selected_metric_col, ascending=False).reset_index(drop=True)

# Total: use view total base (once per Vehicle Class + Credit score), not sum of table column
total_base = view_base
total_loans = agg_df["Count of loans opened"].sum()
total_loan_amt = agg_df["Loan amount (INR Cr)"].sum()
total_nir = (total_loans / total_base) if total_base and total_base != 0 else 0
total_lapu = (total_loan_amt / total_base) if total_base and total_base != 0 else 0
# Total TAM = sum of segment TAMs
total_tam_raw = float(agg_df["tam_cr"].sum())
# When a category filter is applied: Total TAM for category = segment TAM x (% of category of total base)
total_base_overall = view_total_base(raw_df)
_filters_on = filter_vehicle or filter_credit or filter_loan or filter_ticket
if _filters_on and total_base_overall and total_base_overall != 0:
    _cat_share = total_base / total_base_overall
    total_tam = total_tam_raw * _cat_share
else:
    _cat_share = None
    total_tam = total_tam_raw

# ---------------------------------------------------------------------------
# Main layout: tabs
# ---------------------------------------------------------------------------
tab_tam, tab_base = st.tabs(["TAM Dashboard", "Base data views"])

with tab_tam:
    st.caption(f"MAU = {mau:,} | Group by: {', '.join(group_by) if group_by else 'None (overall)'} | Showing TAM, Loan Amount per User (INR), Incidence Rate")

    # Total summary strip (for current filtered view only)
    filters_active = filter_vehicle or filter_credit or filter_loan or filter_ticket
    if filters_active:
        filter_parts = []
        if filter_vehicle:
            filter_parts.append(f"Vehicle Class: {', '.join(filter_vehicle)}")
        if filter_credit:
            filter_parts.append(f"Credit score: {', '.join(filter_credit)}")
        if filter_loan:
            filter_parts.append(f"Loan type: {', '.join(filter_loan)}")
        if filter_ticket:
            filter_parts.append(f"Ticket size: {', '.join(filter_ticket)}")
        st.subheader(f"Total for filtered view")
        st.caption(f"Applied filters: {' | '.join(filter_parts)}. Totals and chart are for this selection only.")
    else:
        st.subheader("Key Numbers")

    agg_by_loan = aggregate_df(filtered_df, ["Loan type"], mau, total_base_ref=view_base)
    def _loan_val(lt: str, col: str):
        r = agg_by_loan[agg_by_loan["Loan type"].astype(str).str.upper() == lt.upper()]
        return r[col].iloc[0] if len(r) else None

    kr1, kr2, kr3, kr4 = st.columns(4)
    with kr1:
        v = _loan_val("PL", "new_incidence_rate")
        val_str = f"{v*100:.2f}%" if v is not None else "—"
        st.markdown(f'<div class="key-number-product"><div class="knp-label">Incidence rate (PL)</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
    with kr2:
        v = _loan_val("GL", "new_incidence_rate")
        val_str = f"{v*100:.2f}%" if v is not None else "—"
        st.markdown(f'<div class="key-number-product"><div class="knp-label">Incidence rate (GL)</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
    with kr3:
        v = _loan_val("BL", "new_incidence_rate")
        val_str = f"{v*100:.2f}%" if v is not None else "—"
        st.markdown(f'<div class="key-number-product"><div class="knp-label">Incidence rate (BL)</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
    with kr4:
        st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Incidence rate (Total)</div><div class="knt-value">{total_nir*100:.2f}%</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="key-numbers-row-spacer"></div>', unsafe_allow_html=True)
    ku1, ku2, ku3, ku4 = st.columns(4)
    with ku1:
        v = _loan_val("PL", "loan_amt_per_user")
        val_str = f"{(v*1e7):,.0f}" if v is not None else "—"
        st.markdown(f'<div class="key-number-product"><div class="knp-label">Loan Amount per User (PL) INR</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
    with ku2:
        v = _loan_val("GL", "loan_amt_per_user")
        val_str = f"{(v*1e7):,.0f}" if v is not None else "—"
        st.markdown(f'<div class="key-number-product"><div class="knp-label">Loan Amount per User (GL) INR</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
    with ku3:
        v = _loan_val("BL", "loan_amt_per_user")
        val_str = f"{(v*1e7):,.0f}" if v is not None else "—"
        st.markdown(f'<div class="key-number-product"><div class="knp-label">Loan Amount per User (BL) INR</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
    with ku4:
        st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Loan Amount per User (Total) INR</div><div class="knt-value">{(total_lapu*1e7):,.0f}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="key-numbers-mau-tam-row"></div>', unsafe_allow_html=True)
    r1a, r1b = st.columns(2)
    with r1a:
        st.markdown(f'<div class="key-number-orange"><div class="kno-label">MAU</div><div class="kno-value">{mau:,}</div></div>', unsafe_allow_html=True)
    with r1b:
        st.markdown(f'<div class="key-number-orange"><div class="kno-label">TAM (Cr)</div><div class="kno-value">{total_tam:.0f}</div></div>', unsafe_allow_html=True)
    if _filters_on and _cat_share is not None:
        st.caption(f"**TAM for category** = segment TAM × (% of total base) = {total_tam_raw:.0f} × ({total_base:,.0f} / {total_base_overall:,.0f}) = **{total_tam:.0f} Cr**")
    else:
        st.caption("Total TAM = sum of all segment TAMs in the table below (effective MAU).")
    if filters_active and len(group_by) == 2:
        st.info("With **Group by: 2 dimensions**, the table has multiple segments (e.g. LMV + 700-800, LMV + 800+). Total TAM is the **sum of all those rows** — it will not equal any single bar. For one total that matches one bar, use **Group by: Vehicle Class** only.")
    st.divider()

    # ----- Loan Amount per User and Incidence Rate by segment (bar charts) -----
    chart_df = agg_df.head(top_n).copy()
    chart_df["_lapu_inr"] = chart_df["loan_amt_per_user"] * 1e7
    c1, c2 = st.columns(2)
    with c1:
        if not chart_df.empty:
            fig_lapu_h = px.bar(
                chart_df, x="_segment", y="_lapu_inr",
                title="Loan Amount per User (INR) by segment",
                labels=dict(_segment="Segment", _lapu_inr="Loan Amount per User (INR)"),
                color="_lapu_inr", color_continuous_scale="Blues",
                text=chart_df["_lapu_inr"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else ""),
            )
            fig_lapu_h.update_traces(textposition="outside", textfont_size=11)
            fig_lapu_h.update_layout(showlegend=False, xaxis_tickangle=-45, xaxis_categoryorder="total descending", margin=dict(b=100), coloraxis_showscale=True, coloraxis_colorbar_title="INR")
            st.plotly_chart(fig_lapu_h, use_container_width=True)
        else:
            st.caption("No data for Loan Amount per User.")
    with c2:
        if not chart_df.empty:
            fig_nir_h = px.bar(
                chart_df, x="_segment", y="new_incidence_rate",
                title="Incidence Rate by segment",
                labels=dict(_segment="Segment", new_incidence_rate="Incidence Rate"),
                color="new_incidence_rate", color_continuous_scale="Blues",
                text=chart_df["new_incidence_rate"].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else ""),
            )
            fig_nir_h.update_traces(textposition="outside", textfont_size=11)
            fig_nir_h.update_layout(showlegend=False, xaxis_tickangle=-45, xaxis_categoryorder="total descending", margin=dict(b=100), yaxis_tickformat=".1%", coloraxis_showscale=True, coloraxis_colorbar_tickformat=".1%", coloraxis_colorbar_title="Rate")
            st.plotly_chart(fig_nir_h, use_container_width=True)
        else:
            st.caption("No data for Incidence Rate.")

    # ----- Treemap -----
    viz_df = agg_df.head(top_n).copy()
    if not viz_df.empty and total_tam > 0:
        # Treemap: TAM (Cr) by segment — area = TAM share; tile text = segment + TAM size + % share
        # Use sum of displayed segments so percentages add to 100% (not overall total_tam which can be adjusted)
        viz_df = viz_df.copy()
        total_tam_in_treemap = viz_df["tam_cr"].sum()
        viz_df["_tam_pct"] = (viz_df["tam_cr"] / total_tam_in_treemap * 100).round(1) if total_tam_in_treemap else 0
        fig_treemap = px.treemap(
            viz_df,
            path=["_segment"],
            values="tam_cr",
            title=f"TAM (Cr) by segment — area = TAM share",
            color="tam_cr",
            color_continuous_scale="Blues",
        )
        # Use customdata + texttemplate so TAM size and % share show on each tile
        tam_cr_list = viz_df["tam_cr"].tolist()
        pct_list = viz_df["_tam_pct"].tolist()
        fig_treemap.data[0].customdata = list(zip(tam_cr_list, pct_list))
        fig_treemap.data[0].texttemplate = "%{label}<br>%{customdata[0]:.0f} Cr (%{customdata[1]:.1f}%)"
        fig_treemap.data[0].textposition = "middle center"
        fig_treemap.update_layout(margin=dict(t=40, b=20, l=20, r=20), coloraxis_colorbar_tickformat=".0f")
        st.plotly_chart(fig_treemap, use_container_width=True)
    else:
        st.caption("No segment data to show other views.")

    # ----- Crosstab TAM (between two chosen dimensions) -----
    st.subheader("Crosstab TAM")
    agg_cross = aggregate_df(filtered_df, [ct_row, ct_col], mau, total_base_ref=view_base)
    if not agg_cross.empty:
        pivot_tam_cross = agg_cross.pivot(index=ct_row, columns=ct_col, values="tam_cr").fillna(0)
        fig_cross = px.imshow(
            pivot_tam_cross,
            title=f"TAM (Cr) — {ct_row} × {ct_col}",
            labels=dict(x=ct_col, y=ct_row, color="TAM (Cr)"),
            aspect="auto",
            color_continuous_scale="Blues",
        )
        fig_cross.update_layout(xaxis_tickangle=-45, margin=dict(b=100), coloraxis_colorbar_tickformat=".0f")
        st.plotly_chart(fig_cross, use_container_width=True)
        st.caption(f"Rows: {ct_row}, Columns: {ct_col}. Same filters and MAU as above.")
        # Table view of crosstab with conditional formatting (red = low, green = high)
        st.subheader(f"TAM (Cr) by {ct_row} × {ct_col} — table")
        display_pivot = pivot_tam_cross.copy()
        display_pivot.index.name = ct_row
        display_pivot = display_pivot.round(0)

        def _ratio_to_rgb(ratio: float) -> str:
            """Light blue (low) -> medium blue (high) gradient, visible but soft."""
            ratio = max(0, min(1, ratio))
            # Low: rgb(235,245,255)  High: rgb(100,160,220)
            r = int(235 - 135 * ratio)
            g = int(245 - 85 * ratio)
            b = int(255 - 35 * ratio)
            return f"rgb({r},{g},{b})"

        def _esc(s):
            return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        vmin = display_pivot.min().min()
        vmax = display_pivot.max().max()
        span = (vmax - vmin) if vmax > vmin else 1

        row_totals = display_pivot.sum(axis=1)
        col_totals = display_pivot.sum(axis=0)
        grand_total = float(display_pivot.values.sum())
        total_style = "border:1px solid #ccc; padding:6px; text-align:right; font-weight:700; background:#e2e8f0;"

        html = '<div style="overflow:auto; max-height:450px;"><table style="border-collapse:collapse; width:100%; font-size:14px;">'
        html += f"<thead><tr><th style='border:1px solid #ccc; padding:6px; text-align:left; background:#f0f0f0;'>{_esc(ct_row)}</th>"
        for c in display_pivot.columns:
            html += f"<th style='border:1px solid #ccc; padding:6px; text-align:right; background:#f0f0f0;'>{_esc(c)}</th>"
        html += f"<th style='{total_style}'>Total</th></tr></thead><tbody>"
        for idx in display_pivot.index:
            html += f"<tr><td style='border:1px solid #ccc; padding:6px; font-weight:500; background:#fafafa;'>{_esc(idx)}</td>"
            for col in display_pivot.columns:
                val = display_pivot.loc[idx, col]
                if pd.isna(val) or span == 0:
                    bg = "rgb(240,240,240)"
                else:
                    ratio = (float(val) - vmin) / span
                    bg = _ratio_to_rgb(ratio)
                html += f"<td style='border:1px solid #ccc; padding:6px; text-align:right; background:{bg};'>{val:.0f}</td>"
            html += f"<td style='{total_style}'>{row_totals.loc[idx]:.0f}</td></tr>"
        html += "<tr><td style='" + total_style.replace("text-align:right", "text-align:left") + "'>Total</td>"
        for c in display_pivot.columns:
            html += f"<td style='{total_style}'>{col_totals.loc[c]:.0f}</td>"
        html += f"<td style='{total_style}'>{grand_total:.0f}</td></tr>"
        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.info("No data for this crosstab with current filters.")

    # ----- Crosstab Loan Amount per User (INR) -----
    st.subheader("Crosstab Loan Amount per User (INR)")
    agg_cross_lapu = aggregate_df(filtered_df, [lapu_row, lapu_col], mau, total_base_ref=view_base)
    if not agg_cross_lapu.empty:
        pivot_lapu = agg_cross_lapu.pivot(index=lapu_row, columns=lapu_col, values="loan_amt_per_user").fillna(0) * 1e7
        fig_lapu = px.imshow(
            pivot_lapu,
            title=f"Loan Amount per User (INR) — {lapu_row} × {lapu_col}",
            labels=dict(x=lapu_col, y=lapu_row, color="Loan Amt per User (INR)"),
            aspect="auto",
            color_continuous_scale="Blues",
        )
        fig_lapu.update_layout(xaxis_tickangle=-45, margin=dict(b=100))
        st.plotly_chart(fig_lapu, use_container_width=True)
        st.caption(f"Rows: {lapu_row}, Columns: {lapu_col}. Same filters and MAU as above.")
        st.subheader(f"Loan Amount per User (INR) by {lapu_row} × {lapu_col} — table")
        display_lapu = pivot_lapu.copy()
        display_lapu.index.name = lapu_row
        display_lapu = display_lapu.round(0)

        def _ratio_to_rgb_lapu(ratio: float) -> str:
            """Light blue (low) -> medium blue (high) gradient, visible but soft."""
            ratio = max(0, min(1, ratio))
            r = int(235 - 135 * ratio)
            g = int(245 - 85 * ratio)
            b = int(255 - 35 * ratio)
            return f"rgb({r},{g},{b})"

        def _esc_lapu(s):
            return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        vmin_l = display_lapu.min().min()
        vmax_l = display_lapu.max().max()
        span_l = (vmax_l - vmin_l) if vmax_l > vmin_l else 1

        # Weighted average LAPU (INR) per row and column: sum(loan amount) / sum(base) * 1e7
        row_agg = agg_cross_lapu.groupby(lapu_row, dropna=False).agg({"Loan amount (INR Cr)": "sum", "Total base": "sum"}).reset_index()
        row_agg["_lapu_inr"] = (row_agg["Loan amount (INR Cr)"] / row_agg["Total base"].replace(0, pd.NA)).fillna(0) * 1e7
        row_totals_avg = row_agg.set_index(lapu_row)["_lapu_inr"]

        col_agg = agg_cross_lapu.groupby(lapu_col, dropna=False).agg({"Loan amount (INR Cr)": "sum", "Total base": "sum"}).reset_index()
        col_agg["_lapu_inr"] = (col_agg["Loan amount (INR Cr)"] / col_agg["Total base"].replace(0, pd.NA)).fillna(0) * 1e7
        col_totals_avg = col_agg.set_index(lapu_col)["_lapu_inr"]

        total_loan = agg_cross_lapu["Loan amount (INR Cr)"].sum()
        total_base_l = agg_cross_lapu["Total base"].sum()
        grand_avg_l = (total_loan / total_base_l * 1e7) if total_base_l and total_base_l != 0 else 0

        total_style_l = "border:1px solid #ccc; padding:6px; text-align:right; font-weight:700; background:#e2e8f0;"

        html_l = '<div style="overflow:auto; max-height:450px;"><table style="border-collapse:collapse; width:100%; font-size:14px;">'
        html_l += f"<thead><tr><th style='border:1px solid #ccc; padding:6px; text-align:left; background:#f0f0f0;'>{_esc_lapu(lapu_row)}</th>"
        for c in display_lapu.columns:
            html_l += f"<th style='border:1px solid #ccc; padding:6px; text-align:right; background:#f0f0f0;'>{_esc_lapu(c)}</th>"
        html_l += f"<th style='{total_style_l}'>Avg (row)</th></tr></thead><tbody>"
        for idx in display_lapu.index:
            html_l += f"<tr><td style='border:1px solid #ccc; padding:6px; font-weight:500; background:#fafafa;'>{_esc_lapu(idx)}</td>"
            for col in display_lapu.columns:
                val = display_lapu.loc[idx, col]
                if pd.isna(val) or span_l == 0:
                    bg = "rgb(240,240,240)"
                else:
                    ratio = (float(val) - vmin_l) / span_l
                    bg = _ratio_to_rgb_lapu(ratio)
                html_l += f"<td style='border:1px solid #ccc; padding:6px; text-align:right; background:{bg};'>{int(round(val)):,}</td>"
            row_avg = row_totals_avg.loc[idx] if idx in row_totals_avg.index else 0
            html_l += f"<td style='{total_style_l}'>{int(round(row_avg)):,}</td></tr>"
        html_l += "<tr><td style='" + total_style_l.replace("text-align:right", "text-align:left") + "'>Avg (col)</td>"
        for c in display_lapu.columns:
            col_avg = col_totals_avg.loc[c] if c in col_totals_avg.index else 0
            html_l += f"<td style='{total_style_l}'>{int(round(col_avg)):,}</td>"
        html_l += f"<td style='{total_style_l}'>{int(round(grand_avg_l)):,}</td></tr>"
        html_l += "</tbody></table></div>"
        st.markdown(html_l, unsafe_allow_html=True)
    else:
        st.info("No data for this crosstab with current filters.")

    # ----- Aggregated table (below) -----
    st.subheader("Aggregated table")
    label_cols = group_by if group_by else ["_segment"]
    display_df = agg_df[
        label_cols
        + [
            "Total base",
            "Count of loans opened",
            "Loan amount (INR Cr)",
            "new_incidence_rate",
            "loan_amt_per_user",
            "tam_cr",
        ]
    ].copy()
    display_df = display_df.rename(
        columns={
            "new_incidence_rate": "Incidence Rate",
            "loan_amt_per_user": "Loan Amount per User (INR)",
            "tam_cr": "TAM (Cr)",
        }
    )
    # Formatted view for display (%, 2 decimals, commas)
    display_fmt = display_df.copy()
    display_fmt["Total base"] = display_fmt["Total base"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
    display_fmt["Incidence Rate"] = display_fmt["Incidence Rate"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
    display_fmt["Loan Amount per User (INR)"] = display_fmt["Loan Amount per User (INR)"].apply(lambda x: f"{(x * 1e7):,.0f}" if pd.notna(x) else "")
    display_fmt["TAM (Cr)"] = display_fmt["TAM (Cr)"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "")
    display_fmt["Count of loans opened"] = display_fmt["Count of loans opened"].apply(lambda x: f"{round(x):,}" if pd.notna(x) else "")
    display_fmt["Loan amount (INR Cr)"] = display_fmt["Loan amount (INR Cr)"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    # Append Total row only when grouped (so we have multiple segments)
    if group_by:
        total_fmt = {col: "" for col in display_fmt.columns}
        for g in group_by:
            total_fmt[g] = "Total"
        total_fmt["Total base"] = f"{int(total_base):,}"
        total_fmt["Count of loans opened"] = f"{total_loans:,.0f}"
        total_fmt["Loan amount (INR Cr)"] = f"{total_loan_amt:.2f}"
        total_fmt["Incidence Rate"] = f"{total_nir*100:.2f}%"
        total_fmt["Loan Amount per User (INR)"] = f"{(total_lapu * 1e7):,.0f}"
        total_fmt["TAM (Cr)"] = f"{total_tam:.0f}"
        display_fmt = pd.concat([display_fmt, pd.DataFrame([total_fmt])], ignore_index=True)
    st.dataframe(
        display_fmt,
        use_container_width=True,
        height=400,
    )
    # Download Excel
    def to_excel_bytes(df_export: pd.DataFrame) -> bytes:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="TAM")
        return buf.getvalue()

    st.download_button(
        label="Download as Excel",
        data=to_excel_bytes(display_df),
        file_name="tam_aggregated.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_excel",
    )

    # ----- Top segment insight -----
    st.divider()
    top_row = agg_df.iloc[0]
    segment_label = top_row["_segment"]
    tam_val = top_row["tam_cr"]
    base_val = top_row["Total base"]
    if group_by:
        st.success(
            f"**Top segment insight:** **{segment_label}** has the highest TAM at **{tam_val:.0f} Cr** "
            f"(Total base: {fmt_base(base_val)})."
        )
    else:
        st.success(
            f"**Overall:** TAM = **{tam_val:.0f} Cr** (Total base: {fmt_base(base_val)}). "
            "Select dimensions in *Group by* to see segment breakdown."
        )

# ========== TAB 2: Base data views ==========
with tab_base:
    st.subheader("Base data: segment splits")
    st.caption("Splits use the same filters as the TAM tab. Total base is counted once per (Vehicle Class, Credit score).")

    if filtered_df.empty:
        st.warning("No data after filters.")
    else:
        # Vehicle Class split (pie only)
        st.markdown("#### Vehicle Class split")
        vc_split = base_split(filtered_df, "Vehicle Class")
        vc_split = vc_split.sort_values("Total base", ascending=False)
        fig_vc_pie = px.pie(vc_split, values="Total base", names="Vehicle Class", title="Total base % by Vehicle Class",
            color_discrete_sequence=px.colors.qualitative.Set3)
        fig_vc_pie.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
        st.plotly_chart(fig_vc_pie, use_container_width=True)

        st.divider()

        # Credit score (CIBIL) split (pie only)
        st.markdown("#### Credit score (CIBIL) split")
        cs_split = base_split(filtered_df, "Credit score")
        cs_split = cs_split.sort_values("Total base", ascending=False)
        fig_cs_pie = px.pie(cs_split, values="Total base", names="Credit score", title="Total base % by Credit score",
            color_discrete_sequence=px.colors.qualitative.Pastel2)
        fig_cs_pie.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
        st.plotly_chart(fig_cs_pie, use_container_width=True)

        # Ticket size split when a loan type is selected (pie only)
        if filter_loan:
            st.divider()
            st.markdown("#### Ticket size split (selected loan type)")
            ts_split = base_split(filtered_df, "Ticket size")
            ts_split = ts_split.sort_values("Total base", ascending=False)
            fig_ts_pie = px.pie(ts_split, values="Total base", names="Ticket size", title="Total base % by Ticket size",
                color_discrete_sequence=px.colors.qualitative.Set2)
            fig_ts_pie.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
            st.plotly_chart(fig_ts_pie, use_container_width=True)
        else:
            st.info("Select a **Loan type** in the sidebar to see Ticket size % split.")
