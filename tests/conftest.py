"""Shared test fixtures."""

from pathlib import Path

import pytest
import structlog


@pytest.fixture(autouse=True)
def _configure_structlog_for_tests():
    """Prevent structlog from writing to stderr during tests (avoids colorama closed file errors on Windows)."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(50),  # CRITICAL only
        context_class=dict,
        logger_factory=structlog.testing.LogCapture,
        cache_logger_on_first_use=False,
    )


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def workflows_dir(fixtures_dir):
    return fixtures_dir / "workflows"
