"""
Export key dashboard numbers to JSON for static GitHub Pages.
Run from project root: python export_dashboard_data.py
Writes docs/dashboard_data.json (no backend; frontend loads this file).
"""

import json
import os
import sys

try:
    import pandas as pd
except ImportError:
    print("Run: pip install pandas openpyxl", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Organic: same logic as organic_dashboard.py
# ---------------------------------------------------------------------------
EXCEL_PATH = "organic_base.xlsx"
BASE_LEVEL_DIMS = ["Vehicle Class", "Credit score"]
AGG_DICT = {"Total base": "first", "Count of loans opened": "sum", "Loan amount (INR Cr)": "sum"}
NUMERIC_AGG_COLS = ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]


def load_organic(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    df.columns = df.columns.astype(str).str.strip()
    rename = {
        "vehicle_class": "Vehicle Class", "Vehicle Class": "Vehicle Class",
        "score_band": "Credit score", "Credit score": "Credit score",
        "loan_type": "Loan type", "Loan type": "Loan type",
        "ticket_bucket": "Ticket size", "Ticket size": "Ticket size",
        "base_size_scrub": "Total base", "Total base": "Total base", "Total Base": "Total base",
        "avg_loans_opened": "Count of loans opened", "Count of loans opened": "Count of loans opened",
        "avg_amount_inr_cr": "Loan amount (INR Cr)", "Loan amount (INR Cr)": "Loan amount (INR Cr)",
        "Loan Amount (INR Cr)": "Loan amount (INR Cr)",
        "source": "Source", "Source": "Source",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    required = ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns: {missing}. Available: {list(df.columns)}")
    return df.dropna(subset=required)


def compute_derived_organic(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    base = out["Total base"].replace(0, pd.NA)
    out["new_incidence_rate"] = (out["Count of loans opened"] / base).fillna(0)
    out["loan_amt_per_user"] = (out["Loan amount (INR Cr)"] / base).fillna(0)
    return out


def aggregate_organic(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    if not group_cols:
        step1 = df.groupby(BASE_LEVEL_DIMS, dropna=False).agg(AGG_DICT).reset_index()
        step2 = step1[NUMERIC_AGG_COLS].sum().to_frame().T
        return compute_derived_organic(step2)
    extra = [d for d in BASE_LEVEL_DIMS if d not in group_cols]
    by_cols = group_cols + extra
    step1 = df.groupby(by_cols, dropna=False).agg(AGG_DICT).reset_index()
    step2 = step1.groupby(group_cols, dropna=False)[NUMERIC_AGG_COLS].sum().reset_index()
    return compute_derived_organic(step2)


def view_total_base_organic(df: pd.DataFrame) -> float:
    step = df.groupby(BASE_LEVEL_DIMS, dropna=False).agg(AGG_DICT).reset_index()
    return float(step["Total base"].sum())


def build_organic_payload(df: pd.DataFrame) -> dict:
    total_base = view_total_base_organic(df)
    agg_all = aggregate_organic(df, ["Vehicle Class", "Loan type"])
    total_loans = agg_all["Count of loans opened"].sum()
    total_loan_amt = agg_all["Loan amount (INR Cr)"].sum()
    total_nir = (total_loans / total_base) if total_base and total_base != 0 else 0
    total_lapu = (total_loan_amt / total_base) if total_base and total_base != 0 else 0

    agg_by_loan = aggregate_organic(df, ["Loan type"])

    def _loan_val(lt: str, col: str):
        r = agg_by_loan[agg_by_loan["Loan type"].astype(str).str.upper() == lt.upper()]
        return float(r[col].iloc[0]) if len(r) else None

    # Top segments for chart (Vehicle Class | Loan type)
    agg_segments = aggregate_organic(df, ["Vehicle Class", "Loan type"])
    agg_segments["_segment"] = agg_segments["Vehicle Class"].astype(str) + " | " + agg_segments["Loan type"].astype(str)
    agg_segments = agg_segments.sort_values("new_incidence_rate", ascending=False).head(15)

    return {
        "organic": {
            "incidence_rate": {
                "PL": round((_loan_val("PL", "new_incidence_rate") or 0) * 100, 2),
                "GL": round((_loan_val("GL", "new_incidence_rate") or 0) * 100, 2),
                "BL": round((_loan_val("BL", "new_incidence_rate") or 0) * 100, 2),
                "total_pct": round(total_nir * 100, 2),
            },
            "loan_amount_per_user_inr": {
                "PL": round((_loan_val("PL", "loan_amt_per_user") or 0) * 1e7, 0),
                "GL": round((_loan_val("GL", "loan_amt_per_user") or 0) * 1e7, 0),
                "BL": round((_loan_val("BL", "loan_amt_per_user") or 0) * 1e7, 0),
                "total": round(total_lapu * 1e7, 0),
            },
            "total_base": round(total_base, 0),
            "segments": [
                {
                    "segment": row["_segment"],
                    "incidence_rate_pct": round(row["new_incidence_rate"] * 100, 1),
                    "loan_amount_per_user_inr": round(row["loan_amt_per_user"] * 1e7, 0),
                }
                for _, row in agg_segments.iterrows()
            ],
        }
    }


# ---------------------------------------------------------------------------
# TAM: minimal load + aggregate for MAU/TAM and key numbers
# ---------------------------------------------------------------------------
CSV_PATH = "TAM Cash Final - Base inorganic.csv"
DEFAULT_MAU = 2_000_000


def load_tam(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    rename = {
        "vehicle_class": "Vehicle Class", "score_band": "Credit score",
        "loan_type": "Loan type", "ticket_bucket": "Ticket size",
        "base_size_scrub": "Total base", "avg_loans_opened": "Count of loans opened",
        "avg_amount_inr_cr": "Loan amount (INR Cr)",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["Total base", "Count of loans opened", "Loan amount (INR Cr)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Total base", "Count of loans opened", "Loan amount (INR Cr)"])


def compute_derived_tam(df: pd.DataFrame, mau: float, total_base_ref: float) -> pd.DataFrame:
    out = df.copy()
    base = out["Total base"].replace(0, pd.NA)
    out["new_incidence_rate"] = (out["Count of loans opened"] / base).fillna(0)
    out["loan_amt_per_user"] = (out["Loan amount (INR Cr)"] / base).fillna(0)
    if total_base_ref and total_base_ref != 0:
        out["tam_cr"] = (mau * out["Loan amount (INR Cr)"] / total_base_ref).fillna(0)
    else:
        out["tam_cr"] = mau * out["loan_amt_per_user"]
    return out


def aggregate_tam(df: pd.DataFrame, group_cols: list, mau: float, total_base_ref: float) -> pd.DataFrame:
    if not group_cols:
        step1 = df.groupby(BASE_LEVEL_DIMS, dropna=False).agg(AGG_DICT).reset_index()
        step2 = step1[NUMERIC_AGG_COLS].sum().to_frame().T
        ref = total_base_ref if total_base_ref else float(step2["Total base"].iloc[0])
        return compute_derived_tam(step2, mau, ref)
    extra = [d for d in BASE_LEVEL_DIMS if d not in group_cols]
    by_cols = group_cols + extra
    step1 = df.groupby(by_cols, dropna=False).agg(AGG_DICT).reset_index()
    step2 = step1.groupby(group_cols, dropna=False)[NUMERIC_AGG_COLS].sum().reset_index()
    ref = total_base_ref if total_base_ref else step2["Total base"].sum()
    return compute_derived_tam(step2, mau, ref)


def view_total_base_tam(df: pd.DataFrame) -> float:
    step = df.groupby(BASE_LEVEL_DIMS, dropna=False).agg(AGG_DICT).reset_index()
    return float(step["Total base"].sum())


def build_tam_payload(df: pd.DataFrame, mau: float = DEFAULT_MAU) -> dict:
    total_base = view_total_base_tam(df)
    agg_by_loan = aggregate_tam(df, ["Loan type"], mau, total_base)
    agg_all = aggregate_tam(df, ["Vehicle Class", "Loan type"], mau, total_base)
    total_loans = agg_all["Count of loans opened"].sum()
    total_loan_amt = agg_all["Loan amount (INR Cr)"].sum()
    total_nir = (total_loans / total_base) if total_base and total_base != 0 else 0
    total_lapu = (total_loan_amt / total_base) if total_base and total_base != 0 else 0
    total_tam = float(agg_all["tam_cr"].sum())

    def _loan_val(lt: str, col: str):
        r = agg_by_loan[agg_by_loan["Loan type"].astype(str).str.upper() == lt.upper()]
        return float(r[col].iloc[0]) if len(r) else None

    return {
        "tam": {
            "mau": mau,
            "tam_cr": round(total_tam, 0),
            "total_base": round(total_base, 0),
            "incidence_rate": {
                "PL": round((_loan_val("PL", "new_incidence_rate") or 0) * 100, 2),
                "GL": round((_loan_val("GL", "new_incidence_rate") or 0) * 100, 2),
                "BL": round((_loan_val("BL", "new_incidence_rate") or 0) * 100, 2),
                "total_pct": round(total_nir * 100, 2),
            },
            "loan_amount_per_user_inr": {
                "PL": round((_loan_val("PL", "loan_amt_per_user") or 0) * 1e7, 0),
                "GL": round((_loan_val("GL", "loan_amt_per_user") or 0) * 1e7, 0),
                "BL": round((_loan_val("BL", "loan_amt_per_user") or 0) * 1e7, 0),
                "total": round(total_lapu * 1e7, 0),
            },
        }
    }


# ---------------------------------------------------------------------------
# Main: write docs/dashboard_data.json
# ---------------------------------------------------------------------------
def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    out = {"updated": pd.Timestamp.now().isoformat()}

    if os.path.isfile(EXCEL_PATH):
        df_organic = load_organic(EXCEL_PATH)
        out.update(build_organic_payload(df_organic))
    else:
        out["organic"] = {"error": f"File not found: {EXCEL_PATH}"}

    if os.path.isfile(CSV_PATH):
        df_tam = load_tam(CSV_PATH)
        out.update(build_tam_payload(df_tam))
    else:
        out["tam"] = {"error": f"File not found: {CSV_PATH}"}

    os.makedirs("docs", exist_ok=True)
    out_path = os.path.join("docs", "dashboard_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
