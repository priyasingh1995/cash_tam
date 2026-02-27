"""
Organic Incidence Dashboard
Incidence rate and Loan amount per user only (no TAM/MAU).
Data source: organic_base.xlsx
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

st.set_page_config(
    page_title="Organic Incidence Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Reuse same tile styling as TAM dashboard (blue totals, product tiles, row spacers)
st.markdown("""
<style>
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
    .key-numbers-row-spacer {
        margin-top: 1.25rem;
        height: 0.25rem;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 0.5rem; }
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
EXCEL_PATH = "organic_base.xlsx"
DIMENSION_COLS = ["Vehicle Class", "Credit score", "Loan type", "Ticket size", "Source"]
NUMERIC_AGG_COLS = ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]
BASE_LEVEL_DIMS = ["Vehicle Class", "Credit score"]
AGG_DICT = {
    "Total base": "first",
    "Count of loans opened": "sum",
    "Loan amount (INR Cr)": "sum",
}
METRIC_OPTIONS = {
    "Incidence Rate": "new_incidence_rate",
    "Loan Amount per User (INR)": "loan_amt_per_user",
}
DEFAULT_GROUPBY = ["Vehicle Class", "Loan type"]
DEFAULT_METRIC = "Incidence Rate"
DEFAULT_TOP_N = 15

# ---------------------------------------------------------------------------
# Cached data load (Excel)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    # Normalize column names: strip whitespace, then map common variants
    df.columns = df.columns.astype(str).str.strip()
    rename = {
        "vehicle_class": "Vehicle Class",
        "Vehicle Class": "Vehicle Class",
        "score_band": "Credit score",
        "Credit score": "Credit score",
        "loan_type": "Loan type",
        "Loan type": "Loan type",
        "ticket_bucket": "Ticket size",
        "Ticket size": "Ticket size",
        "base_size_scrub": "Total base",
        "Total base": "Total base",
        "Total Base": "Total base",
        "avg_loans_opened": "Count of loans opened",
        "Count of loans opened": "Count of loans opened",
        "avg_amount_inr_cr": "Loan amount (INR Cr)",
        "Loan amount (INR Cr)": "Loan amount (INR Cr)",
        "Loan Amount (INR Cr)": "Loan amount (INR Cr)",
        "avg_ticket_size_inr": "Average ticket size (INR)",
        "source": "Source",
        "Source": "Source",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["Total base", "Count of loans opened", "Loan amount (INR Cr)", "Average ticket size (INR)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    required = ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns: {missing}. Available: {list(df.columns)}")
    return df.dropna(subset=required)


def compute_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add Incidence Rate and Loan Amount per User only (no TAM)."""
    out = df.copy()
    base = out["Total base"].replace(0, pd.NA)
    out["new_incidence_rate"] = (out["Count of loans opened"] / base).fillna(0)
    out["loan_amt_per_user"] = (out["Loan amount (INR Cr)"] / base).fillna(0)
    return out


def aggregate_df(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if not group_cols:
        step1 = (
            df.groupby(BASE_LEVEL_DIMS, dropna=False)
            .agg(AGG_DICT)
            .reset_index()
        )
        step2 = step1[NUMERIC_AGG_COLS].sum().to_frame().T
        return compute_derived(step2)
    extra = [d for d in BASE_LEVEL_DIMS if d not in group_cols]
    by_cols = group_cols + extra
    step1 = (
        df.groupby(by_cols, dropna=False)
        .agg(AGG_DICT)
        .reset_index()
    )
    step2 = (
        step1.groupby(group_cols, dropna=False)[NUMERIC_AGG_COLS]
        .sum()
        .reset_index()
    )
    return compute_derived(step2)


def view_total_base(df: pd.DataFrame) -> float:
    step = (
        df.groupby(BASE_LEVEL_DIMS, dropna=False)
        .agg(AGG_DICT)
        .reset_index()
    )
    return step["Total base"].sum()


def base_split(df: pd.DataFrame, dim: str) -> pd.DataFrame:
    extra = [d for d in BASE_LEVEL_DIMS if d != dim]
    by_cols = [dim] + extra
    step1 = df.groupby(by_cols, dropna=False).agg(AGG_DICT).reset_index()
    step2 = step1.groupby(dim, dropna=False)[NUMERIC_AGG_COLS].sum().reset_index()
    return step2


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
try:
    raw_df = load_data(EXCEL_PATH)
except FileNotFoundError:
    st.error(f"File not found: {EXCEL_PATH}")
    st.stop()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Filters & Settings")
if st.sidebar.button("Reload data from file"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.subheader("Filters")
filter_vehicle = st.sidebar.multiselect("Vehicle Class", options=sorted(raw_df["Vehicle Class"].dropna().unique().tolist()), default=[], key="organic_fv")
filter_credit = st.sidebar.multiselect("Credit score", options=sorted(raw_df["Credit score"].dropna().unique().tolist()), default=[], key="organic_fc")
filter_loan = st.sidebar.multiselect("Loan type", options=sorted(raw_df["Loan type"].dropna().unique().tolist()), default=[], key="organic_fl")
filter_ticket = st.sidebar.multiselect("Ticket size", options=sorted(raw_df["Ticket size"].dropna().unique().tolist()), default=[], key="organic_ft")
if "Source" in raw_df.columns:
    filter_platform = st.sidebar.multiselect("Source", options=sorted(raw_df["Source"].dropna().unique().tolist()), default=[], key="organic_fp")
else:
    filter_platform = []

filtered_df = raw_df.copy()
if filter_vehicle:
    filtered_df = filtered_df[filtered_df["Vehicle Class"].isin(filter_vehicle)]
if filter_credit:
    filtered_df = filtered_df[filtered_df["Credit score"].isin(filter_credit)]
if filter_loan:
    filtered_df = filtered_df[filtered_df["Loan type"].isin(filter_loan)]
if filter_ticket:
    filtered_df = filtered_df[filtered_df["Ticket size"].isin(filter_ticket)]
if "Source" in filtered_df.columns and filter_platform:
    filtered_df = filtered_df[filtered_df["Source"].isin(filter_platform)]

st.sidebar.subheader("Group by")
dimension_cols_available = [c for c in DIMENSION_COLS if c in raw_df.columns]
group_by = st.sidebar.multiselect(
    "Aggregation dimensions (choose 1 or 2)",
    options=dimension_cols_available,
    default=DEFAULT_GROUPBY,
    key="organic_group",
)
if len(group_by) > 2:
    group_by = group_by[:2]

st.sidebar.subheader("Sort table by")
sort_by_metric = st.sidebar.selectbox(
    "Default sort order",
    options=list(METRIC_OPTIONS.keys()),
    index=list(METRIC_OPTIONS.keys()).index(DEFAULT_METRIC),
    key="organic_sort",
)
selected_metric_col = METRIC_OPTIONS[sort_by_metric]

st.sidebar.subheader("Charts")
top_n = st.sidebar.slider("Max segments in charts", min_value=5, max_value=50, value=DEFAULT_TOP_N, key="organic_topn")
st.sidebar.subheader("Crosstab Incidence Rate")
ct_row_ir = st.sidebar.selectbox("Row", options=dimension_cols_available, index=0, key="organic_ct_row_ir")
ct_col_ir = st.sidebar.selectbox("Column", options=[c for c in dimension_cols_available if c != ct_row_ir], index=0, key="organic_ct_col_ir")
st.sidebar.subheader("Crosstab Loan Amount per User")
ct_row_lapu = st.sidebar.selectbox("Row", options=dimension_cols_available, index=0, key="organic_ct_row_lapu")
ct_col_lapu = st.sidebar.selectbox("Column", options=[c for c in dimension_cols_available if c != ct_row_lapu], index=0, key="organic_ct_col_lapu")

# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
view_base = view_total_base(filtered_df)
agg_df = aggregate_df(filtered_df, group_by)
if agg_df.empty:
    st.warning("No data after filters.")
    st.stop()

if not group_by:
    agg_df["_segment"] = "All"
elif len(group_by) == 1:
    agg_df["_segment"] = agg_df[group_by[0]].astype(str)
else:
    agg_df["_segment"] = agg_df[group_by[0]].astype(str) + " | " + agg_df[group_by[1]].astype(str)

agg_df = agg_df.sort_values(selected_metric_col, ascending=False).reset_index(drop=True)

total_base = view_base
total_loans = agg_df["Count of loans opened"].sum()
total_loan_amt = agg_df["Loan amount (INR Cr)"].sum()
total_nir = (total_loans / total_base) if total_base and total_base != 0 else 0
total_lapu = (total_loan_amt / total_base) if total_base and total_base != 0 else 0

# By loan type for Key Numbers
agg_by_loan = aggregate_df(filtered_df, ["Loan type"])
def _loan_val(lt: str, col: str):
    r = agg_by_loan[agg_by_loan["Loan type"].astype(str).str.upper() == lt.upper()]
    return r[col].iloc[0] if len(r) else None

filters_active = filter_vehicle or filter_credit or filter_loan or filter_ticket or filter_platform
st.divider()

# ---------------------------------------------------------------------------
# Tabs: Organic Incidence | Base data views
# ---------------------------------------------------------------------------
tab_main, tab_base = st.tabs(["Organic Incidence", "Base data views"])

with tab_main:
    st.caption(f"Group by: {', '.join(group_by) if group_by else 'None'} | Sort by: {sort_by_metric}")

    # Key Numbers
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
        if filter_platform:
            filter_parts.append(f"Source: {', '.join(filter_platform)}")
        st.subheader("Total for filtered view")
        st.caption(f"Applied filters: {' | '.join(filter_parts)}.")
    else:
        st.subheader("Key Numbers")

    # Row 1: Incidence rate (PL, GL, BL, Total blue)
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
    
    # Row 2: Loan amount per user (PL, GL, BL, Total blue)
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
    
    st.divider()
    
    # Heatmaps
    chart_df = agg_df.head(top_n).copy()
    chart_df["_lapu_inr"] = chart_df["loan_amt_per_user"] * 1e7
    c1, c2 = st.columns(2)
    with c1:
        if not chart_df.empty:
            fig_lapu = px.bar(
                chart_df, x="_segment", y="_lapu_inr",
                title="Loan Amount per User (INR) by segment",
                labels=dict(_segment="Segment", _lapu_inr="Loan Amount per User (INR)"),
                color="_lapu_inr", color_continuous_scale="Blues",
                text=chart_df["_lapu_inr"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else ""),
            )
            fig_lapu.update_traces(textposition="outside", textfont_size=11)
            fig_lapu.update_layout(showlegend=False, xaxis_tickangle=-45, xaxis_categoryorder="total descending", margin=dict(b=100), coloraxis_showscale=True, coloraxis_colorbar_title="INR")
            st.plotly_chart(fig_lapu, use_container_width=True)
        else:
            st.caption("No data for Loan Amount per User.")
    with c2:
        if not chart_df.empty:
            fig_nir = px.bar(
                chart_df, x="_segment", y="new_incidence_rate",
                title="Incidence Rate by segment",
                labels=dict(_segment="Segment", new_incidence_rate="Incidence Rate"),
                color="new_incidence_rate", color_continuous_scale="Blues",
                text=chart_df["new_incidence_rate"].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else ""),
            )
            fig_nir.update_traces(textposition="outside", textfont_size=11)
            fig_nir.update_layout(showlegend=False, xaxis_tickangle=-45, xaxis_categoryorder="total descending", margin=dict(b=100), yaxis_tickformat=".1%", coloraxis_showscale=True, coloraxis_colorbar_tickformat=".1%", coloraxis_colorbar_title="Rate")
            st.plotly_chart(fig_nir, use_container_width=True)
        else:
            st.caption("No data for Incidence Rate.")
    
    # Crosstab Incidence Rate
    st.subheader("Crosstab Incidence Rate")
    agg_cross_ir = aggregate_df(filtered_df, [ct_row_ir, ct_col_ir])
    if not agg_cross_ir.empty:
        pivot_ir = agg_cross_ir.pivot(index=ct_row_ir, columns=ct_col_ir, values="new_incidence_rate").fillna(0)
        fig_ir = px.imshow(pivot_ir, title=f"Incidence Rate — {ct_row_ir} × {ct_col_ir}", labels=dict(x=ct_col_ir, y=ct_row_ir, color="Incidence Rate"), aspect="auto", color_continuous_scale="Blues")
        fig_ir.update_layout(xaxis_tickangle=-45, margin=dict(b=100), coloraxis_colorbar_tickformat=".2%")
        st.plotly_chart(fig_ir, use_container_width=True)
        st.caption(f"Rows: {ct_row_ir}, Columns: {ct_col_ir}.")
        # Table with conditional formatting (light blue gradient)
        st.markdown(f"**Incidence Rate by {ct_row_ir} × {ct_col_ir} — table**")
        display_ir = pivot_ir.copy().round(4)
        display_ir.index.name = ct_row_ir
        vmin_ir = display_ir.min().min()
        vmax_ir = display_ir.max().max()
        span_ir = (vmax_ir - vmin_ir) if vmax_ir > vmin_ir else 1
        def _rgb_ir(r): r = max(0, min(1, r)); return f"rgb({int(235-135*r)},{int(245-85*r)},{int(255-35*r)})"
        def _esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        row_tot_ir = display_ir.sum(axis=1)
        col_tot_ir = display_ir.sum(axis=0)
        grand_ir = display_ir.values.sum()
        ts = "border:1px solid #ccc; padding:6px; text-align:right; font-weight:700; background:#e2e8f0;"
        html_ir = '<div style="overflow:auto; max-height:450px;"><table style="border-collapse:collapse; width:100%; font-size:14px;">'
        html_ir += f"<thead><tr><th style='border:1px solid #ccc; padding:6px; text-align:left; background:#f0f0f0;'>{_esc(ct_row_ir)}</th>"
        for c in display_ir.columns:
            html_ir += f"<th style='border:1px solid #ccc; padding:6px; text-align:right; background:#f0f0f0;'>{_esc(c)}</th>"
        html_ir += f"<th style='{ts}'>Total</th></tr></thead><tbody>"
        for idx in display_ir.index:
            html_ir += f"<tr><td style='border:1px solid #ccc; padding:6px; font-weight:500; background:#fafafa;'>{_esc(idx)}</td>"
            for col in display_ir.columns:
                val = display_ir.loc[idx, col]
                ratio = (float(val) - vmin_ir) / span_ir if span_ir else 0
                html_ir += f"<td style='border:1px solid #ccc; padding:6px; text-align:right; background:{_rgb_ir(ratio)};'>{val*100:.2f}%</td>"
            html_ir += f"<td style='{ts}'>{row_tot_ir.loc[idx]*100:.2f}%</td></tr>"
        ts_left = ts.replace("text-align:right", "text-align:left")
        html_ir += f"<tr><td style='{ts_left}'>Total</td>"
        for c in display_ir.columns:
            html_ir += f"<td style='{ts}'>{col_tot_ir.loc[c]*100:.2f}%</td>"
        html_ir += f"<td style='{ts}'>{grand_ir*100:.2f}%</td></tr></tbody></table></div>"
        st.markdown(html_ir, unsafe_allow_html=True)
    else:
        st.info("No data for this crosstab.")
    
    # Crosstab Loan Amount per User
    st.subheader("Crosstab Loan Amount per User (INR)")
    agg_cross_lapu = aggregate_df(filtered_df, [ct_row_lapu, ct_col_lapu])
    if not agg_cross_lapu.empty:
        pivot_lapu_c = agg_cross_lapu.pivot(index=ct_row_lapu, columns=ct_col_lapu, values="loan_amt_per_user").fillna(0) * 1e7
        fig_lapu_c = px.imshow(pivot_lapu_c, title=f"Loan Amount per User (INR) — {ct_row_lapu} × {ct_col_lapu}", labels=dict(x=ct_col_lapu, y=ct_row_lapu, color="INR"), aspect="auto", color_continuous_scale="Blues")
        fig_lapu_c.update_layout(xaxis_tickangle=-45, margin=dict(b=100))
        st.plotly_chart(fig_lapu_c, use_container_width=True)
        st.caption(f"Rows: {ct_row_lapu}, Columns: {ct_col_lapu}.")
        st.markdown(f"**Loan Amount per User (INR) by {ct_row_lapu} × {ct_col_lapu} — table**")
        display_lapu = pivot_lapu_c.copy().round(0)
        display_lapu.index.name = ct_row_lapu
        vmin_l = display_lapu.min().min()
        vmax_l = display_lapu.max().max()
        span_l = (vmax_l - vmin_l) if vmax_l > vmin_l else 1
        def _rgb_l(r): r = max(0, min(1, r)); return f"rgb({int(235-135*r)},{int(245-85*r)},{int(255-35*r)})"
        row_agg = agg_cross_lapu.groupby(ct_row_lapu, dropna=False).agg({"Loan amount (INR Cr)": "sum", "Total base": "sum"}).reset_index()
        row_agg["_lapu_inr"] = (row_agg["Loan amount (INR Cr)"] / row_agg["Total base"].replace(0, pd.NA)).fillna(0) * 1e7
        row_totals_avg = row_agg.set_index(ct_row_lapu)["_lapu_inr"]
        col_agg = agg_cross_lapu.groupby(ct_col_lapu, dropna=False).agg({"Loan amount (INR Cr)": "sum", "Total base": "sum"}).reset_index()
        col_agg["_lapu_inr"] = (col_agg["Loan amount (INR Cr)"] / col_agg["Total base"].replace(0, pd.NA)).fillna(0) * 1e7
        col_totals_avg = col_agg.set_index(ct_col_lapu)["_lapu_inr"]
        total_loan_l = agg_cross_lapu["Loan amount (INR Cr)"].sum()
        total_base_l = agg_cross_lapu["Total base"].sum()
        grand_avg_l = (total_loan_l / total_base_l * 1e7) if total_base_l and total_base_l != 0 else 0
        ts_l = "border:1px solid #ccc; padding:6px; text-align:right; font-weight:700; background:#e2e8f0;"
        html_l = '<div style="overflow:auto; max-height:450px;"><table style="border-collapse:collapse; width:100%; font-size:14px;">'
        html_l += f"<thead><tr><th style='border:1px solid #ccc; padding:6px; text-align:left; background:#f0f0f0;'>{_esc(ct_row_lapu)}</th>"
        for c in display_lapu.columns:
            html_l += f"<th style='border:1px solid #ccc; padding:6px; text-align:right; background:#f0f0f0;'>{_esc(c)}</th>"
        html_l += f"<th style='{ts_l}'>Avg (row)</th></tr></thead><tbody>"
        for idx in display_lapu.index:
            html_l += f"<tr><td style='border:1px solid #ccc; padding:6px; font-weight:500; background:#fafafa;'>{_esc(idx)}</td>"
            for col in display_lapu.columns:
                val = display_lapu.loc[idx, col]
                ratio = (float(val) - vmin_l) / span_l if span_l else 0
                html_l += f"<td style='border:1px solid #ccc; padding:6px; text-align:right; background:{_rgb_l(ratio)};'>{int(round(val)):,}</td>"
            row_avg = row_totals_avg.loc[idx] if idx in row_totals_avg.index else 0
            html_l += f"<td style='{ts_l}'>{int(round(row_avg)):,}</td></tr>"
        ts_l_left = ts_l.replace("text-align:right", "text-align:left")
        html_l += f"<tr><td style='{ts_l_left}'>Avg (col)</td>"
        for c in display_lapu.columns:
            html_l += f"<td style='{ts_l}'>{int(round(col_totals_avg.loc[c] if c in col_totals_avg.index else 0)):,}</td>"
        html_l += f"<td style='{ts_l}'>{int(round(grand_avg_l)):,}</td></tr></tbody></table></div>"
        st.markdown(html_l, unsafe_allow_html=True)
    else:
        st.info("No data for this crosstab.")

# Aggregated table (no TAM)
st.subheader("Aggregated table")
label_cols = group_by if group_by else ["_segment"]
display_df = agg_df[label_cols + ["Total base", "Count of loans opened", "Loan amount (INR Cr)", "new_incidence_rate", "loan_amt_per_user"]].copy()
display_df = display_df.rename(columns={"new_incidence_rate": "Incidence Rate", "loan_amt_per_user": "Loan Amount per User (INR)"})
display_fmt = display_df.copy()
display_fmt["Total base"] = display_fmt["Total base"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
display_fmt["Incidence Rate"] = display_fmt["Incidence Rate"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
display_fmt["Loan Amount per User (INR)"] = display_fmt["Loan Amount per User (INR)"].apply(lambda x: f"{(x * 1e7):,.0f}" if pd.notna(x) else "")
display_fmt["Count of loans opened"] = display_fmt["Count of loans opened"].apply(lambda x: f"{round(x):,}" if pd.notna(x) else "")
display_fmt["Loan amount (INR Cr)"] = display_fmt["Loan amount (INR Cr)"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
if group_by:
    total_fmt = {col: "" for col in display_fmt.columns}
    for g in group_by:
        total_fmt[g] = "Total"
    total_fmt["Total base"] = f"{int(total_base):,}"
    total_fmt["Count of loans opened"] = f"{total_loans:,.0f}"
    total_fmt["Loan amount (INR Cr)"] = f"{total_loan_amt:.2f}"
    total_fmt["Incidence Rate"] = f"{total_nir*100:.2f}%"
    total_fmt["Loan Amount per User (INR)"] = f"{(total_lapu * 1e7):,.0f}"
    display_fmt = pd.concat([display_fmt, pd.DataFrame([total_fmt])], ignore_index=True)
st.dataframe(display_fmt, use_container_width=True, height=400)

def to_excel_bytes(df_export: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Organic")
    return buf.getvalue()

st.download_button(
    label="Download as Excel",
    data=to_excel_bytes(display_df),
    file_name="organic_incidence_aggregated.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    key="organic_download",
)

# Top segment insight (by selected metric)
st.divider()
top_row = agg_df.iloc[0]
segment_label = top_row["_segment"]
base_val = top_row["Total base"]
if sort_by_metric == "Incidence Rate":
    val = top_row["new_incidence_rate"] * 100
    st.success(f"**Top segment:** **{segment_label}** has the highest Incidence Rate at **{val:.2f}%** (Total base: {int(base_val):,}).")
else:
    val_inr = top_row["loan_amt_per_user"] * 1e7
    st.success(f"**Top segment:** **{segment_label}** has the highest Loan Amount per User at **{val_inr:,.0f} INR** (Total base: {int(base_val):,}).")

with tab_base:
    st.subheader("Base data: segment splits")
    st.caption("Splits use the same filters. Total base is counted once per (Vehicle Class, Credit score).")
    if filtered_df.empty:
        st.warning("No data after filters.")
    else:
        vc_split = base_split(filtered_df, "Vehicle Class").sort_values("Total base", ascending=False)
        fig_vc = px.pie(vc_split, values="Total base", names="Vehicle Class", title="Total base % by Vehicle Class", color_discrete_sequence=px.colors.qualitative.Set3)
        fig_vc.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
        st.plotly_chart(fig_vc, use_container_width=True)
        st.divider()
        cs_split = base_split(filtered_df, "Credit score").sort_values("Total base", ascending=False)
        fig_cs = px.pie(cs_split, values="Total base", names="Credit score", title="Total base % by Credit score", color_discrete_sequence=px.colors.qualitative.Pastel2)
        fig_cs.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
        st.plotly_chart(fig_cs, use_container_width=True)
        if filter_loan:
            st.divider()
            ts_split = base_split(filtered_df, "Ticket size").sort_values("Total base", ascending=False)
            fig_ts = px.pie(ts_split, values="Total base", names="Ticket size", title="Total base % by Ticket size", color_discrete_sequence=px.colors.qualitative.Set2)
            fig_ts.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
            st.plotly_chart(fig_ts, use_container_width=True)
        else:
            st.info("Select a **Loan type** in the sidebar to see Ticket size % split.")
