"""Run the SQL model layers in order against a DuckDB connection."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"


def sql_files(layer: str) -> list[Path]:
    return sorted((SQL_DIR / layer).glob("*.sql"))


def run_layer(con, layer: str) -> list[str]:
    ran = []
    for path in sql_files(layer):
        con.execute(path.read_text())
        ran.append(f"{layer}/{path.name}")
    return ran


def build_models(con) -> list[str]:
    """staging -> marts. Assumes raw_* and seed_* tables already exist."""
    return run_layer(con, "staging") + run_layer(con, "marts")
