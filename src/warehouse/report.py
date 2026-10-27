"""Turn warehouse tables into CSVs, charts, report.md / report.html, README.md and docs/DETAILS.md.

Every number written here is read from a table built in the same run.
"""
from __future__ import annotations

import html
import string
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

PCT = {"revenue_growth", "revenue_cagr_5y", "gross_margin", "operating_margin", "net_margin", "roe", "roa",
       "fcf_margin", "rd_intensity", "equity_to_assets", "efficiency_ratio", "nii_share_of_revenue",
       "deposits_to_assets", "change_pct", "max_abs_change_pct", "rel_diff"}
MULT = {"asset_turnover", "equity_multiplier", "debt_to_equity", "cash_conversion", "liabilities_to_equity",
        "abs_ratio"}
MONEY = {"revenue", "net_income", "total_assets", "shareholders_equity", "first_value", "latest_value", "change",
         "assets", "liabilities", "equity_used", "temporary_equity", "gap", "l_and_e", "revenues_tag",
         "asc606_tag", "prior_v", "v"}

EXPORTS = ["latest_fy_comparison", "sector_medians", "financials_scorecard", "coverage_latest_fy",
           "restatement_summary", "audit_restatements", "ratios_annual", "audit_universe", "mart_annual"]
# Explicit, unique sort keys so every exported CSV is byte-identical across reruns.
EXPORT_ORDER = {
    "latest_fy_comparison": "rank_roe nulls last, ticker",
    "sector_medians": "sector",
    "financials_scorecard": "ticker, fiscal_year",
    "coverage_latest_fy": "ticker",
    "restatement_summary": "restated_values desc, ticker",
    "audit_restatements": "ticker, concept_code, tag, period_type, period_start nulls first, period_end",
    "ratios_annual": "ticker, fiscal_year",
    "audit_universe": "ticker, cik nulls first",
    "mart_annual": "ticker, fiscal_year",
}


# ---------------------------------------------------------------- formatting
def fmt_cell(col: str, v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return "-"
    if col in PCT:
        return f"{v * 100:.1f}%"
    if col in MULT:
        return f"{v:.2f}x"
    if col in MONEY:
        return f"{v / 1e6:,.0f}"
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float):
        return f"{v:,.4g}"
    return str(v)


def fmt_frame(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({c: [fmt_cell(c, v) for v in df[c]] for c in df.columns})


def md_table(df: pd.DataFrame) -> str:
    f = fmt_frame(df)
    head = "| " + " | ".join(f.columns) + " |"
    sep = "| " + " | ".join("---" for _ in f.columns) + " |"
    rows = ["| " + " | ".join(str(x).replace("|", "/") for x in r) + " |" for r in f.itertuples(index=False)]
    return "\n".join([head, sep, *rows])


def html_table(df: pd.DataFrame) -> str:
    return fmt_frame(df).to_html(index=False, border=0, classes="t", escape=True)


def pct(v, d=1) -> str:
    return f"{v * 100:.{d}f}%"


# ---------------------------------------------------------------- charts
def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def chart_dupont(df: pd.DataFrame, path: Path) -> None:
    d = df[df["roe"].notna()].sort_values("roe")
    panels = [("roe", "Return on equity", PCT), ("net_margin", "Net margin", PCT),
              ("asset_turnover", "Asset turnover", MULT), ("equity_multiplier", "Equity multiplier", MULT)]
    fig, axes = plt.subplots(1, 4, figsize=(13, 0.32 * len(d) + 1.6), sharey=True)
    for ax, (col, title, kind) in zip(axes, panels):
        vals = d[col]
        ax.barh(d["ticker"], vals, color=BLUE, height=0.62)
        ax.axvline(0, color=INK_2, linewidth=0.8)
        span = vals.max() - min(vals.min(), 0)
        for y, v in enumerate(vals):
            label = pct(v, 0) if kind is PCT else f"{v:.1f}x"
            ax.text(v + (0.02 * span if v >= 0 else -0.02 * span), y, label, va="center",
                    ha="left" if v >= 0 else "right", fontsize=8, color=INK_2)
        ax.set_title(title, fontsize=10.5, color=INK, loc="left")
        ax.set_xlim(min(vals.min() * 1.9, 0), vals.max() * 1.3)
        ax.tick_params(axis="y", length=0, pad=6)
        ax.set_xticks([])
        _style(ax)
        ax.grid(False)
    fy = f"{int(d['fiscal_year'].min())}-{int(d['fiscal_year'].max())}"
    fig.suptitle(f"ROE = net margin x asset turnover x equity multiplier - latest fiscal year ({fy}), "
                 f"{len(d)} non-financial MA companies", x=0.01, ha="left", fontsize=11.5, color=INK)
    fig.text(0.01, 0.005, "Source: SEC EDGAR XBRL companyfacts. Averages of opening and closing balances. "
             "Wayfair omitted (negative equity).", fontsize=8, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_growth_margin(df: pd.DataFrame, path: Path) -> list[str]:
    d = df[df["operating_margin"].notna() & df["revenue_growth"].notna()]
    lo, hi = -0.25, 0.55
    fig, ax = plt.subplots(figsize=(8.5, 6))
    off = []
    for _, r in d.iterrows():
        y = min(max(r["operating_margin"], lo + 0.01), hi - 0.01)
        clipped = y != r["operating_margin"]
        ax.scatter(r["revenue_growth"], y, s=46, color=BLUE, edgecolor="white", linewidth=1.5, zorder=3,
                   marker="v" if clipped else "o")
        label = r["ticker"] + (f" (op. margin {pct(r['operating_margin'], 0)}, off scale)" if clipped else "")
        if clipped:
            off.append(r["ticker"])
        ax.annotate(label, (r["revenue_growth"], y), xytext=(5, 4), textcoords="offset points",
                    fontsize=8.5, color=INK)
    ax.axhline(0, color=INK_2, linewidth=0.8)
    ax.axvline(0, color=INK_2, linewidth=0.8)
    ax.set_ylim(lo, hi)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Revenue growth, latest fiscal year vs prior", color=INK_2, fontsize=9.5)
    ax.set_ylabel("Operating margin", color=INK_2, fontsize=9.5)
    ax.set_title("Growth vs profitability, latest fiscal year (non-financials reporting operating income)",
                 fontsize=11, color=INK, loc="left")
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    fig.text(0.01, 0.005, "Source: SEC EDGAR XBRL companyfacts.", fontsize=8, color=INK_2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return off


def chart_restatements(df: pd.DataFrame, path: Path, years: str) -> None:
    d = df.copy()
    d["minor"] = d["restated_values"] - d["material"]
    d = d.sort_values("restated_values")
    fig, ax = plt.subplots(figsize=(8.5, 0.3 * len(d) + 1.5))
    ax.barh(d["ticker"], d["material"], color=BLUE, height=0.62, label="Material (changed >= 0.5%)")
    ax.barh(d["ticker"], d["minor"], left=d["material"], color=ORANGE, height=0.62,
            edgecolor="white", linewidth=2, label="Minor (< 0.5%)")
    for y, (m, t) in enumerate(zip(d["material"], d["restated_values"])):
        ax.text(t + 2, y, f"{t}", va="center", fontsize=8, color=INK_2)
    ax.set_title("Reported values that changed after first filing, by company", fontsize=11, color=INK, loc="left")
    ax.set_xlabel("Distinct (line-item tag, period) values with more than one reported number", color=INK_2,
                  fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    _style(ax)
    fig.text(0.01, 0.005, f"Source: audit_restatements table (filings {years}, mapped tags only).",
             fontsize=8, color=INK_2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- report
def q(con, sql: str) -> pd.DataFrame:
    return con.sql(sql).df()


def build_report(con, results, manifest: dict, stats: dict, out: Path, root: Path) -> dict:
    tables_dir, charts_dir = out / "tables", out / "charts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)
    for t in EXPORTS:
        q(con, f"select * from {t} order by {EXPORT_ORDER[t]}").to_csv(tables_dir / f"{t}.csv", index=False)

    latest = q(con, f"select * from latest_fy_comparison order by {EXPORT_ORDER['latest_fy_comparison']}")
    sectors = q(con, f"select * from sector_medians order by {EXPORT_ORDER['sector_medians']}")
    fin = q(con, f"select * from financials_scorecard order by {EXPORT_ORDER['financials_scorecard']}")
    cov = q(con, f"select * from coverage_latest_fy order by {EXPORT_ORDER['coverage_latest_fy']}")
    rest = q(con, f"select * from restatement_summary order by {EXPORT_ORDER['restatement_summary']}")
    universe = q(con, "select ticker, sector, industry_group, cik, entity_name, hq_city, hq_state, "
                      "exclusion_reason from audit_universe order by exclusion_reason nulls first, ticker")
    company = q(con, "select ticker, entity_name, sector, industry_group, company_type, sic, hq_city "
                     "from dim_company order by sector, ticker")
    example_sql = (root / "sql" / "examples" / "dupont_top5.sql").read_text()
    example_out = q(con, example_sql)

    chart_dupont(latest, charts_dir / "dupont_roe.png")
    off_scale = chart_growth_margin(latest, charts_dir / "growth_vs_margin.png")
    yrs = q(con, "select min(year(first_filed)) a, max(year(latest_filed)) b from audit_restatements").iloc[0]
    chart_restatements(rest, charts_dir / "restatements_by_company.png", f"{int(yrs['a'])}-{int(yrs['b'])}")

    counts = q(con, """
        select
          (select count(*) from dim_company)                                   as companies,
          (select count(*) from dim_company where company_type in ('bank','insurer')) as financials,
          (select count(*) from fact_financials)                               as fact_rows,
          (select count(*) from fact_financials where is_restated)             as fact_rows_restated,
          (select count(*) from dim_period)                                    as periods,
          (select count(*) from map_xbrl_tag)                                  as tags_mapped,
          (select count(*) from dim_concept)                                   as concepts,
          (select count(*) from mart_annual)                                   as company_years,
          (select min(fiscal_year) from mart_annual)                           as first_fy,
          (select count(*) from audit_restatements)                            as restated_values,
          (select count(*) from audit_restatements where materiality like 'material%') as restated_material,
          (select count(*) from audit_restatements where restatement_source = 'amended filing') as via_amend,
          (select count(*) from stg_facts)                                     as stg_rows
    """).iloc[0].to_dict()

    # ------------------------------------------------ headline facts (all from latest_fy_comparison)
    roe_rank = latest[latest["roe"].notna()].sort_values("roe", ascending=False).reset_index(drop=True)
    top1, top2 = roe_rank.iloc[0], roe_rank.iloc[1]
    best_margin = latest.loc[latest["net_margin"].idxmax()]
    n_nonfin = len(latest)
    headline = {
        "top_roe": {k: top1[k] for k in ("ticker", "roe", "net_margin", "asset_turnover", "equity_multiplier")},
        "second_roe": {k: top2[k] for k in ("ticker", "roe", "net_margin", "asset_turnover", "equity_multiplier")},
        "best_net_margin": {k: best_margin[k] for k in ("ticker", "roe", "net_margin", "asset_turnover",
                                                        "equity_multiplier")},
        "non_financials": n_nonfin,
        "median_roe_nonfin": float(latest["roe"].median()),
    }

    dq = pd.DataFrame([{"check": r.name, "severity": r.severity, "status": r.status,
                        "violating_rows": r.violations,
                        "rows_tested": "-" if r.population is None else f"{r.population:,}"} for r in results])
    n_checks = len(results)
    n_pass = sum(r.status == "PASS" for r in results)
    n_fail = sum(r.status == "FAIL" for r in results)
    n_warn = sum(r.status == "WARN" for r in results)
    by_id = {r.check_id: r for r in results}

    def tickers(check_id: str) -> str:
        r = by_id.get(check_id)
        if r is None or r.violations == 0 or "ticker" not in r.sample:
            return "none"
        vc = r.sample["ticker"].value_counts()
        return ", ".join(f"{t} ({n})" for t, n in vc.items())

    run_date = date.today().isoformat()
    s = {
        "run_date": run_date,
        "companies": int(counts["companies"]),
        "financials": int(counts["financials"]),
        "non_financials": n_nonfin,
        "excluded": ", ".join(f"{r.ticker} ({r.exclusion_reason})" for r in universe.itertuples()
                              if isinstance(r.exclusion_reason, str)),
        "raw_rows": f"{stats['raw_fact_rows']:,}",
        "stg_rows": f"{int(counts['stg_rows']):,}",
        "fact_rows": f"{int(counts['fact_rows']):,}",
        "fact_rows_restated": f"{int(counts['fact_rows_restated']):,}",
        "fact_restated_pct": pct(counts["fact_rows_restated"] / counts["fact_rows"]),
        "periods": f"{int(counts['periods']):,}",
        "tags_mapped": int(counts["tags_mapped"]),
        "concepts": int(counts["concepts"]),
        "company_years": int(counts["company_years"]),
        "first_fy": int(counts["first_fy"]),
        "restated_values": f"{int(counts['restated_values']):,}",
        "restated_material": f"{int(counts['restated_material']):,}",
        "via_amend": int(counts["via_amend"]),
        "requests": manifest["requests_made"],
        "raw_mb": f"{sum(f['bytes'] for f in manifest['files']) / 1e6:.0f}",
        "t1": top1["ticker"], "t1_roe": pct(top1["roe"], 0), "t1_nm": pct(top1["net_margin"]),
        "t1_at": f"{top1['asset_turnover']:.2f}", "t1_em": f"{top1['equity_multiplier']:.1f}",
        "t2": top2["ticker"], "t2_roe": pct(top2["roe"], 0), "t2_nm": pct(top2["net_margin"]),
        "t2_at": f"{top2['asset_turnover']:.2f}", "t2_em": f"{top2['equity_multiplier']:.1f}",
        "bm": best_margin["ticker"], "bm_nm": pct(best_margin["net_margin"]), "bm_roe": pct(best_margin["roe"], 0),
        "bm_at": f"{best_margin['asset_turnover']:.2f}", "bm_em": f"{best_margin['equity_multiplier']:.2f}",
        "median_roe": pct(headline["median_roe_nonfin"]),
        "n_checks": n_checks, "n_pass": n_pass, "n_fail": n_fail, "n_warn": n_warn,
        "dq_table": md_table(dq),
        "c07_n": by_id["07_assets_eq_l_and_e"].violations, "c07_pop": f"{by_id['07_assets_eq_l_and_e'].population:,}",
        "c07_t": tickers("07_assets_eq_l_and_e"),
        "c08_n": by_id["08_balance_sheet_identity"].violations,
        "c08_pop": f"{by_id['08_balance_sheet_identity'].population:,}",
        "c08_t": tickers("08_balance_sheet_identity"),
        "c10_n": by_id["10_yoy_jump_5x"].violations, "c10_pop": f"{by_id['10_yoy_jump_5x'].population:,}",
        "c10_items": ", ".join(f"{n} {item}" for item, n in
                               by_id["10_yoy_jump_5x"].sample["item"].value_counts().items()),
        "c10_rev": ", ".join(f"{r.ticker} {r.fiscal_year} ({r.abs_ratio:g}x)" for r in
                             by_id["10_yoy_jump_5x"].sample.query("item == 'revenue'").itertuples()) or "none",
        "c11_n": by_id["11_fiscal_year_label"].violations, "c11_t": tickers("11_fiscal_year_label"),
        "c12_n": by_id["12_revenue_tag_disagreement"].violations, "c12_t": tickers("12_revenue_tag_disagreement"),
        "c14_n": by_id["14_core_coverage_latest_fy"].violations,
        "c14_list": "; ".join(f"{r.ticker}: {r.missing_item}" for r in
                              by_id["14_core_coverage_latest_fy"].sample.itertuples()) or "none",
        "example_sql": example_sql.strip(),
        "off_scale": ", ".join(off_scale) or "none",
        "liab_derived": ", ".join(q(con, """select ticker from mart_annual m where liabilities_source like 'derived%'
            and fiscal_year = (select max(fiscal_year) from mart_annual x where x.cik = m.cik) order by 1""")["ticker"]),
        "no_debt": ", ".join(latest[latest["debt_to_equity"].isna()]["ticker"]),
        "neg_equity": ", ".join(latest[latest["roe"].isna()]["ticker"]),
    }
    # example output: show raw decimals exactly as the query returns them
    s["example_out"] = raw_md_table(example_out)

    write_markdown_report(out / "report.md", s, latest, sectors, fin, cov, rest, universe, company, dq, by_id, con)
    write_html_report(out / "report.html", s, latest, sectors, fin, cov, rest, universe, dq, by_id)

    s["n_tests"] = sum(f.read_text().count("\ndef test_") for f in (root / "tests").glob("test_*.py"))
    reqs = [line.split("==") for line in (root / "requirements.txt").read_text().split()
            if "==" in line]
    s["stack"] = " · ".join(f"{name} {ver}" for name, ver in reqs)
    s.update({f"ver_{name.replace('-', '_')}": ver for name, ver in reqs})

    # long write-up -> docs/DETAILS.md, short visual summary -> README.md
    (root / "docs").mkdir(exist_ok=True)
    details = string.Template((root / "templates" / "DETAILS.md.tmpl").read_text())
    (root / "docs" / "DETAILS.md").write_text(details.substitute(s))
    readme = string.Template((root / "templates" / "README.md.tmpl").read_text())
    (root / "README.md").write_text(readme.substitute(s))
    return {"headline": headline, "summary": s}


def raw_md_table(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = ["| " + " | ".join(str(x) for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *rows])


LATEST_COLS = ["rank_roe", "ticker", "sector", "fiscal_year", "period_end", "revenue", "revenue_growth",
               "revenue_cagr_5y", "gross_margin", "operating_margin", "net_margin", "roe", "fcf_margin",
               "cash_conversion", "debt_to_equity", "rank_operating_margin", "rank_revenue_growth", "rank_fcf_margin"]
DUPONT_COLS = ["ticker", "roe", "net_margin", "asset_turnover", "equity_multiplier"]


def write_markdown_report(path, s, latest, sectors, fin, cov, rest, universe, company, dq, by_id, con) -> None:
    top_restate = con.sql("""
        select ticker, concept_code, tag, period_end, first_filed, first_value, latest_filed, latest_value, change_pct
        from audit_restatements
        where feeds_fact_table and materiality like 'material%' and first_value <> 0
          and concept_code in ('revenue', 'net_income', 'total_assets', 'operating_cash_flow')
          and (period_type = 'instant' or date_diff('day', period_start, period_end) between 350 and 380)
        qualify row_number() over (order by abs(change_pct) desc, ticker, concept_code, tag, period_end) <= 12
        order by abs(change_pct) desc, ticker, concept_code, tag, period_end
    """).df()
    lines = [
        "# Massachusetts public-company fundamentals - warehouse report",
        "",
        f"Generated {s['run_date']} by `python run.py` from SEC EDGAR XBRL data. "
        f"{s['companies']} companies, {s['company_years']} company-years (fiscal {s['first_fy']} onward), "
        f"{s['fact_rows']} rows in `fact_financials`. Money columns are USD millions.",
        "",
        "## Universe",
        "",
        md_table(company),
        "",
        "Seed tickers that were excluded, and why:",
        "",
        md_table(universe[universe["exclusion_reason"].notna()][["ticker", "entity_name", "exclusion_reason"]]),
        "",
        "## Latest fiscal year - ranked comparison (non-financials)",
        "",
        "Ranks are within the non-financial group; `-` means the line item is not reported or the ratio is "
        "not meaningful (e.g. ROE with negative equity).",
        "",
        md_table(latest[LATEST_COLS]),
        "",
        "![DuPont](charts/dupont_roe.png)",
        "",
        "## DuPont decomposition (latest fiscal year)",
        "",
        md_table(latest[latest["roe"].notna()][DUPONT_COLS]),
        "",
        "## Sector medians (latest fiscal year)",
        "",
        md_table(sectors),
        "",
        "![Growth vs margin](charts/growth_vs_margin.png)",
        "",
        "## Banks and insurer (separate treatment)",
        "",
        "Revenue for banks = net interest income + noninterest income. Gross/operating margin, FCF, cash "
        "conversion, debt/equity and asset turnover are not computed for financials.",
        "",
        md_table(fin),
        "",
        "## Data quality",
        "",
        f"{s['n_checks']} checks: {s['n_pass']} pass, {s['n_fail']} fail (error severity), "
        f"{s['n_warn']} warn. Violating rows for each check are in `output/dq_violations/`.",
        "",
        md_table(dq),
        "",
    ]
    for cid in ("07_assets_eq_l_and_e", "08_balance_sheet_identity", "12_revenue_tag_disagreement",
                "13_gross_profit_consistency", "14_core_coverage_latest_fy"):
        r = by_id[cid]
        if r.violations:
            lines += [f"### {r.name} - {r.violations} rows", "", md_table(r.sample.head(30)), ""]
    lines += [
        "## Restatements",
        "",
        f"{s['restated_values']} (company, tag, period) values changed after first filing; "
        f"{s['restated_material']} by 0.5% or more. {s['fact_rows_restated']} of {s['fact_rows']} fact rows "
        f"({s['fact_restated_pct']}) come from a tag-period whose value was revised at least once.",
        "",
        md_table(rest),
        "",
        "Largest material changes to annual revenue, net income, total assets or operating cash flow "
        "that feed the fact table:",
        "",
        md_table(top_restate),
        "",
        "![Restatements](charts/restatements_by_company.png)",
        "",
        "## Coverage - latest fiscal year (1 = available)",
        "",
        md_table(cov),
        "",
    ]
    path.write_text("\n".join(lines))


CSS = """
:root{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--rule:#e4e3df}
@media (prefers-color-scheme:dark){:root{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--rule:#3a3936}}
body{background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;
max-width:1180px;margin:0 auto;padding:24px 16px}
h1{font-size:24px}h2{font-size:18px;margin-top:36px;border-bottom:1px solid var(--rule);padding-bottom:4px}
h3{font-size:15px}p{color:var(--ink2)}.wrap{overflow-x:auto}
table.t{border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums;margin:8px 0}
table.t th,table.t td{padding:4px 10px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
table.t th{color:var(--ink2);font-weight:600}
table.t td:first-child,table.t th:first-child,table.t td:nth-child(2){text-align:left}
img{max-width:100%;background:#fff;border-radius:4px}
"""


def write_html_report(path, s, latest, sectors, fin, cov, rest, universe, dq, by_id) -> None:
    def sec(title, *parts):
        return f"<h2>{html.escape(title)}</h2>" + "".join(parts)

    def p(t):
        return f"<p>{html.escape(t)}</p>"

    def tbl(df):
        return f'<div class="wrap">{html_table(df)}</div>'

    body = [
        "<h1>Massachusetts public-company fundamentals</h1>",
        p(f"Generated {s['run_date']} by python run.py from SEC EDGAR XBRL data. {s['companies']} companies, "
          f"{s['company_years']} company-years, {s['fact_rows']} fact rows. Money columns are USD millions."),
        sec("Latest fiscal year - ranked comparison (non-financials)", tbl(latest[LATEST_COLS]),
            '<img src="charts/dupont_roe.png" alt="DuPont decomposition of ROE by company">'),
        sec("Sector medians", tbl(sectors),
            '<img src="charts/growth_vs_margin.png" alt="Revenue growth vs operating margin scatter">'),
        sec("Banks and insurer", p("Revenue for banks = net interest income + noninterest income."), tbl(fin)),
        sec("Data quality", p(f"{s['n_checks']} checks: {s['n_pass']} pass, {s['n_fail']} fail, "
                              f"{s['n_warn']} warn."), tbl(dq)),
    ]
    for cid in ("07_assets_eq_l_and_e", "08_balance_sheet_identity"):
        r = by_id[cid]
        if r.violations:
            body.append(f"<h3>{html.escape(r.name)} - {r.violations} rows</h3>" + tbl(r.sample.head(30)))
    body += [
        sec("Restatements", p(f"{s['restated_values']} values changed after first filing; "
                              f"{s['restated_material']} by 0.5% or more."), tbl(rest),
            '<img src="charts/restatements_by_company.png" alt="Restated values by company">'),
        sec("Coverage - latest fiscal year", tbl(cov)),
        sec("Universe", tbl(universe)),
    ]
    path.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                    f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
                    f"<title>MA Fundamentals Report</title><style>{CSS}</style></head><body>"
                    + "".join(body) + "</body></html>")
