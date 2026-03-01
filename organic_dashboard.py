"""
Organic Incidence Dashboard
Incidence rate and Loan amount per user only (no TAM/MAU).
Data source: organic_base.xlsx
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

from dashboard_theme import (
    DASHBOARD_CSS,
    CHART_COLOR_SCALE,
    PIE_VEHICLE_CLASS,
    PIE_CREDIT_SCORE,
    PIE_TICKET_SIZE,
    COMPARE_BG_START,
    COMPARE_BG_END,
    COMPARE_BORDER,
    BLUE_LINK,
    BLUE_TEXT,
    COMPARE_VS_TEXT,
    COMPARE_SEGMENT_PILL_STYLE,
    STACKED_LEFT,
    STACKED_RIGHT,
    TABLE_TOTAL_BG,
    TABLE_HEADER_BG,
    TABLE_ROW_BG,
    TABLE_BORDER,
    sort_credit_scores_ascending,
    sort_df_by_credit_score_ascending,
)

st.set_page_config(
    page_title="Organic Incidence Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

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
DEFAULT_GROUPBY = ["Vehicle Class"]
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


def apply_filters(
    df: pd.DataFrame,
    vehicle: list,
    credit: list,
    loan: list,
    ticket: list,
    platform: list,
) -> pd.DataFrame:
    out = df.copy()
    if vehicle:
        out = out[out["Vehicle Class"].astype(str).isin([str(x) for x in vehicle])]
    if credit:
        out = out[out["Credit score"].astype(str).isin([str(x) for x in credit])]
    if loan:
        out = out[out["Loan type"].astype(str).isin([str(x) for x in loan])]
    if ticket:
        out = out[out["Ticket size"].astype(str).isin([str(x) for x in ticket])]
    if "Source" in out.columns and platform:
        out = out[out["Source"].astype(str).isin([str(x) for x in platform])]
    return out


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
# Sidebar: dynamic filters based on selected view (side view only)
# Streamlit tabs don't expose the selected tab, so we use a View selector to show only that view's filters.
# ---------------------------------------------------------------------------
st.sidebar.header("Settings")
if st.sidebar.button("Refresh", key="organic_refresh_btn", help="Reload data from file and reset all filters."):
    st.cache_data.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
st.sidebar.caption("If the dashboard still looks wrong, refresh your browser (F5) after clicking **Refresh**.")

dimension_cols_available = [c for c in DIMENSION_COLS if c in raw_df.columns]

view = st.sidebar.radio("View", ["Performance", "Segment Comparison", "Base Composition"], key="organic_view", label_visibility="collapsed")
st.sidebar.caption(f"**{view}**")
st.sidebar.divider()

if view == "Performance":
    st.sidebar.subheader("Filters & settings")
    main_vehicle = st.sidebar.multiselect("Vehicle Class", options=sorted(raw_df["Vehicle Class"].dropna().unique().tolist()), default=[], key="main_fv")
    main_credit = st.sidebar.multiselect("Credit score", options=sort_credit_scores_ascending(raw_df["Credit score"].dropna().unique().tolist()), default=[], key="main_fc")
    main_loan = st.sidebar.multiselect("Loan type", options=sorted(raw_df["Loan type"].dropna().unique().tolist()), default=[], key="main_fl")
    main_ticket = st.sidebar.multiselect("Ticket size", options=sorted(raw_df["Ticket size"].dropna().unique().tolist()), default=[], key="main_ft")
    main_platform = st.sidebar.multiselect("Source", options=sorted(raw_df["Source"].dropna().unique().tolist()), default=[], key="main_fp") if "Source" in raw_df.columns else []
    group_by = st.sidebar.multiselect("Group by (1 or 2)", options=dimension_cols_available, default=DEFAULT_GROUPBY, key="organic_main_group")
    if len(group_by) > 2:
        group_by = group_by[:2]
    sort_by_metric = st.sidebar.selectbox("Sort table by", options=list(METRIC_OPTIONS.keys()), index=list(METRIC_OPTIONS.keys()).index(DEFAULT_METRIC), key="organic_main_sort")
    selected_metric_col = METRIC_OPTIONS[sort_by_metric]
    top_n = st.sidebar.slider("Max segments in charts", min_value=5, max_value=50, value=DEFAULT_TOP_N, key="organic_main_topn")
    ct_row_ir = st.sidebar.selectbox("Crosstab IR — Row", options=dimension_cols_available, index=0, key="organic_ct_row_ir")
    ct_col_ir = st.sidebar.selectbox("Crosstab IR — Column", options=[c for c in dimension_cols_available if c != ct_row_ir], index=0, key="organic_ct_col_ir")
    ct_row_lapu = st.sidebar.selectbox("Crosstab LAPU — Row", options=dimension_cols_available, index=0, key="organic_ct_row_lapu")
    ct_col_lapu = st.sidebar.selectbox("Crosstab LAPU — Column", options=[c for c in dimension_cols_available if c != ct_row_lapu], index=0, key="organic_ct_col_lapu")
elif view == "Segment Comparison":
    st.sidebar.subheader("Segment comparison")
    comp_vehicle = []
    comp_credit = []
    comp_loan = []
    comp_ticket = []
    comp_platform = []
    comp_breakdown_by = st.sidebar.selectbox("Breakdown by", options=dimension_cols_available, index=1, key="organic_comp_breakdown")
    comp_segment_dim = st.sidebar.selectbox("Segment dimension", options=dimension_cols_available, index=0, key="organic_comp_segment_dim")
    comp_metric = st.sidebar.selectbox("Metric to compare", options=[k for k in METRIC_OPTIONS.keys() if k != "Incidence Rate"], index=0, key="organic_comp_metric")
    _comp_df_for_opts = apply_filters(raw_df, comp_vehicle, comp_credit, comp_loan, comp_ticket, comp_platform)
    _comp_opts = (sort_credit_scores_ascending(_comp_df_for_opts[comp_segment_dim].dropna().unique().tolist()) if comp_segment_dim == "Credit score" else sorted(_comp_df_for_opts[comp_segment_dim].dropna().unique().tolist())) if (not _comp_df_for_opts.empty and comp_segment_dim in _comp_df_for_opts.columns) else []
    _default_left = ["LMV"] if "LMV" in _comp_opts else (_comp_opts[:1] if _comp_opts else [])
    _default_right = ["2WN"] if "2WN" in _comp_opts else (_comp_opts[1:2] if len(_comp_opts) > 1 else [])
    comp_left = st.sidebar.multiselect("Left side: segment(s)", options=_comp_opts, default=_default_left, key="organic_comp_left")
    comp_right = st.sidebar.multiselect("Right side: segment(s)", options=_comp_opts, default=_default_right, key="organic_comp_right")
else:
    st.sidebar.subheader("Filters & settings")
    base_vehicle = st.sidebar.multiselect("Vehicle Class", options=sorted(raw_df["Vehicle Class"].dropna().unique().tolist()), default=[], key="base_fv")
    base_credit = st.sidebar.multiselect("Credit score", options=sort_credit_scores_ascending(raw_df["Credit score"].dropna().unique().tolist()), default=[], key="base_fc")
    base_loan = []
    base_ticket = []
    base_platform = st.sidebar.multiselect("Source", options=sorted(raw_df["Source"].dropna().unique().tolist()), default=[], key="base_fp") if "Source" in raw_df.columns else []

st.divider()

# ---------------------------------------------------------------------------
# Main content: driven by sidebar View (no tabs — view selector syncs sidebar + content)
# ---------------------------------------------------------------------------
if view == "Performance":
    filtered_main = apply_filters(raw_df, main_vehicle, main_credit, main_loan, main_ticket, main_platform)
    agg_df = pd.DataFrame()
    filters_active = False
    if filtered_main.empty:
        st.warning("No data after filters for this tab.")
    else:
        view_base = view_total_base(filtered_main)
        agg_df = aggregate_df(filtered_main, group_by)
        if agg_df.empty:
            st.warning("No data after aggregation.")
        else:
            if not group_by:
                agg_df = agg_df.copy()
                agg_df["_segment"] = "All"
            elif len(group_by) == 1:
                agg_df = agg_df.copy()
                agg_df["_segment"] = agg_df[group_by[0]].astype(str)
            else:
                agg_df = agg_df.copy()
                agg_df["_segment"] = agg_df[group_by[0]].astype(str) + " | " + agg_df[group_by[1]].astype(str)
            if "Credit score" in group_by:
                agg_df = sort_df_by_credit_score_ascending(agg_df, group_by).reset_index(drop=True)
            else:
                agg_df = agg_df.sort_values(selected_metric_col, ascending=False).reset_index(drop=True)
            total_base = view_base
            total_loans = agg_df["Count of loans opened"].sum()
            total_loan_amt = agg_df["Loan amount (INR Cr)"].sum()
            total_nir = (total_loans / total_base) if total_base and total_base != 0 else 0
            total_lapu = (total_loan_amt / total_base) if total_base and total_base != 0 else 0
            agg_by_loan = aggregate_df(filtered_main, ["Loan type"])
            def _loan_val(lt: str, col: str):
                r = agg_by_loan[agg_by_loan["Loan type"].astype(str).str.upper() == lt.upper()]
                return r[col].iloc[0] if len(r) else None
            filters_active = bool(main_vehicle or main_credit or main_loan or main_ticket or main_platform)

    st.caption(f"Group by: {', '.join(group_by) if group_by else 'None'} | Sort by: {sort_by_metric}")

    if not filtered_main.empty and not agg_df.empty:
        # Key Numbers
        if filters_active:
            filter_parts = []
            if main_vehicle:
                filter_parts.append(f"Vehicle Class: {', '.join(main_vehicle)}")
            if main_credit:
                filter_parts.append(f"Credit score: {', '.join(main_credit)}")
            if main_loan:
                filter_parts.append(f"Loan type: {', '.join(main_loan)}")
            if main_ticket:
                filter_parts.append(f"Ticket size: {', '.join(main_ticket)}")
            if main_platform:
                filter_parts.append(f"Source: {', '.join(main_platform)}")
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
                    color="_lapu_inr", color_continuous_scale=CHART_COLOR_SCALE,
                    text=chart_df["_lapu_inr"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else ""),
                )
                fig_lapu.update_traces(textposition="outside", textfont_size=11)
                fig_lapu.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), coloraxis_showscale=True, coloraxis_colorbar_title="INR")
                st.plotly_chart(fig_lapu, use_container_width=True, key="organic_lapu_segment")
            else:
                st.caption("No data for Loan Amount per User.")
        with c2:
            if not chart_df.empty:
                fig_nir = px.bar(
                    chart_df, x="_segment", y="new_incidence_rate",
                    title="Incidence Rate by segment",
                    labels=dict(_segment="Segment", new_incidence_rate="Incidence Rate"),
                    color="new_incidence_rate", color_continuous_scale=CHART_COLOR_SCALE,
                    text=chart_df["new_incidence_rate"].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else ""),
                )
                fig_nir.update_traces(textposition="outside", textfont_size=11)
                fig_nir.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis_tickformat=".1%", coloraxis_showscale=True, coloraxis_colorbar_tickformat=".1%", coloraxis_colorbar_title="Rate")
                st.plotly_chart(fig_nir, use_container_width=True, key="organic_nir_segment")
            else:
                st.caption("No data for Incidence Rate.")
        
        # Crosstab Incidence Rate
        st.subheader("Crosstab Incidence Rate")
        agg_cross_ir = aggregate_df(filtered_main, [ct_row_ir, ct_col_ir])
        if not agg_cross_ir.empty:
            pivot_ir = agg_cross_ir.pivot(index=ct_row_ir, columns=ct_col_ir, values="new_incidence_rate").fillna(0)
            fig_ir = px.imshow(pivot_ir, title=f"Incidence Rate — {ct_row_ir} × {ct_col_ir}", labels=dict(x=ct_col_ir, y=ct_row_ir, color="Incidence Rate"), aspect="auto", color_continuous_scale=CHART_COLOR_SCALE)
            fig_ir.update_layout(xaxis_tickangle=-45, margin=dict(b=100), coloraxis_colorbar_tickformat=".2%")
            st.plotly_chart(fig_ir, use_container_width=True, key="organic_ir_heatmap")
            st.caption(f"Rows: {ct_row_ir}, Columns: {ct_col_ir}.")
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
        agg_cross_lapu = aggregate_df(filtered_main, [ct_row_lapu, ct_col_lapu])
        if not agg_cross_lapu.empty:
            pivot_lapu_c = agg_cross_lapu.pivot(index=ct_row_lapu, columns=ct_col_lapu, values="loan_amt_per_user").fillna(0) * 1e7
            fig_lapu_c = px.imshow(pivot_lapu_c, title=f"Loan Amount per User (INR) — {ct_row_lapu} × {ct_col_lapu}", labels=dict(x=ct_col_lapu, y=ct_row_lapu, color="INR"), aspect="auto", color_continuous_scale=CHART_COLOR_SCALE)
            fig_lapu_c.update_layout(xaxis_tickangle=-45, margin=dict(b=100))
            st.plotly_chart(fig_lapu_c, use_container_width=True, key="organic_lapu_heatmap")
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

    # Aggregated table (no TAM) — only when we have data
    if not filtered_main.empty and not agg_df.empty:
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

elif view == "Segment Comparison":
    filtered_comp = apply_filters(raw_df, comp_vehicle, comp_credit, comp_loan, comp_ticket, comp_platform)
    if filtered_comp.empty:
        st.warning("No data after filters for this view.")

    st.subheader("Segment Comparison")
    st.caption("Compare one segment (left) vs another (right). Open **Filters** above to narrow data. Below the charts: **Metric split (%)** shows Left vs Right share per category.")
    if not filtered_comp.empty:
        if comp_left and comp_right:
            filtered_left = filtered_comp[filtered_comp[comp_segment_dim].astype(str).isin([str(x) for x in comp_left])]
            filtered_right = filtered_comp[filtered_comp[comp_segment_dim].astype(str).isin([str(x) for x in comp_right])]
            agg_left = aggregate_df(filtered_left, [comp_breakdown_by])
            agg_right = aggregate_df(filtered_right, [comp_breakdown_by])
            if comp_breakdown_by == "Credit score":
                agg_left = sort_df_by_credit_score_ascending(agg_left, [comp_breakdown_by])
                agg_right = sort_df_by_credit_score_ascending(agg_right, [comp_breakdown_by])
            metric_col = METRIC_OPTIONS[comp_metric]
            left_label = ", ".join(str(x) for x in comp_left)
            right_label = ", ".join(str(x) for x in comp_right)
            st.markdown(
                f'<div style="background: linear-gradient(135deg, {COMPARE_BG_START} 0%, {COMPARE_BG_END} 100%); padding: 0.75rem 1.25rem; border-radius: 8px; border-left: 4px solid {COMPARE_BORDER}; margin-bottom: 1rem;">'
                f'<span style="font-size: 1rem; color: {BLUE_TEXT};"><strong>Comparing:</strong></span> '
                f'<span style="background: #fff; padding: 4px 12px; border-radius: 6px; font-weight: 700; color: {BLUE_LINK}; margin-right: 6px;">{left_label}</span> '
                f'<span style="color: {COMPARE_VS_TEXT};">vs</span> '
                f'<span style="background: #fff; padding: 4px 12px; border-radius: 6px; font-weight: 700; color: {BLUE_LINK};">{right_label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # Base size (Total base) by breakdown — as % of segment total
            st.subheader("Base size")
            st.caption(f"Base size by {comp_breakdown_by} as % of that segment's total base (bars sum to 100% per side).")
            base_col_left, base_col_right = st.columns(2)
            with base_col_left:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{comp_segment_dim}:</span> {left_label}</div>', unsafe_allow_html=True)
                if not agg_left.empty:
                    tot_base_left = agg_left["Total base"].sum()
                    agg_left["_pct_base"] = (100 * agg_left["Total base"] / tot_base_left) if tot_base_left and tot_base_left != 0 else 0
                    agg_left["_base_txt"] = agg_left["_pct_base"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else "")
                    fig_base_l = px.bar(agg_left, x=agg_left[comp_breakdown_by].astype(str), y="_pct_base", title=f"Base size (% of segment) by {comp_breakdown_by}", labels=dict(_pct_base="Share (%)", x=comp_breakdown_by), color="_pct_base", color_continuous_scale=CHART_COLOR_SCALE, text="_base_txt")
                    fig_base_l.update_traces(textposition="outside", textfont_size=11)
                    fig_base_l.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis=dict(range=[0, 105], ticksuffix="%"), coloraxis_showscale=True)
                    st.plotly_chart(fig_base_l, use_container_width=True, key="organic_comp_base_l")
                else:
                    st.caption("No data for this segment.")
            with base_col_right:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{comp_segment_dim}:</span> {right_label}</div>', unsafe_allow_html=True)
                if not agg_right.empty:
                    tot_base_right = agg_right["Total base"].sum()
                    agg_right["_pct_base"] = (100 * agg_right["Total base"] / tot_base_right) if tot_base_right and tot_base_right != 0 else 0
                    agg_right["_base_txt"] = agg_right["_pct_base"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else "")
                    fig_base_r = px.bar(agg_right, x=agg_right[comp_breakdown_by].astype(str), y="_pct_base", title=f"Base size (% of segment) by {comp_breakdown_by}", labels=dict(_pct_base="Share (%)", x=comp_breakdown_by), color="_pct_base", color_continuous_scale=CHART_COLOR_SCALE, text="_base_txt")
                    fig_base_r.update_traces(textposition="outside", textfont_size=11)
                    fig_base_r.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis=dict(range=[0, 105], ticksuffix="%"), coloraxis_showscale=True)
                    st.plotly_chart(fig_base_r, use_container_width=True, key="organic_comp_base_r")

            if metric_col == "new_incidence_rate":
                tot_loans_left = agg_left["Count of loans opened"].sum()
                tot_loans_right = agg_right["Count of loans opened"].sum()
                agg_left = agg_left.copy()
                agg_right = agg_right.copy()
                agg_left["_pct"] = (100 * agg_left["Count of loans opened"] / tot_loans_left) if tot_loans_left and tot_loans_left != 0 else 0
                agg_right["_pct"] = (100 * agg_right["Count of loans opened"] / tot_loans_right) if tot_loans_right and tot_loans_right != 0 else 0
            else:
                tot_amt_left = agg_left["Loan amount (INR Cr)"].sum()
                tot_amt_right = agg_right["Loan amount (INR Cr)"].sum()
                agg_left = agg_left.copy()
                agg_right = agg_right.copy()
                agg_left["_pct"] = (100 * agg_left["Loan amount (INR Cr)"] / tot_amt_left) if tot_amt_left and tot_amt_left != 0 else 0
                agg_right["_pct"] = (100 * agg_right["Loan amount (INR Cr)"] / tot_amt_right) if tot_amt_right and tot_amt_right != 0 else 0
            if metric_col == "loan_amt_per_user":
                st.caption("**Loan Amount per User (INR):** For each " + comp_breakdown_by + " bucket, LAPU = (Total loan amount in Cr ÷ Total base for that bucket) × 10⁷. Total base uses **first** per base-level segment, so LAPU can look high when base is split across many rows.")
            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{comp_segment_dim}:</span> {left_label}</div>', unsafe_allow_html=True)
                if agg_left.empty:
                    st.caption("No data for this segment.")
                else:
                    agg_left["_x"] = agg_left[comp_breakdown_by].astype(str)
                    if metric_col == "new_incidence_rate":
                        agg_left["_y"] = agg_left["new_incidence_rate"]
                        agg_left["_text"] = agg_left["_y"].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else "")
                        fig_left = px.bar(agg_left, x="_x", y="_y", title=f"Incidence Rate by {comp_breakdown_by}", labels=dict(_x=comp_breakdown_by, _y="Incidence Rate"), color="_y", color_continuous_scale=CHART_COLOR_SCALE, text="_text")
                        fig_left.update_layout(yaxis_tickformat=".1%", coloraxis_colorbar_tickformat=".1%", coloraxis_cmax=1)
                    else:
                        agg_left["_y"] = agg_left["loan_amt_per_user"] * 1e7
                        agg_left["_text"] = agg_left["_y"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "")
                        fig_left = px.bar(agg_left, x="_x", y="_y", title=f"Loan Amount per User (INR) by {comp_breakdown_by}", labels=dict(_x=comp_breakdown_by, _y="INR"), color="_y", color_continuous_scale=CHART_COLOR_SCALE, text="_text")
                    fig_left.update_traces(textposition="outside", textfont_size=11)
                    fig_left.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), coloraxis_showscale=True)
                    st.plotly_chart(fig_left, use_container_width=True, key="organic_comp_left")
            with col_right:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{comp_segment_dim}:</span> {right_label}</div>', unsafe_allow_html=True)
                if agg_right.empty:
                    st.caption("No data for this segment.")
                else:
                    agg_right["_x"] = agg_right[comp_breakdown_by].astype(str)
                    if metric_col == "new_incidence_rate":
                        agg_right["_y"] = agg_right["new_incidence_rate"]
                        agg_right["_text"] = agg_right["_y"].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else "")
                        fig_right = px.bar(agg_right, x="_x", y="_y", title=f"Incidence Rate by {comp_breakdown_by}", labels=dict(_x=comp_breakdown_by, _y="Incidence Rate"), color="_y", color_continuous_scale=CHART_COLOR_SCALE, text="_text")
                        fig_right.update_layout(yaxis_tickformat=".1%", coloraxis_colorbar_tickformat=".1%", coloraxis_cmax=1)
                    else:
                        agg_right["_y"] = agg_right["loan_amt_per_user"] * 1e7
                        agg_right["_text"] = agg_right["_y"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "")
                        fig_right = px.bar(agg_right, x="_x", y="_y", title=f"Loan Amount per User (INR) by {comp_breakdown_by}", labels=dict(_x=comp_breakdown_by, _y="INR"), color="_y", color_continuous_scale=CHART_COLOR_SCALE, text="_text")
                    fig_right.update_traces(textposition="outside", textfont_size=11)
                    fig_right.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), coloraxis_showscale=True)
                    st.plotly_chart(fig_right, use_container_width=True, key="organic_comp_right")

            # Share of segment total (%)
            st.subheader("Share of segment total (%)")
            st.caption(f"Each bar shows what % of that segment's total {comp_metric} comes from that {comp_breakdown_by} category.")
            pct_left, pct_right = st.columns(2)
            with pct_left:
                if not agg_left.empty and "_pct" in agg_left.columns:
                    agg_left["_pct_text"] = agg_left["_pct"].apply(lambda v: f"{v:.0f}%" if pd.notna(v) else "")
                    fig_pct_l = px.bar(agg_left, x="_x", y="_pct", title=f"{left_label} — % of segment total", labels=dict(_x=comp_breakdown_by, _pct="Share (%)"), color="_pct", color_continuous_scale=CHART_COLOR_SCALE, text="_pct_text")
                    fig_pct_l.update_traces(textposition="outside", textfont_size=11)
                    fig_pct_l.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis=dict(range=[0, 105], ticksuffix="%"), coloraxis_showscale=True)
                    st.plotly_chart(fig_pct_l, use_container_width=True, key="organic_comp_pct_l")
            with pct_right:
                if not agg_right.empty and "_pct" in agg_right.columns:
                    agg_right["_pct_text"] = agg_right["_pct"].apply(lambda v: f"{v:.0f}%" if pd.notna(v) else "")
                    fig_pct_r = px.bar(agg_right, x="_x", y="_pct", title=f"{right_label} — % of segment total", labels=dict(_x=comp_breakdown_by, _pct="Share (%)"), color="_pct", color_continuous_scale=CHART_COLOR_SCALE, text="_pct_text")
                    fig_pct_r.update_traces(textposition="outside", textfont_size=11)
                    fig_pct_r.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis=dict(range=[0, 105], ticksuffix="%"), coloraxis_showscale=True)
                    st.plotly_chart(fig_pct_r, use_container_width=True, key="organic_comp_pct_r")

            # Percent split view
            st.subheader("Metric split (%)")
            st.caption(f"Share of {comp_metric} by segment for each {comp_breakdown_by}.")
            if not agg_left.empty and not agg_right.empty:
                left_vals = agg_left.set_index(comp_breakdown_by)["_y"]
                right_vals = agg_right.set_index(comp_breakdown_by)["_y"]
                left_d = {str(k): float(v) for k, v in left_vals.items()}
                right_d = {str(k): float(v) for k, v in right_vals.items()}
                all_cats = list(dict.fromkeys(list(left_d.keys()) + list(right_d.keys())))
                split_rows = []
                for cat in all_cats:
                    lv = left_d.get(cat, 0) or 0
                    rv = right_d.get(cat, 0) or 0
                    total = lv + rv
                    if total and total != 0:
                        split_rows.append({comp_breakdown_by: cat, "Left %": round(100 * lv / total, 1), "Right %": round(100 * rv / total, 1)})
                    else:
                        split_rows.append({comp_breakdown_by: cat, "Left %": 0.0, "Right %": 0.0})
                split_df = pd.DataFrame(split_rows)
                if not split_df.empty:
                    fig_split = px.bar(
                        split_df, x=comp_breakdown_by, y=["Left %", "Right %"],
                        title=f"Left vs Right share (%) by {comp_breakdown_by}",
                        barmode="stack", color_discrete_map={"Left %": STACKED_LEFT, "Right %": STACKED_RIGHT},
                        text_auto=".1f",
                    )
                    fig_split.update_layout(yaxis_title="Share (%)", yaxis=dict(range=[0, 100], ticksuffix="%"), xaxis_tickangle=-45, margin=dict(b=100), legend_title="Segment")
                    fig_split.update_traces(textposition="inside", textfont_size=11)
                    st.plotly_chart(fig_split, use_container_width=True, key="organic_comp_split")
                    st.dataframe(split_df.rename(columns={"Left %": f"{left_label} %", "Right %": f"{right_label} %"}), use_container_width=True, height=min(400, 80 + 35 * len(split_df)))
                else:
                    st.caption("No data for split view.")
            else:
                st.caption("Need both segments to have data for split view.")
        else:
            st.info("Choose at least one segment for **Left side** and one for **Right side** in the sidebar.")

else:
    filtered_base = apply_filters(raw_df, base_vehicle, base_credit, base_loan, base_ticket, base_platform)
    st.subheader("Base data: segment splits")
    st.caption("Splits use this tab's filters only. Total base is counted once per (Vehicle Class, Credit score).")
    if filtered_base.empty:
        st.warning("No data after filters.")
    else:
        vc_split = base_split(filtered_base, "Vehicle Class").sort_values("Total base", ascending=False)
        cs_split = sort_df_by_credit_score_ascending(base_split(filtered_base, "Credit score"), ["Credit score"])
        pie_col1, pie_col2 = st.columns(2)
        with pie_col1:
            st.markdown("#### Vehicle Class split")
            fig_vc = px.pie(vc_split, values="Total base", names="Vehicle Class", title="Total base % by Vehicle Class", color_discrete_sequence=getattr(px.colors.qualitative, PIE_VEHICLE_CLASS))
            fig_vc.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
            st.plotly_chart(fig_vc, use_container_width=True, key="organic_base_vc_pie")
        with pie_col2:
            st.markdown("#### Credit score (CIBIL) split")
            fig_cs = px.pie(cs_split, values="Total base", names="Credit score", title="Total base % by Credit score", color_discrete_sequence=getattr(px.colors.qualitative, PIE_CREDIT_SCORE))
            fig_cs.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
            st.plotly_chart(fig_cs, use_container_width=True, key="organic_base_cs_pie")
        if base_loan:
            st.divider()
            ts_split = base_split(filtered_base, "Ticket size").sort_values("Total base", ascending=False)
            fig_ts = px.pie(ts_split, values="Total base", names="Ticket size", title="Total base % by Ticket size", color_discrete_sequence=getattr(px.colors.qualitative, PIE_TICKET_SIZE))
            fig_ts.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
            st.plotly_chart(fig_ts, use_container_width=True, key="organic_base_ts_pie")
        else:
            st.info("Select a **Loan type** above to see Ticket size % split.")
