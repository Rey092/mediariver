"""Tests for cross-field workflow validation."""

import pytest

from mediariver.config.loader import load_workflow
from mediariver.config.validators import validate_workflow, ValidationError as WorkflowValidationError

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "workflows"


class TestValidateWorkflow:
    def test_valid_workflow_passes(self):
        spec = load_workflow(FIXTURES_DIR / "valid_basic.yaml")
        validate_workflow(spec)

    def test_watch_connection_must_exist(self):
        spec = load_workflow(FIXTURES_DIR / "invalid_missing_conn.yaml")
        with pytest.raises(WorkflowValidationError, match="nonexistent"):
            validate_workflow(spec)
