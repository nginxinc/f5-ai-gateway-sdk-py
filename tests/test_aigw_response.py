"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from f5_ai_gateway_sdk.request_input import MessageRole
from f5_ai_gateway_sdk.response_output import ResponseOutput

import json


CONTENT_STRING = "Everybody loves cats because cats are cute and cuddly. But what if cats were lions? What would the world be like if cats were lions?"


def test_json_object_hook_parses():
    """Test that ResponseOutput.model_validate_json correctly parses valid JSON response."""
    response_json = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": CONTENT_STRING,
                        "role": "assistant",
                    }
                }
            ]
        }
    )

    parsed_response = ResponseOutput.model_validate_json(response_json)

    assert isinstance(parsed_response, ResponseOutput)
    assert len(parsed_response.choices) == 1
    assert parsed_response.choices[0].message.content == CONTENT_STRING
    assert parsed_response.choices[0].message.role == MessageRole.ASSISTANT
