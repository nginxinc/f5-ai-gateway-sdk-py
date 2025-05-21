"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json

from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_415_UNSUPPORTED_MEDIA_TYPE,
)

from f5_ai_gateway_sdk.multipart_fields import INPUT_NAME, RESPONSE_NAME


class ProcessorError(Exception):
    """
    Error has occurred during processing of either the ``input.content`` or ``response.content``.

    :param status_code: HTTP status code
    :param detail: Error message
    :param messages: Optional list of error messages
    """

    status_code: int
    detail: str
    messages: list[str] = []

    def __init__(
        self, status_code: int, detail: str, messages: list[str] | None = None
    ):
        self.status_code = status_code
        self.detail = detail
        if messages is not None:
            self.messages = messages
        super().__init__(detail)

    def json_error(self):
        if self.messages and len(self.messages) > 0:
            json_error = {"detail": self.detail, "messages": self.messages}
        else:
            json_error = {"detail": self.detail}
        return json.dumps(json_error)


class UnexpectedContentTypeError(ProcessorError):
    def __init__(self, detail: str):
        super().__init__(status_code=HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail)


class InvalidEncoding(ProcessorError):
    def __init__(self, detail):
        super().__init__(status_code=HTTP_400_BAD_REQUEST, detail=detail)


class InvalidMultipartFields(ProcessorError):
    def __init__(self, detail):
        super().__init__(status_code=HTTP_400_BAD_REQUEST, detail=detail)


class MissingPromptAndResponseError(ProcessorError):
    def __init__(
        self,
        detail=f"{INPUT_NAME} (prompt) and {RESPONSE_NAME} (response) fields are missing - "
        "at least one is required",
    ):
        super().__init__(status_code=HTTP_400_BAD_REQUEST, detail=detail)


class MissingMultipartFieldError(ProcessorError):
    def __init__(self, field_name: str):
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST, detail=f"{field_name} part is missing"
        )


class MultipartParseError(ProcessorError):
    def __init__(
        self,
        status_code: int = HTTP_400_BAD_REQUEST,
        detail: str = "Unable to parse multipart form field",
        messages: list[str] | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail, messages=messages)


class MetadataParseError(MultipartParseError):
    def __init__(
        self,
        detail="invalid metadata submitted",
        messages: list[str] | None = None,
    ):
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST, detail=detail, messages=messages
        )


class PromptParseError(MultipartParseError):
    def __init__(
        self,
        detail="invalid prompt field submitted",
        messages: list[str] | None = None,
    ):
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST, detail=detail, messages=messages
        )


class ResponseParseError(MultipartParseError):
    def __init__(
        self,
        detail="invalid response field submitted",
        messages: list[str] | None = None,
    ):
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST, detail=detail, messages=messages
        )


class ParametersParseError(MultipartParseError):
    def __init__(
        self,
        detail="invalid parameters submitted",
        messages: list[str] | None = None,
    ):
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST, detail=detail, messages=messages
        )


class ProcessExecutionError(ProcessorError):
    """
    Error while a processor executes process per contractual agreement.

    :param detail: Error message
    """

    def __init__(self, detail="problem executing processor implementation"):
        super().__init__(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class ResponseObjectError(ProcessorError):
    def __init__(self, detail="problem creating response object"):
        super().__init__(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class ParamsJsonDecodeError(ProcessorError):
    def __init__(
        self,
        detail="failed to decode parameters object",
        messages: list[str] | None = None,
    ):
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST, detail=detail, messages=messages
        )


class InvalidParamsError(ProcessorError):
    def __init__(
        self,
        detail="invalid parameters provided",
        messages: list[str] | None = None,
    ):
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST, detail=detail, messages=messages
        )


__all__ = [
    "ProcessorError",
    "UnexpectedContentTypeError",
    "InvalidEncoding",
    "InvalidMultipartFields",
    "MissingPromptAndResponseError",
    "MissingMultipartFieldError",
    "MultipartParseError",
    "MetadataParseError",
    "PromptParseError",
    "ResponseParseError",
    "ParametersParseError",
    "ProcessExecutionError",
    "ResponseObjectError",
]
