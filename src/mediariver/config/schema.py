"""Pydantic models for workflow YAML specs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConnectionConfig(BaseModel):
    """Configuration for a filesystem connection."""

    model_config = ConfigDict(extra="allow")

    type: str


class WatchConfig(BaseModel):
    """Configuration for directory watching."""

    connection: str
    path: str
    extensions: list[str]
    poll_interval: str = "30s"


class StepConfig(BaseModel):
    """Configuration for a single pipeline step."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    action: str
    input: str | None = None
    condition: str | None = Field(None, alias="if")
    on_failure: Literal["abort", "skip", "retry"] = "abort"
    max_retries: int = 3
    retry_delay: str = "30s"
    params: dict[str, Any] = {}


class WorkflowSpec(BaseModel):
    """Top-level workflow specification."""

    name: str
    description: str = ""
    connections: dict[str, ConnectionConfig]
    watch: WatchConfig
    flow: list[StepConfig]

    @model_validator(mode="after")
    def validate_unique_step_ids(self) -> WorkflowSpec:
        ids = [step.id for step in self.flow]
        duplicates = [x for x in ids if ids.count(x) > 1]
        if duplicates:
            raise ValueError(f"Duplicate step ids: {set(duplicates)}")
        return self
