"""Nemotron on Nebius Token Factory (OpenAI-compatible) with JSON output, retries and a call log.

Every call is appended to data/runtime/calls.jsonl so the UI can show routing, tokens, cost and latency.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any, Type, TypeVar

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from . import config

T = TypeVar("T", bound=BaseModel)

CALL_LOG = config.RUNTIME_DIR / "calls.jsonl"

_client: OpenAI | None = None


class LLMError(RuntimeError):
    pass


def client() -> OpenAI:
    global _client
    if _client is None:
        if not config.NEBIUS_API_KEY:
            raise LLMError("NEBIUS_API_KEY is not set (see .env.example)")
        _client = OpenAI(base_url=config.NEBIUS_BASE_URL, api_key=config.NEBIUS_API_KEY, timeout=180)
    return _client


def _log(entry: dict[str, Any]) -> None:
    with CALL_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _cost(model_id: str, usage: Any) -> float:
    m = config.MODELS.get(model_id)
    if not m or usage is None:
        return 0.0
    return (usage.prompt_tokens * m.usd_per_m_in + usage.completion_tokens * m.usd_per_m_out) / 1e6


def chat(
    job: str,
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
    reasoning: bool | None = None,
    tag: str = "",
    retries: int = 4,
) -> str:
    """One chat completion. Retries rate limits / transient errors with exponential backoff."""
    model_id = model or config.ROUTES[job]
    kwargs: dict[str, Any] = dict(model=model_id, messages=messages, temperature=temperature, max_tokens=max_tokens)
    if response_format:
        kwargs["response_format"] = response_format
    if reasoning is not None:
        # Nemotron chat templates take enable_thinking; harmless if ignored by the server.
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": reasoning}}

    delay = 2.0
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            resp = client().chat.completions.create(**kwargs)
        except (RateLimitError, APIConnectionError) as e:
            if attempt == retries:
                raise LLMError(f"{type(e).__name__}: {e}") from e
            time.sleep(delay)
            delay *= 2
            continue
        except APIStatusError as e:
            if e.status_code >= 500 and attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise LLMError(f"HTTP {e.status_code}: {e.message}") from e
        text = resp.choices[0].message.content or ""
        _log(
            {
                "id": str(uuid.uuid4()),
                "ts": time.time(),
                "job": job,
                "tag": tag,
                "model": model_id,
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                "usd": round(_cost(model_id, resp.usage), 6),
                "latency_s": round(time.time() - t0, 3),
                "attempt": attempt,
            }
        )
        return text
    raise LLMError("unreachable")


_THINK = re.compile(r"<think>.*?</think>", re.S)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


def _json_text(text: str) -> str:
    text = _THINK.sub("", text).strip()
    text = _FENCE.sub("", text).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start > 0:
        text = text[start:]
    return text


def structured(
    job: str,
    system: str,
    user: str,
    schema: Type[T],
    *,
    model: str | None = None,
    tag: str = "",
    max_repairs: int = 2,
    max_tokens: int = 4096,
    reasoning: bool = False,
) -> T:
    """Ask for JSON matching a pydantic schema. Uses json_schema response_format, then validates and repairs."""
    js = schema.model_json_schema()
    rf = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": js, "strict": False}}
    messages = [
        {"role": "system", "content": system + "\n\nRespond with JSON only, matching this schema:\n" + json.dumps(js)},
        {"role": "user", "content": user},
    ]
    last_err = ""
    for i in range(max_repairs + 1):
        try:
            raw = chat(job, messages, model=model, response_format=rf, reasoning=reasoning, tag=tag, max_tokens=max_tokens)
        except LLMError as e:
            if "response_format" in str(e) or "json_schema" in str(e):
                rf = None  # server rejected structured output; fall back to prompt-only JSON
                raw = chat(job, messages, model=model, reasoning=reasoning, tag=tag, max_tokens=max_tokens)
            else:
                raise
        try:
            return schema.model_validate_json(_json_text(raw))
        except (ValidationError, ValueError) as e:
            last_err = str(e)[:1500]
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"That was not valid JSON for the schema. Error:\n{last_err}\nReturn corrected JSON only."},
            ]
    raise LLMError(f"structured output failed after repairs: {last_err}")
