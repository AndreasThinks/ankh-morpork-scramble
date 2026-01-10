.PHONY: help install test test-verbose test-coverage test-watch clean deploy-check generate-docs check-docs

help:
	@echo "Ankh-Morpork Scramble - Available Commands"
	@echo "==========================================="
	@echo "  make install         - Install dependencies"
	@echo "  make test            - Run tests"
	@echo "  make test-verbose    - Run tests with verbose output"
	@echo "  make test-coverage   - Run tests with coverage report"
	@echo "  make test-watch      - Run tests in watch mode"
	@echo "  make deploy-check    - Verify tests pass before deployment"
	@echo "  make generate-docs   - Auto-generate documentation from code"
	@echo "  make check-docs      - Check if documentation is up to date"
	@echo "  make clean           - Clean up generated files"
	@echo "  make run             - Run the development server"

install:
	uv sync --extra dev

test:
	uv run --extra dev pytest

test-verbose:
	uv run --extra dev pytest -v

test-coverage:
	uv run --extra dev pytest --cov=app --cov-report=html --cov-report=term
	@echo ""
	@echo "✅ Coverage report generated in htmlcov/index.html"

test-watch:
	uv run --extra dev pytest-watch

deploy-check:
	@echo "🔍 Running pre-deployment checks..."
	@uv run --extra dev pytest -v --cov=app --cov-fail-under=45
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

generate-docs:
	@echo "📝 Generating documentation from code..."
	@uv run python -m docs_generator.generate
	@echo ""
	@echo "✅ Documentation generated successfully!"

check-docs:
	@echo "🔍 Checking if documentation is up to date..."
	@uv run python -m docs_generator.generate --check
