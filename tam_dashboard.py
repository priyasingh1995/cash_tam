"""
TAM (Total Addressable Market) Interactive Dashboard
Production-ready Streamlit app with filters, aggregation, and Plotly charts.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from typing import Optional

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
    sort_credit_scores_ascending,
    sort_df_by_credit_score_ascending,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TAM Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_PATH = "TAM Cash Final - Base inorganic.csv"
# Set to True only if your CSV stores loan amount in LAKHS (then LAPU is correct but TAM becomes ~100x smaller).
LOAN_AMOUNT_CSV_IN_LAKHS = False
DIMENSION_COLS = ["Vehicle Class", "Credit score", "Loan type", "Ticket size"]
# Display label for dimensions (e.g. "Vehicle" instead of "Vehicle Class")
DIMENSION_LABEL = {"Vehicle Class": "Vehicle"}
def _dim_label(col: str) -> str:
    return DIMENSION_LABEL.get(col, col)
NUMERIC_AGG_COLS = ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]
# Total base: "first" keeps TAM at expected level (total_base_ref stays smaller).
# Use "sum" only if your base is split by sub-segment and you want LAPU = sum(loan_amt)/sum(base).
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
DEFAULT_GROUPBY = ["Vehicle Class"]
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
    if LOAN_AMOUNT_CSV_IN_LAKHS and "Loan amount (INR Cr)" in df.columns:
        # 1 Cr = 100 lakhs → amount_cr = amount_lakhs / 100
        df["Loan amount (INR Cr)"] = df["Loan amount (INR Cr)"] / 100.0
    required = ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}. "
            "Add renames in load_data() for your CSV's column names."
        )
    return df.dropna(subset=required)


def apply_filters(
    df: pd.DataFrame,
    vehicle: list,
    credit: list,
    loan: list,
    ticket: list,
) -> pd.DataFrame:
    """Filter by dimension multiselects; empty list = no filter on that dimension."""
    out = df.copy()
    if vehicle:
        out = out[out["Vehicle Class"].astype(str).isin([str(x) for x in vehicle])]
    if credit:
        out = out[out["Credit score"].astype(str).isin([str(x) for x in credit])]
    if loan:
        out = out[out["Loan type"].astype(str).isin([str(x) for x in loan])]
    if ticket:
        out = out[out["Ticket size"].astype(str).isin([str(x) for x in ticket])]
    return out


def checkbox_multiselect(label: str, options: list, default: Optional[list] = None, key_prefix: str = "cb") -> list:
    """Render multi-selection as checkboxes in an expander. Empty default = no filter (all unchecked)."""
    if default is None:
        default = []
    # Compute current selection from session state for label
    n_selected = sum(1 for i, opt in enumerate(options) if st.session_state.get(f"{key_prefix}_{i}", opt in default))
    expander_label = f"**{label}** — {n_selected} selected" if options else f"**{label}**"
    with st.sidebar.expander(expander_label, expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Select all", key=f"{key_prefix}_sa"):
                for i in range(len(options)):
                    st.session_state[f"{key_prefix}_{i}"] = True
                st.rerun()
        with c2:
            if st.button("Clear all", key=f"{key_prefix}_ca"):
                for i in range(len(options)):
                    st.session_state[f"{key_prefix}_{i}"] = False
                st.rerun()
        selected = []
        for i, opt in enumerate(options):
            k = f"{key_prefix}_{i}"
            if st.checkbox(str(opt), value=st.session_state.get(k, opt in default), key=k):
                selected.append(opt)
    return selected


def compute_derived(df: pd.DataFrame, mau: float, total_base_ref: Optional[float] = None) -> pd.DataFrame:
    """Add Incidence Rate, Loan Amount per User, TAM, Average ticket size (INR). Safe division.
    When total_base_ref is set, TAM uses effective MAU: MAU * (segment base / total_base_ref) so segment TAMs sum to overall TAM.
    Average ticket size = sum of loans (INR) / count of loans = (Loan amount in Cr / Count of loans) * 1e7.
    """
    out = df.copy()
    base = out["Total base"].replace(0, pd.NA)
    out["new_incidence_rate"] = (out["Count of loans opened"] / base).fillna(0)
    out["loan_amt_per_user"] = (out["Loan amount (INR Cr)"] / base).fillna(0)
    count_loans = out["Count of loans opened"].replace(0, pd.NA)
    out["avg_ticket_size_inr"] = (out["Loan amount (INR Cr)"] / count_loans).fillna(0) * 1e7  # INR
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
    total_base_ref: Optional[float] = None,
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
except ValueError as e:
    st.error(str(e))
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar: dynamic filters based on selected view (side view only)
# Streamlit tabs don't expose the selected tab, so we use a View selector to show only that view's filters.
# ---------------------------------------------------------------------------
st.sidebar.header("Settings")
if st.sidebar.button("Refresh", key="tam_refresh_btn", help="Reload data from file and reset all filters."):
    st.cache_data.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
st.sidebar.caption("If the dashboard still looks wrong, refresh your browser (F5) after clicking **Refresh**.")

view = st.sidebar.radio("View", ["TAM", "Segment Comparison", "Base Composition"], key="tam_view", label_visibility="collapsed")
st.sidebar.caption(f"**{view}**")
st.sidebar.divider()

if view == "TAM":
    st.sidebar.subheader("Filters & settings")
    mau = st.sidebar.number_input("MAU (Monthly Active Users)", min_value=1, value=DEFAULT_MAU, step=10000, key="tam_mau")
    _vehicle_opts = sorted(raw_df["Vehicle Class"].dropna().unique().tolist())
    _credit_opts = sort_credit_scores_ascending(raw_df["Credit score"].dropna().unique().tolist())
    _loan_opts = sorted(raw_df["Loan type"].dropna().unique().tolist())
    _ticket_opts = sorted(raw_df["Ticket size"].dropna().unique().tolist())
    filter_vehicle = checkbox_multiselect("Vehicle", _vehicle_opts, default=[], key_prefix="tam_fv")
    filter_credit = checkbox_multiselect("Credit score", _credit_opts, default=[], key_prefix="tam_fc")
    filter_loan = checkbox_multiselect("Loan type", _loan_opts, default=[], key_prefix="tam_fl")
    filter_ticket = checkbox_multiselect("Ticket size", _ticket_opts, default=[], key_prefix="tam_ft")
    group_by = checkbox_multiselect("Group by (1 or 2)", [_dim_label(c) for c in DIMENSION_COLS], default=[_dim_label(c) for c in DEFAULT_GROUPBY], key_prefix="tam_group_by")
    if len(group_by) > 2:
        group_by = group_by[:2]
    _label_to_col = {_dim_label(c): c for c in DIMENSION_COLS}
    group_by = [_label_to_col.get(g, g) for g in group_by]
    sort_by_metric = st.sidebar.selectbox("Sort table by", options=list(METRIC_OPTIONS.keys()), index=list(METRIC_OPTIONS.keys()).index(DEFAULT_METRIC), key="tam_sort_metric")
    selected_metric_col = METRIC_OPTIONS[sort_by_metric]
    selected_metric_label = sort_by_metric
    top_n = st.sidebar.slider("Max segments in bar chart", min_value=5, max_value=50, value=DEFAULT_TOP_N, key="tam_top_n")
    _ct_row_label = st.sidebar.selectbox("Crosstab TAM — Row", options=[_dim_label(c) for c in DIMENSION_COLS], index=0, key="tam_ct_row")
    ct_row = _label_to_col.get(_ct_row_label, _ct_row_label)
    _ct_col_label = st.sidebar.selectbox("Crosstab TAM — Column", options=[_dim_label(c) for c in DIMENSION_COLS if c != ct_row], index=0, key="tam_ct_col")
    ct_col = _label_to_col.get(_ct_col_label, _ct_col_label)
    _lapu_row_label = st.sidebar.selectbox("Crosstab LAPU — Row", options=[_dim_label(c) for c in DIMENSION_COLS], index=0, key="tam_lapu_row")
    lapu_row = _label_to_col.get(_lapu_row_label, _lapu_row_label)
    _lapu_col_label = st.sidebar.selectbox("Crosstab LAPU — Column", options=[_dim_label(c) for c in DIMENSION_COLS if c != lapu_row], index=0, key="tam_lapu_col")
    lapu_col = _label_to_col.get(_lapu_col_label, _lapu_col_label)
elif view == "Segment Comparison":
    st.sidebar.subheader("Segment comparison")
    comp_vehicle = []
    comp_credit = []
    comp_loan = []
    comp_ticket = []
    mau_comp = st.sidebar.number_input("MAU (for TAM)", min_value=1, value=DEFAULT_MAU, step=10000, key="tam_comp_mau")
    _label_to_col_comp = {_dim_label(c): c for c in DIMENSION_COLS}
    _comp_breakdown_label = st.sidebar.selectbox("Breakdown by", options=[_dim_label(c) for c in DIMENSION_COLS], index=1, key="tam_comp_breakdown")
    tam_comp_breakdown = _label_to_col_comp.get(_comp_breakdown_label, _comp_breakdown_label)
    _comp_segment_label = st.sidebar.selectbox("Segment dim", options=[_dim_label(c) for c in DIMENSION_COLS], index=0, key="tam_comp_seg_dim")
    tam_comp_segment_dim = _label_to_col_comp.get(_comp_segment_label, _comp_segment_label)
    _comp_df_for_opts = apply_filters(raw_df, comp_vehicle, comp_credit, comp_loan, comp_ticket)
    _opts = (sort_credit_scores_ascending(_comp_df_for_opts[tam_comp_segment_dim].dropna().unique().tolist()) if tam_comp_segment_dim == "Credit score" else sorted(_comp_df_for_opts[tam_comp_segment_dim].dropna().unique().tolist())) if (not _comp_df_for_opts.empty and tam_comp_segment_dim in _comp_df_for_opts.columns) else []
    _default_left = ["LMV"] if "LMV" in _opts else (_opts[:1] if _opts else [])
    _default_right = ["2WN"] if "2WN" in _opts else (_opts[1:2] if len(_opts) > 1 else [])
    tam_comp_left = checkbox_multiselect("Left side: segment(s)", _opts, default=_default_left, key_prefix="tam_comp_left")
    tam_comp_right = checkbox_multiselect("Right side: segment(s)", _opts, default=_default_right, key_prefix="tam_comp_right")
else:
    st.sidebar.subheader("Filters & settings")
    _base_vehicle_opts = sorted(raw_df["Vehicle Class"].dropna().unique().tolist())
    _base_credit_opts = sort_credit_scores_ascending(raw_df["Credit score"].dropna().unique().tolist())
    base_vehicle = checkbox_multiselect("Vehicle", _base_vehicle_opts, default=[], key_prefix="tam_base_fv")
    base_credit = checkbox_multiselect("Credit score", _base_credit_opts, default=[], key_prefix="tam_base_fc")
    base_loan = []
    base_ticket = []

# ---------------------------------------------------------------------------
# Main content: driven by sidebar View
# ---------------------------------------------------------------------------
if view == "TAM":
    filtered_df = apply_filters(raw_df, filter_vehicle, filter_credit, filter_loan, filter_ticket)
    agg_df = pd.DataFrame()
    if filtered_df.empty:
        st.warning("No data after filters for this tab.")
    else:
        view_base = view_total_base(filtered_df)
        agg_df = aggregate_df(filtered_df, group_by, mau, total_base_ref=view_base)
        if agg_df.empty:
            st.warning("No data after aggregation.")
        else:
            if not group_by:
                agg_df["_segment"] = "All"
            elif len(group_by) == 1:
                agg_df["_segment"] = agg_df[group_by[0]].astype(str)
            else:
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
            total_avg_ticket = (total_loan_amt * 1e7 / total_loans) if total_loans and total_loans != 0 else 0
            total_tam_raw = float(agg_df["tam_cr"].sum())
            total_base_overall = view_total_base(raw_df)
            _filters_on = filter_vehicle or filter_credit or filter_loan or filter_ticket
            if _filters_on and total_base_overall and total_base_overall != 0:
                _cat_share = total_base / total_base_overall
                total_tam = total_tam_raw * _cat_share
            else:
                _cat_share = None
                total_tam = total_tam_raw

    st.caption(f"MAU = {mau:,} | Group by: {', '.join(_dim_label(g) for g in group_by) if group_by else 'None (overall)'} | Showing TAM, Loan Amount per User (INR), Incidence Rate, Average ticket size (INR)")

    if not filtered_df.empty and not agg_df.empty:
        # Total summary strip (for current filtered view only)
        filters_active = filter_vehicle or filter_credit or filter_loan or filter_ticket
        if filters_active:
            filter_parts = []
            if filter_vehicle:
                filter_parts.append(f"Vehicle: {', '.join(filter_vehicle)}")
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

        # MAU and TAM (Cr) at the top
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
            st.info("With **Group by: 2 dimensions**, the table has multiple segments (e.g. LMV + 700-800, LMV + 800+). Total TAM is the **sum of all those rows** — it will not equal any single bar. For one total that matches one bar, use **Group by: Vehicle** only.")
        st.markdown('<div class="key-numbers-mau-tam-row"></div>', unsafe_allow_html=True)

        agg_by_loan = aggregate_df(filtered_df, ["Loan type"], mau, total_base_ref=view_base)
        loan_types = (
            agg_by_loan.sort_values("new_incidence_rate", ascending=False)["Loan type"].astype(str).tolist()
            if not agg_by_loan.empty else []
        )
        def _loan_val(lt: str, col: str):
            r = agg_by_loan[agg_by_loan["Loan type"].astype(str).str.upper() == lt.upper()]
            return r[col].iloc[0] if len(r) else None

        # Incidence rate: one tile per loan type + Total (all loan types included in total)
        n_loan = len(loan_types) + 1
        max_per_row = 6  # when more, use two rows so tiles are wider and readable
        use_two_rows = len(loan_types) > max_per_row

        # ----- TAM contribution (Cr) by loan type — right after MAU & TAM -----
        st.markdown('<p class="key-numbers-row-title key-numbers-row-title--tam">TAM contribution (Cr)</p>', unsafe_allow_html=True)
        if use_two_rows:
            cols_tam_1 = st.columns(max_per_row)
            for i, lt in enumerate(loan_types[:max_per_row]):
                with cols_tam_1[i]:
                    v = _loan_val(lt, "tam_cr")
                    val_str = f"{v:,.0f}" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--tam"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            n_second = len(loan_types) - max_per_row + 1
            cols_tam_2 = st.columns(n_second)
            for i, lt in enumerate(loan_types[max_per_row:]):
                with cols_tam_2[i]:
                    v = _loan_val(lt, "tam_cr")
                    val_str = f"{v:,.0f}" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--tam"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            with cols_tam_2[-1]:
                st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Total</div><div class="knt-value">{total_tam:,.0f}</div></div>', unsafe_allow_html=True)
        else:
            cols_tam = st.columns(n_loan)
            for i, lt in enumerate(loan_types):
                with cols_tam[i]:
                    v = _loan_val(lt, "tam_cr")
                    val_str = f"{v:,.0f}" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--tam"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            with cols_tam[-1]:
                st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Total</div><div class="knt-value">{total_tam:,.0f}</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="key-numbers-row-spacer"></div>', unsafe_allow_html=True)

        # ----- Incidence Rate -----
        st.markdown('<p class="key-numbers-row-title key-numbers-row-title--ir">Incidence Rate</p>', unsafe_allow_html=True)
        if use_two_rows:
            # Row 1: first max_per_row loan types
            cols_ir_1 = st.columns(max_per_row)
            for i, lt in enumerate(loan_types[:max_per_row]):
                with cols_ir_1[i]:
                    v = _loan_val(lt, "new_incidence_rate")
                    val_str = f"{v*100:.2f}%" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--ir"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            # Row 2: remaining loan types + Total
            n_second = len(loan_types) - max_per_row + 1
            cols_ir_2 = st.columns(n_second)
            for i, lt in enumerate(loan_types[max_per_row:]):
                with cols_ir_2[i]:
                    v = _loan_val(lt, "new_incidence_rate")
                    val_str = f"{v*100:.2f}%" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--ir"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            with cols_ir_2[-1]:
                st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Total</div><div class="knt-value">{total_nir*100:.2f}%</div></div>', unsafe_allow_html=True)
        else:
            cols_ir = st.columns(n_loan)
            for i, lt in enumerate(loan_types):
                with cols_ir[i]:
                    v = _loan_val(lt, "new_incidence_rate")
                    val_str = f"{v*100:.2f}%" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--ir"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            with cols_ir[-1]:
                st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Total</div><div class="knt-value">{total_nir*100:.2f}%</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="key-numbers-row-spacer"></div>', unsafe_allow_html=True)

        # ----- Loan Amount per User (INR) -----
        st.markdown('<p class="key-numbers-row-title key-numbers-row-title--lapu">Loan Amount per User (INR)</p>', unsafe_allow_html=True)
        if use_two_rows:
            cols_lapu_1 = st.columns(max_per_row)
            for i, lt in enumerate(loan_types[:max_per_row]):
                with cols_lapu_1[i]:
                    v = _loan_val(lt, "loan_amt_per_user")
                    val_str = f"{(v*1e7):,.0f}" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--lapu"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            n_second = len(loan_types) - max_per_row + 1
            cols_lapu_2 = st.columns(n_second)
            for i, lt in enumerate(loan_types[max_per_row:]):
                with cols_lapu_2[i]:
                    v = _loan_val(lt, "loan_amt_per_user")
                    val_str = f"{(v*1e7):,.0f}" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--lapu"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            with cols_lapu_2[-1]:
                st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Total</div><div class="knt-value">{(total_lapu*1e7):,.0f}</div></div>', unsafe_allow_html=True)
        else:
            cols_lapu = st.columns(n_loan)
            for i, lt in enumerate(loan_types):
                with cols_lapu[i]:
                    v = _loan_val(lt, "loan_amt_per_user")
                    val_str = f"{(v*1e7):,.0f}" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--lapu"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            with cols_lapu[-1]:
                st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Total</div><div class="knt-value">{(total_lapu*1e7):,.0f}</div></div>', unsafe_allow_html=True)

        # ----- Average ticket size (INR, in Lakh) -----
        st.markdown('<div class="key-numbers-row-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<p class="key-numbers-row-title key-numbers-row-title--ats">Average ticket size (INR)</p>', unsafe_allow_html=True)
        if use_two_rows:
            cols_ats_1 = st.columns(max_per_row)
            for i, lt in enumerate(loan_types[:max_per_row]):
                with cols_ats_1[i]:
                    v = _loan_val(lt, "avg_ticket_size_inr")
                    val_str = f"{(v/1e5):.1f} Lakh" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--ats"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            n_second = len(loan_types) - max_per_row + 1
            cols_ats_2 = st.columns(n_second)
            for i, lt in enumerate(loan_types[max_per_row:]):
                with cols_ats_2[i]:
                    v = _loan_val(lt, "avg_ticket_size_inr")
                    val_str = f"{(v/1e5):.1f} Lakh" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--ats"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            with cols_ats_2[-1]:
                st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Total</div><div class="knt-value">{(total_avg_ticket/1e5):.1f} Lakh</div></div>', unsafe_allow_html=True)
        else:
            cols_ats = st.columns(n_loan)
            for i, lt in enumerate(loan_types):
                with cols_ats[i]:
                    v = _loan_val(lt, "avg_ticket_size_inr")
                    val_str = f"{(v/1e5):.1f} Lakh" if v is not None else "—"
                    st.markdown(f'<div class="key-number-product key-number-product--ats"><div class="knp-label">{lt}</div><div class="knp-value">{val_str}</div></div>', unsafe_allow_html=True)
            with cols_ats[-1]:
                st.markdown(f'<div class="key-number-total-blue"><div class="knt-label">Total</div><div class="knt-value">{(total_avg_ticket/1e5):.1f} Lakh</div></div>', unsafe_allow_html=True)

        st.caption("**Total** incidence rate, LAPU, average ticket size, TAM contribution, and overall TAM include all loan types in the data.")
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
                    color="_lapu_inr", color_continuous_scale=CHART_COLOR_SCALE,
                    text=chart_df["_lapu_inr"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else ""),
                )
                fig_lapu_h.update_traces(textposition="outside", textfont_size=11)
                fig_lapu_h.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), coloraxis_showscale=True, coloraxis_colorbar_title="INR")
                st.plotly_chart(fig_lapu_h, use_container_width=True, key="tam_lapu_segment")
            else:
                st.caption("No data for Loan Amount per User.")
        with c2:
            if not chart_df.empty:
                fig_nir_h = px.bar(
                    chart_df, x="_segment", y="new_incidence_rate",
                    title="Incidence Rate by segment",
                    labels=dict(_segment="Segment", new_incidence_rate="Incidence Rate"),
                    color="new_incidence_rate", color_continuous_scale=CHART_COLOR_SCALE,
                    text=chart_df["new_incidence_rate"].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else ""),
                )
                fig_nir_h.update_traces(textposition="outside", textfont_size=11)
                fig_nir_h.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis_tickformat=".1%", coloraxis_showscale=True, coloraxis_colorbar_tickformat=".1%", coloraxis_colorbar_title="Rate")
                st.plotly_chart(fig_nir_h, use_container_width=True, key="tam_nir_segment")
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
                color_continuous_scale=CHART_COLOR_SCALE,
            )
            # Use customdata + texttemplate so TAM size and % share show on each tile
            tam_cr_list = viz_df["tam_cr"].tolist()
            pct_list = viz_df["_tam_pct"].tolist()
            fig_treemap.data[0].customdata = list(zip(tam_cr_list, pct_list))
            fig_treemap.data[0].texttemplate = "%{label}<br>%{customdata[0]:.0f} Cr (%{customdata[1]:.1f}%)"
            fig_treemap.data[0].textposition = "middle center"
            fig_treemap.update_layout(margin=dict(t=40, b=20, l=20, r=20), coloraxis_colorbar_tickformat=".0f")
            st.plotly_chart(fig_treemap, use_container_width=True, key="tam_treemap")
        else:
            st.caption("No segment data to show other views.")

        # ----- Crosstab TAM (between two chosen dimensions) -----
        st.subheader("Crosstab TAM")
        agg_cross = aggregate_df(filtered_df, [ct_row, ct_col], mau, total_base_ref=view_base)
        if not agg_cross.empty:
            pivot_tam_cross = agg_cross.pivot(index=ct_row, columns=ct_col, values="tam_cr").fillna(0)
            fig_cross = px.imshow(
                pivot_tam_cross,
                title=f"TAM (Cr) — {_dim_label(ct_row)} × {_dim_label(ct_col)}",
                labels=dict(x=_dim_label(ct_col), y=_dim_label(ct_row), color="TAM (Cr)"),
                aspect="auto",
                color_continuous_scale=CHART_COLOR_SCALE,
            )
            fig_cross.update_layout(xaxis_tickangle=-45, margin=dict(b=100), coloraxis_colorbar_tickformat=".0f")
            st.plotly_chart(fig_cross, use_container_width=True, key="tam_cross")
            st.caption(f"Rows: {_dim_label(ct_row)}, Columns: {_dim_label(ct_col)}. Same filters and MAU as above.")
            # Table view of crosstab with conditional formatting (red = low, green = high)
            st.subheader(f"TAM (Cr) by {_dim_label(ct_row)} × {_dim_label(ct_col)} — table")
            display_pivot = pivot_tam_cross.copy()
            display_pivot.index.name = _dim_label(ct_row)
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
            html += f"<thead><tr><th style='border:1px solid #ccc; padding:6px; text-align:left; background:#f0f0f0;'>{_esc(_dim_label(ct_row))}</th>"
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
                title=f"Loan Amount per User (INR) — {_dim_label(lapu_row)} × {_dim_label(lapu_col)}",
                labels=dict(x=_dim_label(lapu_col), y=_dim_label(lapu_row), color="Loan Amt per User (INR)"),
                aspect="auto",
                color_continuous_scale=CHART_COLOR_SCALE,
            )
            fig_lapu.update_layout(xaxis_tickangle=-45, margin=dict(b=100))
            st.plotly_chart(fig_lapu, use_container_width=True, key="tam_lapu_ct")
            st.caption(f"Rows: {_dim_label(lapu_row)}, Columns: {_dim_label(lapu_col)}. Same filters and MAU as above.")
            st.subheader(f"Loan Amount per User (INR) by {_dim_label(lapu_row)} × {_dim_label(lapu_col)} — table")
            display_lapu = pivot_lapu.copy()
            display_lapu.index.name = _dim_label(lapu_row)
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
            html_l += f"<thead><tr><th style='border:1px solid #ccc; padding:6px; text-align:left; background:#f0f0f0;'>{_esc_lapu(_dim_label(lapu_row))}</th>"
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
                "avg_ticket_size_inr",
                "tam_cr",
            ]
        ].copy()
        display_df = display_df.rename(
            columns={
                "new_incidence_rate": "Incidence Rate",
                "loan_amt_per_user": "Loan Amount per User (INR)",
                "avg_ticket_size_inr": "Average ticket size (INR)",
                "tam_cr": "TAM (Cr)",
                "Vehicle Class": "Vehicle",
            }
        )
        # Formatted view for display (%, 2 decimals, commas)
        display_fmt = display_df.copy()
        display_fmt["Total base"] = display_fmt["Total base"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
        display_fmt["Incidence Rate"] = display_fmt["Incidence Rate"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
        display_fmt["Loan Amount per User (INR)"] = display_fmt["Loan Amount per User (INR)"].apply(lambda x: f"{(x * 1e7):,.0f}" if pd.notna(x) else "")
        display_fmt["Average ticket size (INR)"] = display_fmt["Average ticket size (INR)"].apply(lambda x: f"{(x/1e5):.1f}" if pd.notna(x) else "")
        display_fmt["TAM (Cr)"] = display_fmt["TAM (Cr)"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "")
        display_fmt["Count of loans opened"] = display_fmt["Count of loans opened"].apply(lambda x: f"{round(x):,}" if pd.notna(x) else "")
        display_fmt["Loan amount (INR Cr)"] = display_fmt["Loan amount (INR Cr)"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
        # Append Total row only when grouped (so we have multiple segments)
        if group_by:
            total_fmt = {col: "" for col in display_fmt.columns}
            for g in group_by:
                total_fmt[_dim_label(g) if g in DIMENSION_LABEL else g] = "Total"
            total_fmt["Total base"] = f"{int(total_base):,}"
            total_fmt["Count of loans opened"] = f"{total_loans:,.0f}"
            total_fmt["Loan amount (INR Cr)"] = f"{total_loan_amt:.2f}"
            total_fmt["Incidence Rate"] = f"{total_nir*100:.2f}%"
            total_fmt["Loan Amount per User (INR)"] = f"{(total_lapu * 1e7):,.0f}"
            total_fmt["Average ticket size (INR)"] = f"{(total_avg_ticket/1e5):.1f}"
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

elif view == "Segment Comparison":
    filtered_comp = apply_filters(raw_df, comp_vehicle, comp_credit, comp_loan, comp_ticket)
    if filtered_comp.empty:
        st.warning("No data after filters for this view.")

    st.subheader("Segment Comparison")
    st.caption("Compare one segment (left) vs another (right): Share of TAM (%), Incidence Rate, and Loan Amount per User (INR) by breakdown. MAU = " + f"{mau_comp:,}" + ".")
    if not filtered_comp.empty:
        if tam_comp_left and tam_comp_right:
            fl = filtered_comp[filtered_comp[tam_comp_segment_dim].astype(str).isin([str(x) for x in tam_comp_left])]
            fr = filtered_comp[filtered_comp[tam_comp_segment_dim].astype(str).isin([str(x) for x in tam_comp_right])]
            vb_left = view_total_base(fl)
            vb_right = view_total_base(fr)
            agg_left = aggregate_df(fl, [tam_comp_breakdown], mau_comp, total_base_ref=vb_left)
            agg_right = aggregate_df(fr, [tam_comp_breakdown], mau_comp, total_base_ref=vb_right)
            if tam_comp_breakdown == "Credit score":
                agg_left = sort_df_by_credit_score_ascending(agg_left, [tam_comp_breakdown])
                agg_right = sort_df_by_credit_score_ascending(agg_right, [tam_comp_breakdown])
            left_label = ", ".join(str(x) for x in tam_comp_left)
            right_label = ", ".join(str(x) for x in tam_comp_right)
            agg_left["_x"] = agg_left[tam_comp_breakdown].astype(str)
            agg_right["_x"] = agg_right[tam_comp_breakdown].astype(str)
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
            st.caption(f"Base size by {_dim_label(tam_comp_breakdown)} as % of that segment's total base (bars sum to 100% per side).")
            col_base_l, col_base_r = st.columns(2)
            with col_base_l:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{_dim_label(tam_comp_segment_dim)}:</span> {left_label}</div>', unsafe_allow_html=True)
                if not agg_left.empty:
                    tot_base_left = agg_left["Total base"].sum()
                    agg_left["_pct_base"] = (100 * agg_left["Total base"] / tot_base_left) if tot_base_left and tot_base_left != 0 else 0
                    agg_left["_base_txt"] = agg_left["_pct_base"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else "")
                    fig_base_l = px.bar(agg_left, x="_x", y="_pct_base", title=f"Base size (% of segment) by {_dim_label(tam_comp_breakdown)}", labels=dict(_x=_dim_label(tam_comp_breakdown), _pct_base="Share (%)"), color="_pct_base", color_continuous_scale=CHART_COLOR_SCALE, text="_base_txt")
                    fig_base_l.update_traces(textposition="outside", textfont_size=11)
                    fig_base_l.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis=dict(range=[0, 105], ticksuffix="%"), coloraxis_showscale=True)
                    st.plotly_chart(fig_base_l, use_container_width=True, key="tam_comp_base_l")
                else:
                    st.caption("No data.")
            with col_base_r:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{_dim_label(tam_comp_segment_dim)}:</span> {right_label}</div>', unsafe_allow_html=True)
                if not agg_right.empty:
                    tot_base_right = agg_right["Total base"].sum()
                    agg_right["_pct_base"] = (100 * agg_right["Total base"] / tot_base_right) if tot_base_right and tot_base_right != 0 else 0
                    agg_right["_base_txt"] = agg_right["_pct_base"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else "")
                    fig_base_r = px.bar(agg_right, x="_x", y="_pct_base", title=f"Base size (% of segment) by {_dim_label(tam_comp_breakdown)}", labels=dict(_x=_dim_label(tam_comp_breakdown), _pct_base="Share (%)"), color="_pct_base", color_continuous_scale=CHART_COLOR_SCALE, text="_base_txt")
                    fig_base_r.update_traces(textposition="outside", textfont_size=11)
                    fig_base_r.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis=dict(range=[0, 105], ticksuffix="%"), coloraxis_showscale=True)
                    st.plotly_chart(fig_base_r, use_container_width=True, key="tam_comp_base_r")

            # Share of TAM (%)
            tot_tam_l = agg_left["tam_cr"].sum()
            tot_tam_r = agg_right["tam_cr"].sum()
            agg_left = agg_left.copy()
            agg_right = agg_right.copy()
            agg_left["_pct_tam"] = (100 * agg_left["tam_cr"] / tot_tam_l) if tot_tam_l and tot_tam_l != 0 else 0
            agg_right["_pct_tam"] = (100 * agg_right["tam_cr"] / tot_tam_r) if tot_tam_r and tot_tam_r != 0 else 0

            st.subheader("Share of TAM (%)")
            st.caption(f"Share of segment TAM by {_dim_label(tam_comp_breakdown)}. Left: {left_label} | Right: {right_label}.")
            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{_dim_label(tam_comp_segment_dim)}:</span> {left_label}</div>', unsafe_allow_html=True)
                if agg_left.empty:
                    st.caption("No data.")
                else:
                    agg_left["_pct_txt"] = agg_left["_pct_tam"].apply(lambda v: f"{v:.0f}%" if pd.notna(v) else "")
                    fig_tam_l = px.bar(agg_left, x="_x", y="_pct_tam", title=f"Share of TAM (%) by {_dim_label(tam_comp_breakdown)}", labels=dict(_x=_dim_label(tam_comp_breakdown), _pct_tam="Share (%)"), color="_pct_tam", color_continuous_scale=CHART_COLOR_SCALE, text="_pct_txt")
                    fig_tam_l.update_traces(textposition="outside", textfont_size=11)
                    fig_tam_l.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis=dict(range=[0, 105], ticksuffix="%"), coloraxis_showscale=True)
                    st.plotly_chart(fig_tam_l, use_container_width=True, key="tam_comp_tam_l")
            with col_r:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{_dim_label(tam_comp_segment_dim)}:</span> {right_label}</div>', unsafe_allow_html=True)
                if agg_right.empty:
                    st.caption("No data.")
                else:
                    agg_right["_pct_txt"] = agg_right["_pct_tam"].apply(lambda v: f"{v:.0f}%" if pd.notna(v) else "")
                    fig_tam_r = px.bar(agg_right, x="_x", y="_pct_tam", title=f"Share of TAM (%) by {_dim_label(tam_comp_breakdown)}", labels=dict(_x=_dim_label(tam_comp_breakdown), _pct_tam="Share (%)"), color="_pct_tam", color_continuous_scale=CHART_COLOR_SCALE, text="_pct_txt")
                    fig_tam_r.update_traces(textposition="outside", textfont_size=11)
                    fig_tam_r.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis=dict(range=[0, 105], ticksuffix="%"), coloraxis_showscale=True)
                    st.plotly_chart(fig_tam_r, use_container_width=True, key="tam_comp_tam_r")

            st.subheader("Incidence Rate")
            st.caption(f"Incidence rate (loans ÷ base) by {_dim_label(tam_comp_breakdown)} for each segment. Can exceed 100% when users have multiple loans.")
            col_ir_l, col_ir_r = st.columns(2)
            with col_ir_l:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{_dim_label(tam_comp_segment_dim)}:</span> {left_label}</div>', unsafe_allow_html=True)
                if agg_left.empty:
                    st.caption("No data.")
                else:
                    agg_left["_y_ir"] = agg_left["new_incidence_rate"]
                    agg_left["_ir_txt"] = agg_left["_y_ir"].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else "")
                    fig_ir_l = px.bar(agg_left, x="_x", y="_y_ir", title=f"Incidence Rate by {_dim_label(tam_comp_breakdown)}", labels=dict(_x=_dim_label(tam_comp_breakdown), _y_ir="Incidence Rate"), color="_y_ir", color_continuous_scale=CHART_COLOR_SCALE, text="_ir_txt")
                    fig_ir_l.update_traces(textposition="outside", textfont_size=11)
                    fig_ir_l.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis_tickformat=".1%", coloraxis_colorbar_tickformat=".1%", coloraxis_showscale=True)
                    st.plotly_chart(fig_ir_l, use_container_width=True, key="tam_comp_ir_l")
            with col_ir_r:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{_dim_label(tam_comp_segment_dim)}:</span> {right_label}</div>', unsafe_allow_html=True)
                if agg_right.empty:
                    st.caption("No data.")
                else:
                    agg_right["_y_ir"] = agg_right["new_incidence_rate"]
                    agg_right["_ir_txt"] = agg_right["_y_ir"].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else "")
                    fig_ir_r = px.bar(agg_right, x="_x", y="_y_ir", title=f"Incidence Rate by {_dim_label(tam_comp_breakdown)}", labels=dict(_x=_dim_label(tam_comp_breakdown), _y_ir="Incidence Rate"), color="_y_ir", color_continuous_scale=CHART_COLOR_SCALE, text="_ir_txt")
                    fig_ir_r.update_traces(textposition="outside", textfont_size=11)
                    fig_ir_r.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), yaxis_tickformat=".1%", coloraxis_colorbar_tickformat=".1%", coloraxis_showscale=True)
                    st.plotly_chart(fig_ir_r, use_container_width=True, key="tam_comp_ir_r")

            st.subheader("Loan Amount per User (INR)")
            st.caption(
                "**Formula:** For each " + _dim_label(tam_comp_breakdown) + " bucket, **LAPU (INR) = (Total loan amount in Cr for that bucket ÷ Total base for that bucket) × 10⁷**. "
                "Total loan amount and total base are summed over the selected segment (e.g. " + left_label + "). "
                "Total base is aggregated with **first** per (Vehicle, Credit score), so when base is split across many rows (e.g. by Loan type/Ticket size), the denominator can be smaller than the full base and LAPU can look high. "
                "800+ or other buckets show 0 when there is no data for that bucket in the segment."
            )
            col_l2, col_r2 = st.columns(2)
            with col_l2:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{_dim_label(tam_comp_segment_dim)}:</span> {left_label}</div>', unsafe_allow_html=True)
                if agg_left.empty:
                    st.caption("No data.")
                else:
                    agg_left["_y_lapu"] = agg_left["loan_amt_per_user"] * 1e7
                    agg_left["_lapu_txt"] = agg_left["_y_lapu"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "")
                    fig_lapu_l = px.bar(agg_left, x="_x", y="_y_lapu", title=f"Loan Amount per User (INR) by {_dim_label(tam_comp_breakdown)}", labels=dict(_x=_dim_label(tam_comp_breakdown), _y_lapu="INR"), color="_y_lapu", color_continuous_scale=CHART_COLOR_SCALE, text="_lapu_txt")
                    fig_lapu_l.update_traces(textposition="outside", textfont_size=11)
                    fig_lapu_l.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), coloraxis_showscale=True)
                    st.plotly_chart(fig_lapu_l, use_container_width=True, key="tam_comp_lapu_l")
            with col_r2:
                st.markdown(f'<div style="{COMPARE_SEGMENT_PILL_STYLE}"><span style="font-size: 0.9rem;">{_dim_label(tam_comp_segment_dim)}:</span> {right_label}</div>', unsafe_allow_html=True)
                if agg_right.empty:
                    st.caption("No data.")
                else:
                    agg_right["_y_lapu"] = agg_right["loan_amt_per_user"] * 1e7
                    agg_right["_lapu_txt"] = agg_right["_y_lapu"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "")
                    fig_lapu_r = px.bar(agg_right, x="_x", y="_y_lapu", title=f"Loan Amount per User (INR) by {_dim_label(tam_comp_breakdown)}", labels=dict(_x=_dim_label(tam_comp_breakdown), _y_lapu="INR"), color="_y_lapu", color_continuous_scale=CHART_COLOR_SCALE, text="_lapu_txt")
                    fig_lapu_r.update_traces(textposition="outside", textfont_size=11)
                    fig_lapu_r.update_layout(showlegend=False, xaxis_tickangle=-45, margin=dict(b=100), coloraxis_showscale=True)
                    st.plotly_chart(fig_lapu_r, use_container_width=True, key="tam_comp_lapu_r")
        else:
            st.info("Choose at least one segment for **Left** and one for **Right** in the sidebar.")

else:
    filtered_base = apply_filters(raw_df, base_vehicle, base_credit, base_loan, base_ticket)

    st.subheader("Base data: segment splits")
    st.caption("Splits use this tab's filters only (independent of other tabs).")

    if filtered_base.empty:
        st.warning("No data after filters.")
    else:
        # Vehicle Class and Credit score pies side by side
        vc_split = base_split(filtered_base, "Vehicle Class")
        vc_split = vc_split.sort_values("Total base", ascending=False)
        cs_split = base_split(filtered_base, "Credit score")
        cs_split = sort_df_by_credit_score_ascending(cs_split, ["Credit score"])
        pie_col1, pie_col2 = st.columns(2)
        with pie_col1:
            st.markdown("#### Vehicle split")
            fig_vc_pie = px.pie(vc_split, values="Total base", names="Vehicle Class", title="Total base % by Vehicle",
                color_discrete_sequence=getattr(px.colors.qualitative, PIE_VEHICLE_CLASS))
            fig_vc_pie.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
            st.plotly_chart(fig_vc_pie, use_container_width=True, key="tam_base_vc_pie")
        with pie_col2:
            st.markdown("#### Credit score (CIBIL) split")
            fig_cs_pie = px.pie(cs_split, values="Total base", names="Credit score", title="Total base % by Credit score",
                color_discrete_sequence=getattr(px.colors.qualitative, PIE_CREDIT_SCORE))
            fig_cs_pie.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
            st.plotly_chart(fig_cs_pie, use_container_width=True, key="tam_base_cs_pie")

        # Ticket size split when a loan type is selected (pie only)
        if base_loan:
            st.divider()
            st.markdown("#### Ticket size split (selected loan type)")
            ts_split = base_split(filtered_base, "Ticket size")
            ts_split = ts_split.sort_values("Total base", ascending=False)
            fig_ts_pie = px.pie(ts_split, values="Total base", names="Ticket size", title="Total base % by Ticket size",
                color_discrete_sequence=getattr(px.colors.qualitative, PIE_TICKET_SIZE))
            fig_ts_pie.update_traces(textposition="inside", textinfo="percent+label", texttemplate="%{label}<br>%{percent:.1%}")
            st.plotly_chart(fig_ts_pie, use_container_width=True, key="tam_base_ts_pie")
        else:
            st.info("Select a **Loan type** in this tab's filters to see Ticket size % split.")
