.PHONY: run test clean

run:
	PYTHONPATH=src uv run python src/sentinel/app/cli.py

test:
	uv run pytest tests/ -v

clean:
	find . -name __pycache__ -exec rm -rf {} +
	rm -f sentinel.db
