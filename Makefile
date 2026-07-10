.PHONY: install test coverage build lint

install:
	uv sync --extra dev

test:
	uv run --extra dev pytest

coverage:
	uv run --extra dev pytest --cov=. --cov-report=xml:coverage.xml

build:
	docker build -t timothe/ace-pace:local .

lint:
	uv run --extra dev pyright acepace.py clients.py
