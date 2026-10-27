PY := .venv/bin/python

.PHONY: all run offline test clean

all: run test

.venv/bin/python:
	python3 -m venv .venv
	$(PY) -m pip install -q -r requirements.txt

run: .venv/bin/python
	$(PY) run.py

offline: .venv/bin/python
	$(PY) run.py --offline

test: .venv/bin/python
	$(PY) -m pytest -q

clean:
	rm -f data/warehouse.duckdb
