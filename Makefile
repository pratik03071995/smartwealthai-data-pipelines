.PHONY: install dev test lint run

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

dev:
	. .venv/bin/activate && pip install -r requirements-dev.txt

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check src && black --check src

run:
	. .venv/bin/activate && python -m smartwealth_data.cli earnings --tickers "AAPL,MSFT,NVDA"
