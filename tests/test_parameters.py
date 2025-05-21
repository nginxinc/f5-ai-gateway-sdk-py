"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from f5_ai_gateway_sdk.signature import (
    Signature,
    INPUT_ONLY_SIGNATURE as ANY_SIGNATURE,
)
from f5_ai_gateway_sdk.parameters import Parameters


class ValidOTELParameters(Parameters):
    one_string: str
    one_int: int
    one_float: float
    one_bool: bool
    one_string_list: list[str]
    one_string_tuple: tuple[str, str]
    one_string_set: set[str]
    one_string_dict: dict[str, str]
    one_string_nested_dict: dict[str, dict[str, str]]


class FailingStr:
    def __str__(self):
        raise Exception("Failed")


class UnsupportedOTELParameters(Parameters):
    one_string: str
    failing_str: FailingStr
    # [Signature] is not a supported type for OTEL attributes,
    # so we expect that it gets converted to a str
    str_conv_list: list[Signature] = []
    bad_conv_list: set[FailingStr]


def test_can_read_otel_attributes():
    parameters = ValidOTELParameters(
        one_string="string",
        one_int=1,
        one_float=1.0,
        one_bool=True,
        one_string_list=["string"],
        one_string_tuple=("string", "string"),
        one_string_set={"string"},
        one_string_dict={"key": "value"},
        one_string_nested_dict={"key1": {"key2": "value"}},
    )
    attributes = dict(parameters.otel_attributes())
    expected = {
        "parameters.reject": False,
        "parameters.modify": False,
        "parameters.annotate": True,
        "parameters.one_string": "string",
        "parameters.one_int": 1,
        "parameters.one_float": 1.0,
        "parameters.one_bool": True,
        "parameters.one_string_list": ["string"],
        "parameters.one_string_tuple": ["string", "string"],
        "parameters.one_string_set": ["string"],
        "parameters.one_string_dict.key": "value",
        "parameters.one_string_nested_dict.key1.key2": "value",
    }
    for k, v in expected.items():
        assert k in attributes
        assert attributes[k] == v, f"{attributes[k]} != {v}"
    assert expected == attributes


def test_unsupported_otel_attributes():
    parameters = UnsupportedOTELParameters(
        one_string="string",
        failing_str=FailingStr(),
        str_conv_list=[ANY_SIGNATURE],
        bad_conv_list={FailingStr()},
    )
    attributes = dict(parameters.otel_attributes())
    expected = {
        "parameters.reject": False,
        "parameters.modify": False,
        "parameters.annotate": True,
        "parameters.one_string": "string",
        "parameters.str_conv_list": [
            "{'required': frozenset({<SignatureField.INPUT: 'input.messages'>}), 'optional': None}"
        ],
    }
    assert expected == attributes, "otel params match"
