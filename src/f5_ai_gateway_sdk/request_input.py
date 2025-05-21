"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from io import StringIO

from pydantic import BaseModel

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

    content: str
    role: str = MessageRole.USER


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
