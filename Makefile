.PHONY: help install test test-verbose test-coverage test-watch clean deploy-check

help:
	@echo "Ankh-Morpork Scramble - Available Commands"
	@echo "==========================================="
	@echo "  make install         - Install dependencies"
	@echo "  make test            - Run tests"
	@echo "  make test-verbose    - Run tests with verbose output"
	@echo "  make test-coverage   - Run tests with coverage report"
	@echo "  make test-watch      - Run tests in watch mode"
	@echo "  make deploy-check    - Verify tests pass before deployment"
	@echo "  make clean           - Clean up generated files"
	@echo "  make run             - Run the development server"

install:
	uv sync --extra dev

test:
	uv run pytest

test-verbose:
	uv run pytest -v

test-coverage:
	uv run pytest --cov=app --cov-report=html --cov-report=term
	@echo ""
	@echo "✅ Coverage report generated in htmlcov/index.html"

test-watch:
	uv run pytest-watch

deploy-check:
	@echo "🔍 Running pre-deployment checks..."
	@uv run pytest -v --cov=app --cov-fail-under=45
	@echo ""
	@echo "✅ All tests passed! Ready to deploy."

clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
