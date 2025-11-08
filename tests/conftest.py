"""Pytest configuration helpers for test suite.

Provides fallback command-line options when optional plugins
such as ``pytest-cov`` are unavailable. This allows the test
suite to run in minimal environments without forcing extra
dependencies while still supporting coverage flags when the
plugin is installed.
"""
from __future__ import annotations

from typing import Final
import importlib.util


def _has_pytest_cov() -> bool:
    """Return True if the ``pytest-cov`` plugin can be imported."""

    return importlib.util.find_spec("pytest_cov") is not None


_HAS_PYTEST_COV: Final[bool] = _has_pytest_cov()


if not _HAS_PYTEST_COV:

    def pytest_addoption(parser):  # type: ignore[override]
        """Register no-op coverage flags when pytest-cov is missing."""

        parser.addoption(
            "--cov",
            action="append",
            default=[],
            dest="cov",
            metavar="COV",
            help="(no-op) Enable coverage reporting when pytest-cov is installed.",
        )
        parser.addoption(
            "--cov-report",
            action="append",
            default=[],
            dest="cov_report",
            metavar="REPORT",
            help=(
                "(no-op) Coverage reports require pytest-cov; option is ignored "
                "when the plugin is unavailable."
            ),
        )

    def pytest_configure(config):  # type: ignore[override]
        """Emit a friendly note when coverage options are ignored."""

        if config.getoption("cov") or config.getoption("cov_report"):
            config.issue_config_time_warning(
                "pytest-cov is not installed; coverage options from pyproject.toml "
                "are ignored. Install the 'dev' extra to enable coverage support.",
                stacklevel=2,
            )
