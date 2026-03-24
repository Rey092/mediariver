"""YAML workflow file loading."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from mediariver.config.schema import WorkflowSpec
from mediariver.engine.template import resolve_value


def load_workflow(path: Path) -> WorkflowSpec:
    """Load and validate a single workflow YAML file.

    Resolves {{env.X}} templates in connection configs at load time,
    since connections are built before the pipeline runner runs.
    """
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")
    raw = yaml.safe_load(path.read_text())

    # Resolve env templates in connection configs
    env_ctx = {"env": dict(os.environ)}
    if "connections" in raw and isinstance(raw["connections"], dict):
        for conn_name, conn_data in raw["connections"].items():
            if isinstance(conn_data, dict):
                raw["connections"][conn_name] = resolve_value(conn_data, env_ctx)

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
