"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from f5_ai_gateway_sdk.request_input import RequestInput, MessageRole
from pydantic import ValidationError

import json
import pytest


CONTENT_STRING = "Everybody loves cats because cats are cute and cuddly. But what if cats were lions? What would the world be like if cats were lions?"


def test_json_object_hook_parses():
    input_json = json.dumps({"messages": [{"content": CONTENT_STRING}]})

    parsed_input = RequestInput.model_validate_json(input_json)

    assert isinstance(parsed_input, RequestInput)
    assert len(parsed_input.messages) == 1
    assert parsed_input.messages[0].content == CONTENT_STRING
    assert parsed_input.messages[0].role == MessageRole.USER


def test_json_object_hook_allows_role():
    input_json = json.dumps(
        {
            "messages": [
                {
                    "content": CONTENT_STRING,
                    "role": "system",
                }
            ]
        }
    )

    parsed_input = RequestInput.model_validate_json(input_json)

    assert isinstance(parsed_input, RequestInput)
    assert len(parsed_input.messages) == 1

    assert parsed_input.messages[0].role == MessageRole.SYSTEM


def test_json_object_hook_allows_arbitrary_role():
    CUSTOM_ROLE = "friend"
    input_json = json.dumps(
        {
            "messages": [
                {
                    "content": CONTENT_STRING,
                    "role": CUSTOM_ROLE,
                }
            ]
        }
    )

    parsed_input = RequestInput.model_validate_json(input_json)

    assert isinstance(parsed_input, RequestInput)
    assert len(parsed_input.messages) == 1

    assert parsed_input.messages[0].role == CUSTOM_ROLE


def test_json_object_invalid():
    input_json = json.dumps({"messages": [{"content": CONTENT_STRING}]})[1:]

    with pytest.raises(ValidationError):
        RequestInput.model_validate_json(input_json)
