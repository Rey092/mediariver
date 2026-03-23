"""YAML workflow file loading."""

from __future__ import annotations

from pathlib import Path

import yaml

from mediariver.config.schema import WorkflowSpec


def load_workflow(path: Path) -> WorkflowSpec:
    """Load and validate a single workflow YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")
    raw = yaml.safe_load(path.read_text())
    return WorkflowSpec(**raw)


def load_workflows_from_dir(directory: Path) -> list[WorkflowSpec]:
    """Load all workflow YAML files from a directory."""
    if not directory.exists():
        raise FileNotFoundError(f"Workflows directory not found: {directory}")
    specs = []
    for path in sorted(directory.glob("*.yaml")):
        specs.append(load_workflow(path))
    for path in sorted(directory.glob("*.yml")):
        specs.append(load_workflow(path))
    return specs
