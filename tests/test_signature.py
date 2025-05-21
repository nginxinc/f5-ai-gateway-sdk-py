"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json
import pytest


from f5_ai_gateway_sdk.signature import (
    Signature,
    BOTH_SIGNATURE,
    RESPONSE_ONLY_SIGNATURE,
    RESPONSE_AND_PROMPT_SIGNATURE,
    INPUT_ONLY_SIGNATURE,
    BOTH_RESPONSE_PROMPT_SIGNATURE,
)

test_signatures = [
    BOTH_RESPONSE_PROMPT_SIGNATURE,
    BOTH_SIGNATURE,
    RESPONSE_ONLY_SIGNATURE,
    RESPONSE_AND_PROMPT_SIGNATURE,
    INPUT_ONLY_SIGNATURE,
]


@pytest.mark.parametrize("signature", test_signatures)
def test_can_serialize_to_json(signature: Signature):
    """
    Test that the various signature types can be serialized to JSON.

    Parameters:
        signature (Signature): The signature to test.
    """

    expected_keys = ["type", "required"]

    json_content = json.dumps(signature.to_list())
    assert isinstance(json_content, str)
    actual = json.loads(json_content)
    for field in actual:
        for key, _ in field.items():
            assert key in expected_keys

        for key in expected_keys:
            signature_value = field.get(key, None)
            assert signature_value is not None


@pytest.mark.parametrize("signature", test_signatures)
def test_supports_direction(signature: Signature):
    """
    Test that the signature correctly reports if it supports either input or response.

    Parameters:
        signature (Signature): The signature to test.
    """

    json_content = json.dumps(signature.to_list())
    supports_input = "input." in json_content
    supports_response = "response." in json_content
    assert signature.supports_input() == supports_input
    assert signature.supports_response() == supports_response
