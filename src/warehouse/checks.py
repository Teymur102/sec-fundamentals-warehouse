"""Data-quality runner.

Each file in sql/checks/ is one assertion: a SELECT that returns the rows that VIOLATE it.
Zero rows = pass. Otherwise the result is FAIL (severity error) or WARN (severity warn).
Header comments carry the metadata:
    -- name: ...
    -- severity: error|warn
    -- description: ...
    -- population: <one-line SELECT count(*)>   (optional: how many things were tested)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .build import sql_files

HEADER = re.compile(r"^--\s*(name|severity|description|population):\s*(.+)$", re.M)


@dataclass
class CheckResult:
    check_id: str
    name: str
    severity: str
    description: str
    violations: int
    population: int | None
    status: str
    sample: pd.DataFrame = field(repr=False)


def parse_header(sql: str) -> dict:
    meta = {k: v.strip() for k, v in HEADER.findall(sql)}
    missing = {"name", "severity", "description"} - meta.keys()
    if missing:
        raise ValueError(f"check is missing header fields: {missing}")
    if meta["severity"] not in ("error", "warn"):
        raise ValueError(f"bad severity {meta['severity']!r}")
    return meta


def run_checks(con) -> list[CheckResult]:
    results = []
    for path in sql_files("checks"):
        sql = path.read_text()
        meta = parse_header(sql)
        df = con.sql(sql).df()
        n = len(df)
        population = con.sql(meta["population"]).fetchall()[0][0] if "population" in meta else None
        status = "PASS" if n == 0 else ("FAIL" if meta["severity"] == "error" else "WARN")
        results.append(CheckResult(path.stem, meta["name"], meta["severity"], meta["description"],
                                   n, population, status, df))
    return results


def results_frame(results: list[CheckResult]) -> pd.DataFrame:
    return pd.DataFrame([{
        "check_id": r.check_id, "check": r.name, "severity": r.severity,
        "status": r.status, "violating_rows": r.violations,
        "rows_tested": r.population, "description": r.description,
    } for r in results])


def write_results(results: list[CheckResult], out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = results_frame(results)
    summary.to_csv(out_dir / "dq_results.csv", index=False)
    detail_dir = out_dir / "dq_violations"
    detail_dir.mkdir(exist_ok=True)
    for old in detail_dir.glob("*.csv"):
        old.unlink()
    for r in results:
        if r.violations:
            r.sample.to_csv(detail_dir / f"{r.check_id}.csv", index=False)
    return summary
