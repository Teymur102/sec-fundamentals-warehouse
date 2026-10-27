"""Land raw SEC JSON into DuckDB tables, untouched apart from flattening.

raw_facts      one row per (company, taxonomy, tag, unit, period, filing) as SEC publishes it
raw_companies  one row per company from the submissions endpoint (name, SIC, HQ address)
seed_*         hand-maintained CSVs in seeds/ (universe, XBRL tag map)
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

TAXONOMIES = ("us-gaap",)


def flatten_companyfacts(doc: dict) -> list[tuple]:
    cik = int(doc["cik"])
    rows = []
    for taxonomy in TAXONOMIES:
        for tag, body in doc.get("facts", {}).get(taxonomy, {}).items():
            for unit, facts in body.get("units", {}).items():
                for f in facts:
                    rows.append((
                        cik, taxonomy, tag, unit,
                        f.get("start"), f["end"], f["val"],
                        f["accn"], f.get("fy"), f.get("fp"), f["form"], f["filed"], f.get("frame"),
                    ))
    return rows


RAW_FACT_COLUMNS = ["cik", "taxonomy", "tag", "unit", "period_start", "period_end", "val",
                    "accn", "fy", "fp", "form", "filed", "frame"]


def load_raw(con: duckdb.DuckDBPyConnection, raw_dir: Path, ciks: list[int]) -> dict:
    fact_rows: list[tuple] = []
    company_rows: list[dict] = []
    for cik in ciks:
        facts = json.loads((raw_dir / f"companyfacts_CIK{cik:010d}.json").read_text())
        fact_rows.extend(flatten_companyfacts(facts))
        sub = json.loads((raw_dir / f"submissions_CIK{cik:010d}.json").read_text())
        biz = sub.get("addresses", {}).get("business", {}) or {}
        company_rows.append({
            "cik": cik,
            "entity_name": sub.get("name"),
            "tickers": ",".join(sub.get("tickers") or []),
            "exchanges": ",".join(x or "" for x in (sub.get("exchanges") or [])),
            "sic": int(sub["sic"]) if sub.get("sic") else None,
            "sic_description": sub.get("sicDescription"),
            "hq_city": biz.get("city"),
            "hq_state": biz.get("stateOrCountry"),
            "fiscal_year_end_mmdd": sub.get("fiscalYearEnd"),
        })

    facts_df = pd.DataFrame(fact_rows, columns=RAW_FACT_COLUMNS)
    facts_df["val"] = facts_df["val"].astype("float64")
    companies_df = pd.DataFrame(company_rows)
    create_raw_tables(con, facts_df, companies_df)
    return {"raw_fact_rows": len(facts_df), "companies": len(companies_df)}


def create_raw_tables(con, facts_df: pd.DataFrame, companies_df: pd.DataFrame) -> None:
    con.register("facts_df", facts_df)
    con.register("companies_df", companies_df)
    con.execute("""
        create or replace table raw_facts as
        select cast(cik as integer) cik, taxonomy, tag, unit,
               cast(period_start as date) period_start, cast(period_end as date) period_end,
               cast(val as double) val, accn, cast(fy as integer) fy, fp, form,
               cast(filed as date) filed, frame
        from facts_df
    """)
    con.execute("create or replace table raw_companies as select * from companies_df")
    con.unregister("facts_df")
    con.unregister("companies_df")


def load_seeds(con, seeds_dir: Path) -> None:
    con.execute(f"""
        create or replace table seed_companies as
        select * from read_csv('{seeds_dir / 'companies.csv'}', header=true, all_varchar=true)
    """)
    con.execute(f"""
        create or replace table seed_concepts as
        select * from read_csv('{seeds_dir / 'concepts.csv'}', header=true)
    """)
    con.execute(f"""
        create or replace table seed_tag_map as
        select * from read_csv('{seeds_dir / 'tag_map.csv'}', header=true,
                               columns={{'concept_code':'VARCHAR','tag':'VARCHAR','priority':'INTEGER','note':'VARCHAR'}})
    """)
    con.execute(f"""
        create or replace table seed_tag_overrides as
        select * from read_csv('{seeds_dir / 'tag_overrides.csv'}', header=true,
                               columns={{'ticker':'VARCHAR','tag':'VARCHAR','priority':'INTEGER','reason':'VARCHAR'}})
    """)
