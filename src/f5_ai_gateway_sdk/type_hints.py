"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from __future__ import annotations
from io import StringIO
from typing import TypeVar, IO, TypeAlias
from collections.abc import MutableMapping, Mapping
from pydantic import JsonValue

from f5_ai_gateway_sdk.request_input import RequestInput
from f5_ai_gateway_sdk.response_output import ResponseOutput


from f5_ai_gateway_sdk.parameters import Parameters

Metadata: TypeAlias = dict[str, JsonValue]
"""Metadata sent along to a processor to provide context for processing."""

JSON: TypeAlias = (
    Mapping[str, "JSON"] | MutableMapping[str, "JSON"] | list["JSON"] | JsonValue
)
"""JSON-compatible data type."""

"""Metadata sent along to a processor to provide context for processing."""


StreamingPrompt = IO[str] | StringIO | None
"""Prompt text to be processed as a stream by a processor and later sent to a LLM."""


StreamingResponse = IO[str] | None
"""Response text to streamed back to the client from a LLM."""

PROMPT = TypeVar("PROMPT", bound=RequestInput | StreamingPrompt, contravariant=True)
"""Generic type variable for a prompt or streaming prompt."""

RESPONSE = TypeVar(
    "RESPONSE", bound=ResponseOutput | StreamingResponse, contravariant=True
)
"""Generic type variable for a response or streaming response."""

PARAMS = TypeVar("PARAMS", bound=Parameters, contravariant=True)
"""Generic type variable for parameters sent to a processor."""


__all__ = [
    "JSON",
    "Metadata",
    "StreamingPrompt",
    "StreamingResponse",
    "PROMPT",
    "RESPONSE",
    "PARAMS",
]
