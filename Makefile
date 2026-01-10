.PHONY: help install test test-verbose test-coverage test-watch clean deploy-check generate-docs check-docs install-skills

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
	@echo "  make install-skills  - Install Agent Skills to Cline project"
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

install-skills:
	@echo "🎮 Installing Agent Skills for Cline"
	@echo ""
	@echo "Choose installation location:"
	@echo "  1) Current project (.cline/skills/)"
	@echo "  2) Global installation (~/.cline/skills/)"
	@echo ""
	@read -p "Enter choice (1 or 2): " choice; \
	if [ "$$choice" = "1" ]; then \
		read -p "Enter project path (or press Enter for current directory): " project_path; \
		if [ -z "$$project_path" ]; then \
			project_path="."; \
		fi; \
		mkdir -p "$$project_path/.cline/skills"; \
		cp -r skills/* "$$project_path/.cline/skills/"; \
		echo ""; \
		echo "✅ Skills installed to $$project_path/.cline/skills/"; \
		echo ""; \
		echo "Installed skills:"; \
		ls -1 "$$project_path/.cline/skills/"; \
	elif [ "$$choice" = "2" ]; then \
		mkdir -p ~/.cline/skills; \
		cp -r skills/* ~/.cline/skills/; \
		echo ""; \
		echo "✅ Skills installed globally to ~/.cline/skills/"; \
		echo ""; \
		echo "Installed skills:"; \
		ls -1 ~/.cline/skills/; \
	else \
		echo ""; \
		echo "❌ Invalid choice. Please run 'make install-skills' again."; \
		exit 1; \
	fi; \
	echo ""; \
	echo "📝 Next steps:"; \
	echo "  1. Enable Skills in Cline: Settings → Features → Enable Skills"; \
	echo "  2. Open Skills panel: Click scale icon below chat input"; \
	echo "  3. Verify all 5 skills are listed and enabled"; \
	echo ""; \
	echo "For more info: See skills/README.md"
