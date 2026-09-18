"""Base class every agent in the swarm inherits from.

An "agent" here is a thin, named wrapper around one LLMHarness call:
it owns the system prompt, the input/output schemas, and how to turn
validated input into a prompt string. All retry/timeout/validation/
logging behavior lives in the harness, not here -- that's the point of
having a shared harness.
"""
from __future__ import annotations

from typing import Callable, Optional, Type

from pydantic import BaseModel

import config
from harness import LLMHarness, HarnessResult
from harness.llm_clients import LLMClient, MockLLMClient, AnthropicLLMClient


def default_client() -> LLMClient:
    if config.LLM_BACKEND == "anthropic":
        return AnthropicLLMClient(model=config.LLM_MODEL)
    return MockLLMClient()


class BaseAgent:
    name: str = "base_agent"
    system_prompt: str = "You are a helpful assistant."
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]

    def __init__(self, client: Optional[LLMClient] = None, fallback: Optional[BaseModel] = None):
        self.harness = LLMHarness(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            client=client or default_client(),
            fallback=fallback,
        )

    def build_prompt(self, validated_input: BaseModel) -> str:
        raise NotImplementedError

    def run(self, raw_input: dict) -> HarnessResult:
        return self.harness.run(raw_input, self.build_prompt)
