"""Base schema class shared by all agent input/output models.

Every agent defines its own pydantic models (see models/*.py) that
subclass HarnessSchema. The harness validates raw dict input against
the agent's declared input schema *before* calling the LLM, and
validates the parsed LLM output against the declared output schema
*after* calling the LLM -- so a malformed prompt never reaches the
model, and a malformed / hallucinated response never reaches the rest
of the system.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HarnessSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
