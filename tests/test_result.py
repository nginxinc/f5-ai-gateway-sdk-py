"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import pytest

from f5_ai_gateway_sdk.request_input import RequestInput
from f5_ai_gateway_sdk.response_output import ResponseOutput
from f5_ai_gateway_sdk.result import Result


def test_prompt_not_allowed_with_response():
    with pytest.raises(
        ValueError,
        match="modified_prompt and modified_response are mutually exlusive",
    ):
        Result(
            modified_prompt=RequestInput(messages=[]),
            modified_response=ResponseOutput(choices=[]),
        )
