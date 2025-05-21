"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from pydantic import BaseModel

from f5_ai_gateway_sdk.multipart_fields import RESPONSE_NAME
from f5_ai_gateway_sdk.multipart_response import MultipartResponseField

from f5_ai_gateway_sdk.request_input import Message


class Choice(BaseModel):
    """
    Represents a choice returned from an upstream.

    :param message: The ``Message`` object associated with the choice.
    """

    __autoclass_content__ = "class"

    message: Message


class ResponseOutput(BaseModel):
    """
    Represents a collection of ``Message`` objects.

    :param choices: A list of ``Choice`` objects.

    Example::

        {
            "choices": [
                {
                    "message:"
                        {
                            "content": "The capital of France is Paris.",
                            "role": "assistant",
                        }
                },
            ]
        }
    """

    __autoclass_content__ = "class"

    choices: list[Choice]
    """A list of ``Choice`` objects."""

    def to_multipart_field(self) -> MultipartResponseField:
        """Convert to response object"""
        return MultipartResponseField(
            name=RESPONSE_NAME, content=self.model_dump_json()
        )

    def hash(self) -> int:
        """Return hash of model"""
        return hash(self.model_dump_json())


__all__ = ["Choice", "ResponseOutput"]
