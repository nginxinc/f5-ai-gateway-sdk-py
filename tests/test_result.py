"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import pytest

from f5_ai_gateway_sdk.request_input import RequestInput
from f5_ai_gateway_sdk.response_output import ResponseOutput
from f5_ai_gateway_sdk.result import Result
from f5_ai_gateway_sdk.tags import Tags


def test_prompt_not_allowed_with_response():
    """Test that modified_prompt and modified_response cannot be used together in a Result."""
    with pytest.raises(
        ValueError,
        match="modified_prompt and modified_response are mutually exlusive",
    ):
        Result(
            modified_prompt=RequestInput(messages=[]),
            modified_response=ResponseOutput(choices=[]),
        )


@pytest.mark.parametrize(
    "name,annotate,modify,result,expected_log",
    [
        (
            "Annotate not allowed",
            False,
            False,
            Result(tags=Tags({"test": ["value"]})),
            "test_processor tried to annotate request with tags when parameters.annotate was set to false, tags will be dropped",
        ),
        ("Treat empty Tags as no annotate", False, False, Result(tags=Tags()), ""),
        (
            "Modify not allowed for prompt",
            True,
            False,
            Result(modified_prompt=RequestInput(messages=[])),
            "test_processor tried to modify request when parameters.modify was set to false, modification will be dropped",
        ),
        (
            "Modify not allowed for response",
            True,
            False,
            Result(modified_response=ResponseOutput(choices=[])),
            "test_processor tried to modify request when parameters.modify was set to false, modification will be dropped",
        ),
        (
            "Modify allowed",
            False,
            True,
            Result(modified_response=ResponseOutput(choices=[])),
            "",
        ),
        (
            "Annotate allowed",
            True,
            True,
            Result(tags=Tags(), modified_prompt=RequestInput(messages=[])),
            "",
        ),
    ],
    ids=lambda name: name,
)
def test_validate_not_allowed_parameters(
    caplog, name, annotate: bool, modify: bool, result: Result, expected_log
):
    """Test validate_allowed drops modifications or tags which have not been approved."""
    result.validate_allowed("test_processor", annotate, modify)

    if expected_log:
        assert expected_log in caplog.text
    else:
        assert len(caplog.records) == 0
    if not annotate:
        assert not bool(result.tags)
    if not modify:
        assert result.modified_prompt is None
        assert result.modified_response is None
