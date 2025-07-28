"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json
import logging
from enum import Enum
from typing import Self

from pydantic import BaseModel, model_validator
from pydantic.fields import Field
from starlette.responses import Response
from starlette.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
)

from f5_ai_gateway_sdk.multipart_fields import REJECT_NAME, METADATA_NAME
from f5_ai_gateway_sdk.multipart_response import (
    MultipartResponse,
    MultipartResponseField,
)
from f5_ai_gateway_sdk.request_input import RequestInput
from f5_ai_gateway_sdk.response_output import ResponseOutput
from f5_ai_gateway_sdk.tags import Tags
from f5_ai_gateway_sdk.type_hints import Metadata


class Result(BaseModel):
    """
    Class representing the result of processing a prompt and metadata.
    This object encodes whether the request was rejected, and whether
    the prompt/response pair should be rewritten.
    """

    modified_prompt: RequestInput | None = None
    modified_response: ResponseOutput | None = None
    metadata: Metadata | None = None
    processor_result: Metadata | None = None
    tags: Tags = Tags()

    @model_validator(mode="after")
    def check_prompt_or_response(self) -> Self:
        """
        Check that a processor is not modifying prompt and response together.
        If response is present the request is in a responseStage, so modifying
        the prompt will have no impact.
        """
        if self.modified_prompt is not None and self.modified_response is not None:
            raise ValueError(
                "modified_prompt and modified_response are mutually exlusive"
            )
        return self

    @property
    def modified(self) -> bool:
        """Check if a modification exists"""
        return self.modified_prompt is not None or self.modified_response is not None

    @property
    def is_empty(self) -> bool:
        """Check if anything has been set on instance"""
        return not (
            self.metadata
            or self.modified_response
            or self.modified_prompt
            or self.processor_result
            or self.tags
        )

    def validate_allowed(self, processor_name: str, annotate: bool, modify: bool):
        """Validate modifications and annotations based on parameters"""
        if self.modified and not modify:
            logging.warning(
                "%s tried to modify request when parameters.modify was set to false, modification will be dropped",
                processor_name,
            )
            self.modified_prompt = None
            self.modified_response = None

        if bool(self.tags) and not annotate:
            logging.warning(
                "%s tried to annotate request with tags when parameters.annotate was set to false, tags will be dropped",
                processor_name,
            )
            self.tags = Tags()

    def to_response(self) -> Response:
        """
        Converts the Result object to a Starlette Response object, with the following rules:
          If the prompt was modified, the modified prompt is sent in the body along with the metadata, and
          a 200 status code is returned.
          If the prompt was not modified and a processor result (additional metadata) is set,
          the processor result is sent in the body, and a 200 status code is returned.
          If the prompt was not modified and no processor result or metadata is set, no body is sent, and
          a 204 status code is returned.

        :return: Starlette Response object
        """

        if (
            not self.metadata
            and not self.tags
            and not self.processor_result
            and not self.modified_prompt
            and not self.modified_response
        ):
            return Response(status_code=HTTP_204_NO_CONTENT)
        elif not self.metadata:
            self.metadata = Metadata()

        if self.processor_result:
            self.metadata["processor_result"] = self.processor_result
        # Likewise with tags
        if self.tags:
            self.metadata["tags"] = self.tags.to_response()

        fields = [
            convert_metadata_to_multipart_field(self.metadata),
        ]
        if self.modified_response:
            fields.append(self.modified_response.to_multipart_field())
        elif self.modified_prompt:
            fields.append(self.modified_prompt.to_multipart_field())

        return MultipartResponse(
            fields=fields,
            status_code=HTTP_200_OK,
        )


REJECT_PREFIX = "AIGW_"


class RejectCode(str, Enum):
    """Error codes available for rejects"""

    AUTHENTICATION = f"{REJECT_PREFIX}AUTHENTICATION"
    AUTHORIZATION = f"{REJECT_PREFIX}AUTHORIZATION"
    POLICY_VIOLATION = f"{REJECT_PREFIX}POLICY_VIOLATION"
    RATE_LIMIT = f"{REJECT_PREFIX}RATE_LIMIT"
    RESOURCE_AVAILABILITY = f"{REJECT_PREFIX}RESOURCE_AVAILABILITY"
    TIMEOUT = f"f{REJECT_PREFIX}TIMEOUT"
    VALIDATION = f"f{REJECT_PREFIX}VALIDATION"


class Reject(BaseModel):
    """Reject response"""

    code: RejectCode
    detail: str
    # exclude the follow fields from mode_dump_json() as they will
    # be added to the metadata field
    metadata: Metadata = Field(default=Metadata(), exclude=True)
    tags: Tags = Field(default=Tags(), exclude=True)
    processor_result: Metadata | None = None

    def is_empty(self) -> bool:
        """Compatability with Result(), always false due to required fields"""
        return False

    def to_multipart_field(self) -> MultipartResponseField:
        """Convert to response object"""
        return MultipartResponseField(name=REJECT_NAME, content=self.model_dump_json())

    def to_response(self) -> Response:
        """Return Reject as Response object"""
        if self.tags:
            self.metadata["tags"] = self.tags.to_response()
        if self.processor_result:
            self.metadata["processor_result"] = self.processor_result
        return MultipartResponse(
            fields=[
                self.to_multipart_field(),
                convert_metadata_to_multipart_field(self.metadata),
            ],
            status_code=HTTP_200_OK,
        )


def convert_metadata_to_multipart_field(meta: Metadata) -> MultipartResponseField:
    """Converts metadata dict to multipart field"""
    return MultipartResponseField(name=METADATA_NAME, content=json.dumps(meta))


__all__ = ["Result", "Reject", "RejectCode"]
