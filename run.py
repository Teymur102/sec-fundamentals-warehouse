"""One command: fetch -> load -> model -> analytics -> data-quality checks -> report.

    python run.py            # uses cached raw JSON in data/raw, downloads anything missing
    python run.py --offline  # never touches the network
    python run.py --refresh  # delete the cache and download everything again
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from warehouse import build, checks, fetch, load, report  # noqa: E402

RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "warehouse.duckdb"
SEEDS = ROOT / "seeds"
OUT = ROOT / "output"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    if args.refresh and RAW.exists():
        shutil.rmtree(RAW)

    print("1/6 fetch   SEC EDGAR -> data/raw")
    manifest = fetch.fetch_all(RAW, SEEDS / "companies.csv", offline=args.offline)
    print(f"    {manifest['requests_made']} downloaded, {manifest['served_from_cache']} from cache; "
          f"not in SEC ticker file: {manifest['tickers_not_in_sec_file'] or 'none'}")

    print("2/6 load    raw JSON -> DuckDB raw_* and seed_* tables")
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    load.load_seeds(con, SEEDS)
    stats = load.load_raw(con, RAW, [r["cik"] for r in manifest["resolved"]])
    print(f"    {stats['raw_fact_rows']:,} raw facts for {stats['companies']} companies")

    print("3/6 model   staging -> dims/facts/marts")
    for f in build.build_models(con):
        print(f"    ran sql/{f}")

    print("4/6 analyze ratios, rankings, sector medians")
    for f in build.run_layer(con, "analytics"):
        print(f"    ran sql/{f}")

    print("5/6 checks  data-quality assertions")
    results = checks.run_checks(con)
    summary = checks.write_results(results, OUT)
    for r in results:
        tested = f" of {r.population:,}" if r.population is not None else ""
        print(f"    {r.status:4}  {r.check_id:32} {r.violations:>4}{tested} violating rows")

    print("6/6 report  tables, charts, report.md/html, README.md")
    facts = report.build_report(con, results, manifest, stats, OUT, ROOT)
    con.close()

    print(json.dumps(facts["headline"], indent=2, default=str))
    print(f"done in {time.time() - t0:.1f}s")
    n_fail = int((summary["status"] == "FAIL").sum())
    print(f"data-quality: {len(summary)} checks, {int((summary['status'] == 'PASS').sum())} pass, "
          f"{n_fail} fail, {int((summary['status'] == 'WARN').sum())} warn (see output/dq_results.csv)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
