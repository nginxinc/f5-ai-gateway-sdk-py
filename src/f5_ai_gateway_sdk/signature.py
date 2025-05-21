"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from f5_ai_gateway_sdk.multipart_fields import INPUT_NAME, RESPONSE_NAME


class SignatureField(Enum):
    """
    Enum for the fields that can be required in a processor signature.

    Available values:
        - ``INPUT``: The input stage.
        - ``RESPONSE``: The response stage.
    """

    INPUT = INPUT_NAME
    RESPONSE = RESPONSE_NAME


@dataclass
class Signature:
    """
    Signature for a processor that defines the required input and response fields for a processor.
    These values are used to inform the gateway of what inputs are acceptable.

    The following predefined Signatures cover most common use cases.
        - ``INPUT_ONLY_SIGNATURE``
        - ``RESPONSE_ONLY_SIGNATURE``
        - ``RESPONSE_AND_PROMPT_SIGNATURE``
        - ``BOTH_SIGNATURE``
        - ``BOTH_RESPONSE_PROMPT_SIGNATURE``

    :param required: A set of ``SignatureField`` objects representing the required input fields.
    :param optional: A set of ``SignatureField`` objects representing the optional input fields.
    """

    required: set[SignatureField] | frozenset[SignatureField] | None = None
    optional: set[SignatureField] | frozenset[SignatureField] | None = None

    def __post_init__(self):
        if self.required is None and self.optional is None:
            raise ValueError("Signature must have at least one of required or optional")

        # Assure that the fields are immutable
        self.required = frozenset(self.required) if self.required else None
        self.optional = frozenset(self.optional) if self.optional else None

    def to_list(self) -> list:
        """
        Return a list of dicts that represent the fields required by this signature
        """
        _list: list[Any] = []
        if self.required:
            _list.extend([{"type": f.value, "required": True} for f in self.required])
        if self.optional:
            _list.extend([{"type": f.value, "required": False} for f in self.optional])

        return _list

    def __str__(self):
        required = ", ".join(f.value for f in self.required) if self.required else None
        optional = ", ".join(f.value for f in self.optional) if self.optional else None
        return f"Signature(required={required}, optional={optional})"

    def supports_input(self) -> bool:
        """
        Returns True if the signature requires works with input requests.

        Returns:
            bool: Whether the signature works with input requests.
        """
        return self.__supports_direction("input")

    def supports_response(self) -> bool:
        """
        Returns True if the signature requires works with response requests.

        Returns:
            bool: Whether the signature works with response requests.
        """
        return self.__supports_direction("response")

    def __supports_direction(self, direction: str) -> bool:
        supported = False
        if self.required is not None:
            supported = any(f.value.startswith(f"{direction}.") for f in self.required)
        if not supported and self.optional is not None:
            supported = any(f.value.startswith(f"{direction}.") for f in self.optional)
        return supported


class NonValidatingSignature(Signature):
    """
    A signature that does not validate the fields in the signature.
    """

    def __post_init__(self):
        super().__post_init__()


# The following are signatures for common processor combinations


INPUT_ONLY_SIGNATURE = Signature(required={SignatureField.INPUT})
"""Signature for a processor that only requires input content (prompt)"""
RESPONSE_ONLY_SIGNATURE = Signature(required={SignatureField.RESPONSE})
"""Signature for a processor that only requires response content (prompt response)"""
RESPONSE_AND_PROMPT_SIGNATURE = Signature(
    required={SignatureField.INPUT, SignatureField.RESPONSE}
)
"""Signature for a processor that requires prompt (input) content for response content"""
BOTH_SIGNATURE = Signature(optional={SignatureField.INPUT, SignatureField.RESPONSE})
"""Signature for a processor that requires either input content or response content"""
BOTH_RESPONSE_PROMPT_SIGNATURE = Signature(
    required={SignatureField.INPUT},
    optional={SignatureField.RESPONSE},
)
"""Signature for a processor that requires input content and response content with a prompt"""

#: All predefined signatures for common processor combinations.
ALL_PREDEFINED_SIGNATURES = [
    INPUT_ONLY_SIGNATURE,
    RESPONSE_ONLY_SIGNATURE,
    RESPONSE_AND_PROMPT_SIGNATURE,
    BOTH_SIGNATURE,
    BOTH_RESPONSE_PROMPT_SIGNATURE,
]

__all__ = [
    "INPUT_ONLY_SIGNATURE",
    "RESPONSE_ONLY_SIGNATURE",
    "RESPONSE_AND_PROMPT_SIGNATURE",
    "BOTH_SIGNATURE",
    "BOTH_RESPONSE_PROMPT_SIGNATURE",
    "ALL_PREDEFINED_SIGNATURES",
    "Signature",
    "SignatureField",
]
