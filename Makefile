.PHONY: run run-real install-pi test clean

run:
	PYTHONPATH=src uv run --frozen python src/sentinel/app/cli.py

run-real:
	SENTINEL_BACKEND=real PYTHONPATH=src uv run --frozen python src/sentinel/app/cli.py

install-pi:
	uv sync --extra pi

test:
	uv run --frozen pytest tests/ -v

clean:
	find . -name __pycache__ -exec rm -rf {} +
	rm -f sentinel.db
