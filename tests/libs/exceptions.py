"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Generic exceptions that help delineate Test, Infra, or Product issues.
"""

from collections import namedtuple
import inspect
import json
from typing import Any

Blame = namedtuple("Blaming", "test, infra, product")("Test", "Infra", "Product")
TestBakes = namedtuple("Reasons", "unexpected")(
    "test called an infrastructure piece in a way that was unexpected, but predictable"
)


class TestEnvironmentError(EnvironmentError):
    """Despite relation to infrastructure, this error indicates that the test(er) is missing a piece."""

    def __init__(self, message: str = None, sns: str = None):
        self.caller = caller = get_caller()
        self.at_fault = at_fault = Blame.test
        self.reason = reason = "test-supplied environment factor missing or misbehaving"
        if not (used_message := message):
            used_message = (
                f"{caller} expected certain parameters to match expectations, but failed"
                ""
            )
        if not (used_sns := sns):
            used_sns = (
                f"check the expected behavior behind {caller} and how to properly call it"
                ""
            )
        message = json.dumps(
            dict(
                reason=reason,
                message=used_message,
                suggested_next_steps=used_sns,
                at_fault=at_fault,
                caller=caller,
            )
        )
        super().__init__(message)


class TestRestrictedOperationError(PermissionError):
    """Test does not have permission to perform a specific operation against the environment."""

    def __init__(self, message: str = None, sns: str = None):
        self.caller = caller = get_caller()
        self.at_fault = at_fault = Blame.test
        self.reason = reason = "test action is hard-restricted"
        if not (used_message := message):
            used_message = "illegal call to method or code space as part of a test"
        if not (used_sns := sns):
            used_sns = "modify test code so as not to invoke this"
        message = json.dumps(
            dict(
                at_fault=at_fault,
                caller=caller,
                message=used_message,
                reason=reason,
                suggested_next_steps=used_sns,
            )
        )


class TestTypeError(TypeError):
    """A test attempted to use a type in an infrastructure piece that is not accepted."""

    __test__ = False

    def __init__(self, expected: Any = None, given: str = None, sns: str = None):
        self.caller = caller = get_caller()
        self.at_fault = at_fault = Blame.test
        self.reason = reason = TestBakes.unexpected
        if (used_sns := sns) is None:
            used_sns = "check the given type against the expected type within the call by the caller"
        message = json.dumps(
            dict(
                reason=reason,
                message=f"{caller} anticipated {str(expected)} not {type(given)}",
                at_fault=at_fault,
                caller=caller,
                suggested_next_steps=used_sns,
            )
        )
        super().__init__(message)


class TestValueError(ValueError):
    """Invalid value given that does not match the test's infrastructure expectation."""

    def __init__(self, value: str = None, message: str = None, sns: str = None):
        """Create the exception using the default message or a message given to report on the value."""
        self.caller = caller = get_caller()
        self.at_fault = at_fault = Blame.test
        self.reason = reason = TestBakes.unexpected
        if not (reported_message := message):
            reported_message = f"{caller} was incorrectly given {value}"
        if not (used_sns := sns):
            used_sns = str(
                "change the caller's value to an acceptable one or look to troubleshoot why it was rejected"
            )
        message = json.dumps(
            dict(
                reason=reason,
                message=reported_message,
                at_fault=at_fault,
                caller=caller,
                value=value,
                suggested_next_steps=used_sns,
            )
        )
        super().__init__(message)


# - helper methods
def get_caller():
    """Get the caller of the previous method call in the stack."""
    reduced_frame = namedtuple("ReducedFrame", "file, method, line_number")
    caller_frame = inspect.getouterframes(inspect.currentframe())[-2]
    return reduced_frame(
        *[getattr(caller_frame, attr) for attr in ["filename", "function", "lineno"]]
    )
