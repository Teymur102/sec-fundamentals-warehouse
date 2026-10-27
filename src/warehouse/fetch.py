"""Download SEC EDGAR inputs into data/raw (cached; re-runs make no requests).

Sources
  - https://www.sec.gov/files/company_tickers.json            ticker -> CIK
  - https://data.sec.gov/submissions/CIK##########.json         name, SIC, HQ address
  - https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json  every XBRL fact

SEC fair-access policy: declare a User-Agent with contact info and stay under
10 requests/second. We throttle to 5 req/s to leave headroom.
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

USER_AGENT = "Teymur Eyvazov teymur.eyvazov001@umb.edu"
MIN_INTERVAL_S = 0.2  # 5 requests/second, half of SEC's 10 req/s ceiling

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


class Throttle:
    def __init__(self, min_interval: float = MIN_INTERVAL_S):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


def _get(session: requests.Session, throttle: Throttle, url: str) -> bytes:
    for attempt in range(4):
        throttle.wait()
        r = session.get(url, timeout=60)
        if r.status_code == 200:
            return r.content
        if r.status_code in (429, 503):  # back off and retry
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
    raise RuntimeError(f"giving up on {url} after retries")


def _cached(path: Path, session, throttle, url: str, log: list) -> Path:
    if path.exists() and path.stat().st_size > 0:
        log.append({"file": path.name, "url": url, "status": "cached"})
        return path
    body = _get(session, throttle, url)
    path.write_bytes(body)
    log.append({"file": path.name, "url": url, "status": "downloaded"})
    return path


def read_universe(seed_csv: Path) -> list[dict]:
    with seed_csv.open() as f:
        return [row for row in csv.DictReader(f) if not row["ticker"].startswith("#")]


def fetch_all(raw_dir: Path, seed_csv: Path, offline: bool = False) -> dict:
    """Fetch tickers, submissions and companyfacts for every seed ticker.

    Returns a manifest dict that is also written to data/raw/manifest.json.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    throttle = Throttle()
    log: list[dict] = []

    def get(path: Path, url: str) -> Path:
        if offline and not path.exists():
            raise FileNotFoundError(f"--offline but {path} is not cached")
        return _cached(path, session, throttle, url, log)

    tickers_path = get(raw_dir / "company_tickers.json", TICKERS_URL)
    tickers = json.loads(tickers_path.read_text())
    by_ticker = {v["ticker"].upper(): int(v["cik_str"]) for v in tickers.values()}

    resolved, missing = [], []
    for row in read_universe(seed_csv):
        t = row["ticker"].upper()
        cik = by_ticker.get(t)
        if cik is None:
            missing.append(t)
            continue
        get(raw_dir / f"submissions_CIK{cik:010d}.json", SUBMISSIONS_URL.format(cik=cik))
        get(raw_dir / f"companyfacts_CIK{cik:010d}.json", FACTS_URL.format(cik=cik))
        resolved.append({"ticker": t, "cik": cik})

    files = []
    for p in sorted(raw_dir.glob("*.json")):
        if p.name == "manifest.json":
            continue
        files.append({
            "file": p.name,
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
        })
    manifest = {
        "user_agent": USER_AGENT,
        "requests_made": sum(1 for x in log if x["status"] == "downloaded"),
        "served_from_cache": sum(1 for x in log if x["status"] == "cached"),
        "resolved": resolved,
        "tickers_not_in_sec_file": missing,
        "files": files,
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
