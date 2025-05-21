"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json
from collections.abc import Iterable

from email.message import Message

from requests.structures import CaseInsensitiveDict
from requests_toolbelt import MultipartDecoder
from requests_toolbelt.multipart.decoder import BodyPart

from f5_ai_gateway_sdk.multipart_fields import (
    HEADER_ENCODING,
    INPUT_NAME,
    INPUT_PARAMETERS_NAME,
    RESPONSE_NAME,
    RESPONSE_PARAMETERS_NAME,
    METADATA_NAME,
    DEFAULT_ENCODING,
)
from f5_ai_gateway_sdk.type_hints import JSON


class FieldValue:
    def __init__(self, part: BodyPart):
        self.encoding = part.encoding if part.encoding else DEFAULT_ENCODING
        self.content = part.content.decode(self.encoding)
        self.headers = CaseInsensitiveDict()
        for key, value in part.headers.items():
            self.headers[key.decode(HEADER_ENCODING)] = value.decode(HEADER_ENCODING)

    def get_required_header(self, header_name: str) -> str:
        header = self.headers.get(header_name)
        if not header:
            raise ValueError(f"{header_name} header is not present")
        return header

    def content_disposition(self) -> str:
        return self.get_required_header("Content-Disposition")

    def content_type(self) -> str:
        return self.get_required_header("Content-Type")

    def as_json(self) -> JSON:
        return json.loads(self.content)


class MultipartDecoderHelper:
    def __init__(self, content, content_type):
        super().__init__()
        self.__fields: dict[str, FieldValue] = {}
        self.__field_order: list[str] = []
        decoder = MultipartDecoder(content, content_type)
        self.add_parts_by_name(decoder.parts)

    def add_parts_by_name(self, parts: Iterable[BodyPart]):
        for part in parts:
            content_disposition = part.headers[b"Content-Disposition"]
            if not content_disposition:
                raise ValueError("Content-Disposition header is required")
            message = Message()
            message.add_header(
                "Content-Disposition", content_disposition.decode(HEADER_ENCODING)
            )
            name = message.get_param(
                param="name", unquote=True, header="Content-Disposition"
            )
            if not name:
                raise ValueError(
                    "Content-Disposition header must have a name parameter"
                )
            self.__fields[name] = FieldValue(part)
            self.__field_order.append(name)

    @property
    def prompt(self) -> FieldValue | None:
        return self.__fields.get(INPUT_NAME)

    @property
    def prompt_parameters(self) -> FieldValue | None:
        return self.__fields.get(INPUT_PARAMETERS_NAME)

    @property
    def response(self) -> FieldValue | None:
        return self.__fields.get(RESPONSE_NAME)

    @property
    def response_parameters(self) -> FieldValue | None:
        return self.__fields.get(RESPONSE_PARAMETERS_NAME)

    @property
    def metadata(self) -> FieldValue | None:
        return self.__fields.get(METADATA_NAME)

    @property
    def field_order(self) -> list[str]:
        return self.__field_order

    def get(self, key: str) -> FieldValue | None:
        return self.__fields.get(key)

    def has(self, key: str) -> bool:
        return key in self.__fields

    def has_prompt(self) -> bool:
        return INPUT_NAME in self.__fields

    def has_prompt_parameters(self) -> bool:
        return INPUT_PARAMETERS_NAME in self.__fields

    def has_response(self) -> bool:
        return RESPONSE_NAME in self.__fields

    def has_response_parameters(self) -> bool:
        return RESPONSE_PARAMETERS_NAME in self.__fields

    def has_metadata(self) -> bool:
        return METADATA_NAME in self.__fields
