"""http.post and http.get — HTTP request actions."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class HttpPostParams(BaseModel):
    url: str
    body: dict[str, Any] = {}
    headers: dict[str, str] = {}
    timeout: int = 30


@register_action("http.post")
class HttpPostAction(BaseAction):
    name = "http.post"
    params_model = HttpPostParams

    def run(self, context: dict[str, Any], params: HttpPostParams, executor: CommandExecutor, resolved_input: str | None = None) -> ActionResult:
        response = httpx.post(
            params.url,
            json=params.body,
            headers=params.headers,
            timeout=params.timeout,
        )
        return ActionResult(
            status="done",
            extras={"status_code": response.status_code, "response": response.text},
        )


class HttpGetParams(BaseModel):
    url: str
    save_to: str | None = None
    headers: dict[str, str] = {}
    timeout: int = 30


@register_action("http.get")
class HttpGetAction(BaseAction):
    name = "http.get"
    params_model = HttpGetParams

    def run(self, context: dict[str, Any], params: HttpGetParams, executor: CommandExecutor, resolved_input: str | None = None) -> ActionResult:
        response = httpx.get(params.url, headers=params.headers, timeout=params.timeout)
        if params.save_to:
            with open(params.save_to, "wb") as f:
                f.write(response.content)
            return ActionResult(status="done", output=params.save_to)
        return ActionResult(
            status="done",
            extras={"status_code": response.status_code, "response": response.text},
        )
