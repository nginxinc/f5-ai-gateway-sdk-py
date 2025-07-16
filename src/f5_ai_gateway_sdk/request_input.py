"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from io import StringIO

from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_serializer,
    PrivateAttr,
)
from pydantic.functional_validators import model_validator

from f5_ai_gateway_sdk.multipart_fields import INPUT_NAME
from f5_ai_gateway_sdk.multipart_response import MultipartResponseField


class MessageRole(str):
    """
    Enum for the fields that can be required in a processor signature.

    Available values:
        - ``USER``: Represents the user role in the conversation.
        - ``SYSTEM``: Represents the system role responsible for managing the conversation context.
        - ``ASSISTANT``: Represents the assistant role, typically used for responses from the AI.
        - ``TOOL``: Represents an external tool or resource invoked during the conversation.
    """

    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"
    TOOL = "tool"
    DEVELOPER = "developer"


class Message(BaseModel):
    """
    Represents a message with a role and content.

    :param content: The text content of the message.
    :param role: The role of the message, which can be one of the values from MessageRole enum. Default is USER.
    """

    __autoclass_content__ = "class"
    model_config = ConfigDict(extra="allow")

    content: str
    role: str = MessageRole.USER
    _content_parsed_as_null: bool = PrivateAttr(default=False)

    # messages may have null content when
    # containing tool_calls
    # this tracks that case in order to allow
    # returning in the same format without the
    # SDK user needing to handle None on content
    @model_validator(mode="before")
    @classmethod
    def track_null_content(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("content") is None:
            # Store this info in the data itself so it survives validation
            data["__content_parsed_as_null__"] = True
            data["content"] = ""
        return data

    @model_validator(mode="after")
    def set_null_flag(self) -> Self:
        # Check if the original data indicated null content
        if hasattr(self, "__content_parsed_as_null__") or getattr(
            self, "__content_parsed_as_null__", False
        ):
            self._content_parsed_as_null = True
            # Remove the temporary tracking field now that we've set the private attribute
            if hasattr(self, "__content_parsed_as_null__"):
                delattr(self, "__content_parsed_as_null__")
        return self

    @field_serializer("content")
    def serialize_content(self, content: str):
        if self._content_parsed_as_null and len(content) == 0:
            return None
        return content


class RequestInput(BaseModel):
    """
    Represents a collection of ``Message`` objects.

    :param messages: A list of ``Message`` objects representing the input messages.

    Example::

        {
            "messages": [
                {
                    "content": "What is the capital of France?",
                    "role": "user"
                },
                {
                    "content": "Only answer questions about geography",
                    "role": "system"
                }
            ]
        }
    """

    __autoclass_content__ = "class"
    model_config = ConfigDict(extra="allow")

    messages: list[Message]

    def to_multipart_field(self) -> MultipartResponseField:
        """Convert to response object"""
        return MultipartResponseField(name=INPUT_NAME, content=self.model_dump_json())

    def stream(self, roles: list[MessageRole] | None = None) -> StringIO:
        """
        Creates a stream of message contents, filtered by roles if provided.

        :meta private:

        :param roles: An optional list of roles to filter the messages by

        :return: A stream of concatenated message contents.
        """

        if roles is None:
            roles = []
        appender = StringIO()
        for message in self.messages:
            if roles and message.role not in roles:
                continue
            appender.write(message.content + "\n")
        return appender

    def concatenate(self, roles: list[MessageRole] | None = None) -> str:
        """
        Concatenates the message contents, filtered by roles if provided.

        :param roles: An optional list of roles to filter the messages by

        :return: A concatenated string of message contents.
        """
        return self.stream(roles).getvalue()

    def hash(self) -> int:
        """Return hash of model"""
        return hash(self.model_dump_json())


__all__ = ["Message", "RequestInput", "MessageRole"]
