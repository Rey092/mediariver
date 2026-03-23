"""Tests for YAML workflow loading."""

from pathlib import Path

import pytest

from mediariver.config.loader import load_workflow, load_workflows_from_dir
from mediariver.config.schema import WorkflowSpec

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "workflows"


class TestLoadWorkflow:
    def test_load_valid_basic(self):
        spec = load_workflow(FIXTURES_DIR / "valid_basic.yaml")
        assert isinstance(spec, WorkflowSpec)
        assert spec.name == "test-basic"
        assert len(spec.flow) == 2

    def test_load_valid_conditional(self):
        spec = load_workflow(FIXTURES_DIR / "valid_conditional.yaml")
        assert spec.flow[1].condition == "{{steps.probe.width < 1200}}"

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_workflow(Path("/nonexistent/file.yaml"))

    def test_load_invalid_yaml(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("not: [valid: yaml: {{{")
        with pytest.raises(Exception):
            load_workflow(bad_file)


class TestLoadWorkflowsFromDir:
    def test_load_all_from_directory(self):
        specs = load_workflows_from_dir(FIXTURES_DIR)
        names = {s.name for s in specs}
        assert "test-basic" in names
        assert "test-conditional" in names

    def test_load_from_empty_dir(self, tmp_path):
        specs = load_workflows_from_dir(tmp_path)
        assert specs == []

    def test_load_from_nonexistent_dir(self):
        with pytest.raises(FileNotFoundError):
            load_workflows_from_dir(Path("/nonexistent/dir"))
