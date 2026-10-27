"""Tests for tag mapping, dedupe, restatement audit and fiscal calendar.

They run the real SQL in sql/ against a tiny hand-built set of facts in an in-memory DuckDB,
with the real seeds/concepts.csv, tag_map.csv and tag_overrides.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from warehouse import build, checks, load  # noqa: E402

ACME, BANKCO, TEXCO, OFFPRICE, BSX = 1, 2, 3, 4, 5

COMPANIES = pd.DataFrame([
    # cik, name, tickers, exchanges, sic, sic_description, city, state, fye
    (ACME, "Acme Corp", "ACME", "NYSE", 3841, "Devices", "BOSTON", "MA", "1231"),
    (BANKCO, "Bank Co", "BNK", "NYSE", 6022, "State Commercial Banks", "BOSTON", "MA", "1231"),
    (TEXCO, "Tex Co", "TEX", "NYSE", 2080, "Beverages", "FRISCO", "TX", "1231"),
    (OFFPRICE, "Off Price Inc", "OFF", "NYSE", 5651, "Retail", "FRAMINGHAM", "MA", "0201"),
    (BSX, "Boston Scientific", "BSX", "NYSE", 3841, "Devices", "MARLBOROUGH", "MA", "1231"),
], columns=["cik", "entity_name", "tickers", "exchanges", "sic", "sic_description", "hq_city", "hq_state",
            "fiscal_year_end_mmdd"])

SEED_COMPANIES = pd.DataFrame([
    ("ACME", "Health Care", "Devices"), ("BNK", "Financials", "Bank"), ("TEX", "Consumer", "Beverages"),
    ("OFF", "Consumer", "Retail"), ("BSX", "Health Care", "Devices"), ("GONE", "Technology", "Hardware"),
], columns=["ticker", "sector", "industry_group"])


def fact(cik, tag, start, end, val, accn, fy, form, filed, fp="FY"):
    return (cik, "us-gaap", tag, "USD", start, end, float(val), accn, fy, fp, form, filed, None)


FY23 = ("2023-01-01", "2023-12-31")
FY24 = ("2024-01-01", "2024-12-31")

FACTS = [
    # --- ACME: tag variants + restatement --------------------------------------------------
    # FY2023 revenue: both Revenues and the ASC 606 tag -> Revenues (priority 1) must win
    fact(ACME, "Revenues", *FY23, 100, "a-23", 2023, "10-K", "2024-02-15"),
    fact(ACME, "RevenueFromContractWithCustomerExcludingAssessedTax", *FY23, 90, "a-23", 2023, "10-K", "2024-02-15"),
    # FY2024: only the ASC 606 tag exists -> it is used
    fact(ACME, "RevenueFromContractWithCustomerExcludingAssessedTax", *FY24, 120, "a-24", 2024, "10-K", "2025-02-15"),
    # FY2023 Revenues re-reported in the FY2024 10-K unchanged (comparative column) -> not a restatement
    fact(ACME, "Revenues", *FY23, 100, "a-24", 2024, "10-K", "2025-02-15"),
    # FY2023 net income: filed as 10, restated to 12 in the next 10-K -> latest (12) wins
    fact(ACME, "NetIncomeLoss", *FY23, 10, "a-23", 2023, "10-K", "2024-02-15"),
    fact(ACME, "NetIncomeLoss", *FY23, 12, "a-24", 2024, "10-K", "2025-02-15"),
    # same filing date, two accessions: later accession number wins
    fact(ACME, "NetIncomeLoss", *FY24, 30, "a-24", 2024, "10-K", "2025-02-15"),
    fact(ACME, "NetIncomeLoss", *FY24, 31, "a-24z", 2024, "10-K/A", "2025-02-15"),
    # balance sheet instants
    fact(ACME, "Assets", None, "2024-12-31", 1000, "a-24", 2024, "10-K", "2025-02-15"),
    fact(ACME, "Liabilities", None, "2024-12-31", 600, "a-24", 2024, "10-K", "2025-02-15"),
    fact(ACME, "StockholdersEquity", None, "2024-12-31", 400, "a-24", 2024, "10-K", "2025-02-15"),
    # a balance-sheet tag wrongly reported as a duration -> dropped by the period_type join
    fact(ACME, "Assets", *FY24, 999, "a-24", 2024, "10-K", "2025-02-15"),
    # a quarter inside FY2024
    fact(ACME, "RevenueFromContractWithCustomerExcludingAssessedTax", "2024-04-01", "2024-06-30", 30,
         "a-q2", 2024, "10-Q", "2024-08-01", fp="Q2"),
    # a non-USD fact and an 8-K fact are filtered out in staging
    (ACME, "us-gaap", "Revenues", "EUR", *FY24, 5.0, "a-24", 2024, "FY", "10-K", "2025-02-15", None),
    fact(ACME, "Revenues", *FY24, 7, "a-8k", 2024, "8-K", "2025-01-10"),

    # --- BANKCO: bank revenue = NII + noninterest income -----------------------------------
    fact(BANKCO, "RevenueFromContractWithCustomerExcludingAssessedTax", *FY24, 40, "b-24", 2024, "10-K", "2025-02-20"),
    fact(BANKCO, "InterestIncomeExpenseNet", *FY24, 300, "b-24", 2024, "10-K", "2025-02-20"),
    fact(BANKCO, "NoninterestIncome", *FY24, 100, "b-24", 2024, "10-K", "2025-02-20"),
    fact(BANKCO, "NetIncomeLoss", *FY24, 80, "b-24", 2024, "10-K", "2025-02-20"),

    # --- TEXCO: not in Massachusetts -> excluded -------------------------------------------
    fact(TEXCO, "Revenues", *FY24, 500, "t-24", 2024, "10-K", "2025-02-20"),

    # --- OFFPRICE: retail calendar; filer switched fy convention (like TJX) ------------------
    fact(OFFPRICE, "Revenues", "2020-02-02", "2021-01-30", 50, "o-21", 2020, "10-K", "2021-03-30"),
    fact(OFFPRICE, "Revenues", "2021-01-31", "2022-01-29", 60, "o-22", 2022, "10-K", "2022-03-30"),
    fact(OFFPRICE, "Revenues", "2022-01-30", "2023-01-28", 70, "o-23", 2023, "10-K", "2023-03-30"),

    # --- BSX: override demotes the Revenues tag ----------------------------------------------
    fact(BSX, "Revenues", *FY23, 9076, "s-23", 2023, "10-K", "2024-02-20"),
    fact(BSX, "SalesRevenueNet", *FY23, 8386, "s-23", 2023, "10-K", "2024-02-20"),
]


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(":memory:")
    load.load_seeds(c, ROOT / "seeds")
    c.register("sc", SEED_COMPANIES)
    c.execute("create or replace table seed_companies as select * from sc")
    facts = pd.DataFrame(FACTS, columns=load.RAW_FACT_COLUMNS)
    load.create_raw_tables(c, facts, COMPANIES)
    build.build_models(c)
    build.run_layer(c, "analytics")
    yield c
    c.close()


def one(con, sql):
    rows = con.sql(sql).fetchall()
    assert len(rows) == 1, rows
    return rows[0]


def fact_value(con, cik, concept, end, period_type="duration"):
    return one(con, f"""
        select f.value, f.source_tag, f.is_restated, f.n_candidate_tags
        from fact_financials f join dim_period p using (period_key)
        where f.company_key = {cik} and f.concept_code = '{concept}'
          and p.period_end = '{end}' and p.period_type = '{period_type}'
          and (p.period_type = 'instant' or p.period_length = 'FY')""")


# ------------------------------------------------------------------ tag mapping
def test_every_tag_maps_to_exactly_one_concept():
    m = pd.read_csv(ROOT / "seeds" / "tag_map.csv")
    assert not m["tag"].duplicated().any()
    concepts = set(pd.read_csv(ROOT / "seeds" / "concepts.csv")["concept_code"])
    assert set(m["concept_code"]) <= concepts


def test_revenue_tag_priority_prefers_revenues(con):
    value, tag, _, n = fact_value(con, ACME, "revenue", "2023-12-31")
    assert (value, tag, n) == (100, "Revenues", 2)


def test_revenue_falls_back_to_asc606_tag(con):
    value, tag, _, _ = fact_value(con, ACME, "revenue", "2024-12-31")
    assert (value, tag) == (120, "RevenueFromContractWithCustomerExcludingAssessedTax")


def test_company_override_demotes_bad_tag(con):
    value, tag, _, _ = fact_value(con, BSX, "revenue", "2023-12-31")
    assert (value, tag) == (8386, "SalesRevenueNet")


def test_bank_revenue_is_nii_plus_noninterest_income(con):
    rev, src = one(con, f"select revenue, revenue_source from mart_annual where cik = {BANKCO}")
    assert rev == 400 and src.startswith("derived")


def test_shape_mismatch_and_filters(con):
    # Assets as a duration (999), EUR and 8-K facts never reach the fact table
    assert one(con, f"select count(*) from fact_financials where company_key = {ACME} and value in (999, 5, 7)")[0] == 0
    value, *_ = fact_value(con, ACME, "total_assets", "2024-12-31", "instant")
    assert value == 1000


# ------------------------------------------------------------------ dedupe + restatements
def test_latest_filed_value_wins(con):
    value, _, restated, _ = fact_value(con, ACME, "net_income", "2023-12-31")
    assert value == 12 and restated


def test_same_day_tie_broken_by_accession(con):
    value, *_ = fact_value(con, ACME, "net_income", "2024-12-31")
    assert value == 31


def test_identical_rereport_is_not_a_restatement(con):
    _, _, restated, _ = fact_value(con, ACME, "revenue", "2023-12-31")
    assert not restated


def test_restatement_audit_row(con):
    first, latest, pct, materiality, feeds = one(con, f"""
        select first_value, latest_value, change_pct, materiality, feeds_fact_table
        from audit_restatements where cik = {ACME} and tag = 'NetIncomeLoss' and period_end = '2023-12-31'""")
    assert (first, latest) == (10, 12)
    assert pct == pytest.approx(0.2)
    assert materiality.startswith("material") and feeds


def test_fact_table_primary_key(con):
    assert one(con, """select count(*) from (select company_key, concept_code, period_key from fact_financials
                       group by all having count(*) > 1)""")[0] == 0


# ------------------------------------------------------------------ universe + calendar
def test_non_massachusetts_and_missing_tickers_excluded(con):
    reasons = dict(con.sql("select ticker, exclusion_reason from audit_universe").fetchall())
    assert "TX" in reasons["TEX"]
    assert "not in SEC" in reasons["GONE"]
    assert reasons["ACME"] is None
    assert one(con, f"select count(*) from dim_company where cik = {TEXCO}")[0] == 0


def test_fiscal_year_uses_latest_convention(con):
    years = dict(con.sql(f"""select period_end::varchar, fiscal_year from dim_period
                             where cik = {OFFPRICE} and period_length = 'FY'""").fetchall())
    # latest 10-K says the year ending 2023-01-28 is fiscal 2023 -> earlier years follow suit
    assert years == {"2021-01-30": 2021, "2022-01-29": 2022, "2023-01-28": 2023}


def test_quarter_gets_fiscal_year_and_quarter(con):
    fy, fq, length = one(con, f"""select fiscal_year, fiscal_quarter, period_length from dim_period
                                  where cik = {ACME} and period_end = '2024-06-30'""")
    assert (fy, fq, length) == (2024, 2, "Q")


# ------------------------------------------------------------------ checks + loader
def test_checks_have_valid_headers_and_run(con):
    results = checks.run_checks(con)
    assert len(results) == len(list((ROOT / "sql" / "checks").glob("*.sql")))
    by_id = {r.check_id: r for r in results}
    assert by_id["01_pk_fact_financials"].status == "PASS"
    assert by_id["08_balance_sheet_identity"].status == "PASS"  # 1000 = 600 + 400
    assert by_id["11_fiscal_year_label"].violations == 1        # OFFPRICE's 2021 filing said fy 2020


def test_flatten_companyfacts():
    doc = {"cik": 42, "facts": {
        "us-gaap": {"Assets": {"units": {"USD": [
            {"end": "2024-12-31", "val": 5, "accn": "x", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-01-01"}]}}},
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
            {"end": "2024-12-31", "val": 9, "accn": "x", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-01-01"}]}}},
    }}
    rows = load.flatten_companyfacts(doc)
    assert rows == [(42, "us-gaap", "Assets", "USD", None, "2024-12-31", 5, "x", 2024, "FY", "10-K", "2025-01-01", None)]
