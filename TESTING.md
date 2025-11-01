# Testing Guide

## Overview

The Ankh-Morpork Scramble project uses comprehensive testing to ensure code quality and prevent regressions. We enforce a 70% minimum code coverage threshold and all tests must pass before deployment.

## Running Tests

### Quick Start

```bash
# Run all tests
make test

# Run with verbose output
make test-verbose

# Run with coverage report
make test-coverage

# Check if ready to deploy
make deploy-check
```

### Using UV directly

```bash
# Basic test run
uv run pytest

# With coverage
uv run pytest --cov=app --cov-report=html

# Specific test file
uv run pytest tests/test_api.py -v

# Specific test function
uv run pytest tests/test_api.py::test_create_game -v
```

## Test Structure

```
tests/
├── __init__.py
├── test_dice.py              # Dice rolling mechanics (9 tests)
├── test_models.py            # Data models (10 tests) 
├── test_api.py               # API endpoints (8 tests)
└── test_join_and_messages.py # Join/messaging features (7 tests)
```

**Total: 34 tests** (as of current implementation)

## Current Test Coverage

### ✅ Well-Covered Areas
- **Dice Rolling**: d6, 2d6, target rolls, modifiers, armor, injury
- **Data Models**: Position, Pitch, Player, Team, state transitions
- **API Endpoints**: CRUD operations, game creation, team setup
- **Join & Messaging**: Team joining, message sending/receiving, game reset

### ⚠️ Areas Needing More Tests
- Movement mechanics (dodge, rush, standing up)
- Ball handling (pick-up, pass, catch, scatter)
- Combat system (blocks, armor breaks, injuries)
- Turnover conditions
- Special actions (blitz, foul)
- Game state progression

## CI/CD Integration

### GitHub Actions
Every push and pull request triggers:
1. Dependency installation via UV
2. Full test suite execution
3. Coverage report generation
4. Coverage threshold check (70% minimum)

**Status**: Tests must pass before merging to `main` or `develop`.

### Pre-commit Hooks
Install pre-commit hooks to run tests before each commit:

```bash
# Install pre-commit (if not already installed)
pip install pre-commit

# Install git hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

This will:
- Run all tests before commit
- Check YAML, JSON, TOML syntax
- Fix trailing whitespace
- Ensure files end with newline

### Deployment Protection
The `make deploy-check` command ensures:
- All tests pass
- Coverage meets 70% threshold
- No pytest warnings or errors

**Always run before deploying:**
```bash
make deploy-check && ./deploy.sh
```

## Writing New Tests

### Test File Naming
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Example Test

```python
"""Tests for new feature"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_new_feature():
    """Test description"""
    # Arrange
    response = client.post("/game")
    game_id = response.json()["game_id"]
    
    # Act
    result = client.get(f"/game/{game_id}")
    
    # Assert
    assert result.status_code == 200
    assert result.json()["game_id"] == game_id
```

### Using Markers

```python
@pytest.mark.slow
def test_long_running():
    """Test that takes a while"""
    pass

@pytest.mark.integration
def test_full_system():
    """Test multiple components together"""
    pass
```

Run specific markers:
```bash
# Skip slow tests
pytest -m "not slow"

# Only integration tests
pytest -m integration
```

## Coverage Reports

### Viewing Coverage

```bash
# Generate HTML coverage report
make test-coverage

# Open in browser
open htmlcov/index.html
```

### Coverage Configuration
Coverage is configured in `pyproject.toml`:
- **Source**: `app/` directory
- **Omit**: Test files, `__init__.py` files
- **Exclude**: `pragma: no cover`, type checking blocks

### Coverage Goals
- **Current**: ~70% (enforced minimum)
- **Target**: 85%+ for production deployment

## Troubleshooting

### Tests Fail Locally But Pass in CI
- Ensure you're using the same Python version (3.11)
- Run `uv sync --extra dev` to update dependencies
- Clear pytest cache: `make clean`

### Import Errors
```bash
# Reinstall package in editable mode
uv sync
```

### Slow Tests
```bash
# Skip slow tests
pytest -m "not slow"

# Run only fast tests
pytest -m "not (slow or integration)"
```

### Coverage Too Low
1. Check uncovered lines: `make test-coverage`
2. Open `htmlcov/index.html` to see visual report
3. Add tests for uncovered code paths
4. Use `# pragma: no cover` for truly untestable code

## Best Practices

1. **Write tests first** (TDD) when adding new features
2. **One assertion focus** per test function
3. **Use descriptive test names** that explain what is being tested
4. **Test edge cases** and error conditions
5. **Keep tests independent** - no shared state
6. **Use fixtures** for common setup (pytest fixtures)
7. **Mock external dependencies** (if any added)
8. **Update this doc** when adding new test categories

## Future Test Additions

Planned test files to reach comprehensive coverage:
- `test_movement.py` - Movement, dodge, rush mechanics
- `test_ball_handling.py` - Pick-up, pass, catch, scatter
- `test_combat.py` - Blocks, armor, injury resolution
- `test_turnovers.py` - All turnover conditions
- `test_game_progression.py` - Turn/half/game transitions
- `test_edge_cases.py` - Error conditions, validation

Target: **75-90 tests** for complete coverage.

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- Project-specific rules: `.clinerules/ankh-morpork-project.md`
