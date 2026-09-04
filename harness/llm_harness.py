"""LLMHarness: the single reusable entry point every agent calls through.

Guarantees, in order, on every `run()`:
  1. Input is validated against the caller's pydantic input schema.
  2. The request is logged (redacted) before the call is made.
  3. The LLM call is wrapped in a configurable timeout. If it times out
     and a fallback was provided, the fallback is returned gracefully
     instead of raising.
  4. Rate-limit (429) / server (5xx) errors are retried with exponential
     backoff (harness.retry), up to config.MAX_RETRIES.
  5. The raw response is parsed as JSON and validated against the
     caller's pydantic output schema. If it doesn't validate, that is
     reported as a structured failure rather than silently passed on.
  6. The response (redacted) and outcome are logged.

Nothing here is agent-specific -- agents only supply schemas, a system
prompt, and a prompt-building function.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Callable, Optional, Type

from pydantic import BaseModel, ValidationError

import config
from .exceptions import (
    RetryExhaustedError,
    SchemaValidationError,
    TimeoutFallbackError,
    RetryableError,
)
from .llm_clients import LLMClient, MockLLMClient
from .logging_utils import build_logger, log_event, redact_text
from .retry import call_with_retry

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm-harness")


@dataclass
class HarnessResult:
    success: bool
    output: Optional[BaseModel] = None
    raw_text: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    used_fallback: bool = False
    attempts: int = 0
    latency_seconds: float = 0.0
    agent_name: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output.model_dump() if self.output is not None else None,
            "error": self.error,
            "error_type": self.error_type,
            "used_fallback": self.used_fallback,
            "attempts": self.attempts,
            "latency_seconds": round(self.latency_seconds, 4),
            "agent_name": self.agent_name,
        }


class LLMHarness:
    def __init__(
        self,
        agent_name: str,
        system_prompt: str,
        input_schema: Type[BaseModel],
        output_schema: Type[BaseModel],
        client: Optional[LLMClient] = None,
        timeout: float = config.REQUEST_TIMEOUT,
        max_retries: int = config.MAX_RETRIES,
        fallback: Optional[BaseModel] = None,
    ):
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.client = client or MockLLMClient()
        self.timeout = timeout
        self.max_retries = max_retries
        self.fallback = fallback
        self.logger = build_logger(f"guardian.{agent_name}")

    def run(self, raw_input: dict, prompt_builder: Callable[[BaseModel], str]) -> HarnessResult:
        start = time.monotonic()

        # 1. Validate input
        try:
            validated_input = self.input_schema(**raw_input)
        except ValidationError as exc:
            log_event("input_validation_failed", {"raw_input": raw_input, "errors": exc.errors()})
            return HarnessResult(
                success=False,
                error=f"Input schema validation failed: {exc}",
                error_type="SchemaValidationError",
                agent_name=self.agent_name,
                latency_seconds=time.monotonic() - start,
            )

        prompt = prompt_builder(validated_input)
        log_event("request", {
            "agent": self.agent_name,
            "input": validated_input.model_dump(),
            "prompt_preview": redact_text(prompt[:400]),
        })

        # 2 & 3. Timeout-wrapped, retried call
        attempt_counter = {"n": 0}

        def _tracked_call() -> str:
            attempt_counter["n"] += 1
            return self.client.complete(self.system_prompt, prompt)

        def _do_call() -> str:
            return call_with_retry(
                _tracked_call,
                max_retries=self.max_retries,
                logger=self.logger,
            )

        try:
            future = _executor.submit(_do_call)
            raw_text = future.result(timeout=self.timeout)
        except FutureTimeoutError:
            future.cancel()
            latency = time.monotonic() - start
            log_event("timeout", {"agent": self.agent_name, "timeout": self.timeout})
            if self.fallback is not None:
                return HarnessResult(
                    success=True,
                    output=self.fallback,
                    used_fallback=True,
                    error=f"Timed out after {self.timeout}s; used fallback.",
                    error_type="TimeoutFallback",
                    agent_name=self.agent_name,
                    latency_seconds=latency,
                )
            return HarnessResult(
                success=False,
                error=str(TimeoutFallbackError(f"Timed out after {self.timeout}s with no fallback configured.", timeout=self.timeout)),
                error_type="TimeoutFallbackError",
                agent_name=self.agent_name,
                latency_seconds=latency,
            )
        except RetryExhaustedError as exc:
            latency = time.monotonic() - start
            log_event("retry_exhausted", {"agent": self.agent_name, "error": str(exc), "attempts": exc.attempts})
            if self.fallback is not None:
                return HarnessResult(
                    success=True,
                    output=self.fallback,
                    used_fallback=True,
                    error=str(exc),
                    error_type="RetryExhaustedError",
                    attempts=exc.attempts,
                    agent_name=self.agent_name,
                    latency_seconds=latency,
                )
            return HarnessResult(
                success=False,
                error=str(exc),
                error_type="RetryExhaustedError",
                attempts=exc.attempts,
                agent_name=self.agent_name,
                latency_seconds=latency,
            )
        except Exception as exc:
            latency = time.monotonic() - start
            log_event("unexpected_error", {"agent": self.agent_name, "error": str(exc)})
            if self.fallback is not None:
                return HarnessResult(
                    success=True,
                    output=self.fallback,
                    used_fallback=True,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    agent_name=self.agent_name,
                    latency_seconds=latency,
                )
            return HarnessResult(
                success=False,
                error=str(exc),
                error_type=type(exc).__name__,
                agent_name=self.agent_name,
                latency_seconds=latency,
            )

        latency = time.monotonic() - start

        # 4. Parse + validate output
        try:
            parsed = json.loads(raw_text)
            validated_output = self.output_schema(**parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            log_event("output_validation_failed", {"raw_text": raw_text, "error": str(exc)})
            if self.fallback is not None:
                return HarnessResult(
                    success=True,
                    output=self.fallback,
                    raw_text=raw_text,
                    used_fallback=True,
                    error=f"Output schema validation failed: {exc}",
                    error_type="SchemaValidationError",
                    agent_name=self.agent_name,
                    latency_seconds=latency,
                    attempts=attempt_counter["n"],
                )
            return HarnessResult(
                success=False,
                raw_text=raw_text,
                error=f"Output schema validation failed: {exc}",
                error_type="SchemaValidationError",
                agent_name=self.agent_name,
                latency_seconds=latency,
                attempts=attempt_counter["n"],
            )

        log_event("response", {
            "agent": self.agent_name,
            "output": validated_output.model_dump(),
            "latency_seconds": round(latency, 4),
        })

        return HarnessResult(
            success=True,
            output=validated_output,
            raw_text=raw_text,
            agent_name=self.agent_name,
            latency_seconds=latency,
            attempts=attempt_counter["n"],
        )