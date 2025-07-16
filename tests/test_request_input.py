"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from f5_ai_gateway_sdk.request_input import RequestInput
import pytest


@pytest.mark.parametrize(
    "content_value,should_have_null",
    [
        ("null", True),
        ('"Hello world"', False),
    ],
)
def test_maintains_content_and_excludes_tracking_fields(
    content_value, should_have_null
):
    """
    Test that messages with both null and non-null content are properly handled
    during parsing and serialization, and that no internal tracking fields
    are exposed in the serialized result.

    This verifies that the SDK properly handles:
    - Messages with null content (common in tool call scenarios)
    - Messages with regular string content
    - Additional fields (tool_calls) are persisted
    - Internal implementation details remain hidden from serialized output
    """
    data = f'{{"messages":[{{"role":"user","content":{content_value},"tool_calls":[{{"id":"call_abc"}}]}}]}}'

    parsed = RequestInput.model_validate_json(data)
    serialized = parsed.model_dump_json()

    assert ("null" in serialized) == should_have_null
    assert "tool_calls" in serialized
    assert "content_parsed_as_null" not in serialized
