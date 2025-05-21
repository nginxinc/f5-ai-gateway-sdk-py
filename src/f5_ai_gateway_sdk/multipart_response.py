"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from collections.abc import Iterator

from pydantic.main import BaseModel
from starlette.responses import StreamingResponse as HttpStreamingResponse


from f5_ai_gateway_sdk.multipart_fields import (
    DEFAULT_ENCODING,
    generate_boundary,
    encode_multipart_field,
    HEADER_ENCODING,
    multipart_field_order,
)


class MultipartResponseField(BaseModel):
    """Field name and content for multipart response"""

    name: str
    content: str
    content_type: str = "application/json"


class MultipartResponse(HttpStreamingResponse):
    """
    Response object that encodes a prompt and metadata as multipart/form-data.
    """

    BOUNDARY_SIZE = 64
    """Size of the boundary string in characters"""
    TEXT_CONTENT_TYPE = f"text/plain;charset={DEFAULT_ENCODING}"
    """Plain text content type with character set specified"""
    JSON_CONTENT_TYPE = "application/json"
    """Content type of the prompt/response body (typically prompt or prompt response)"""

    def __init__(
        self,
        status_code: int,
        fields: list[MultipartResponseField] = [],
    ):
        """
        Create a new MultipartResponse object.
        :param metadata: metadata for the prompt/response
        :param status_code: HTTP status code
        :param modified_prompt: prompt text to be processed by a processor and later sent to a LLM
        :param modified_response: response text to be sent back to the client from a LLM
        """
        if status_code < 1 or status_code > 599:
            raise ValueError("Invalid HTTP status code")
        if not any(f for f in fields if f.name == "metadata"):
            raise ValueError("Metadata is required")

        self.boundary = generate_boundary(self.BOUNDARY_SIZE)
        """Boundary string used to separate parts of the multipart/form-data response"""

        self.media_type = (
            f'multipart/form-data;charset={DEFAULT_ENCODING};boundary="{self.boundary}"'
        )
        """Media type of the response content that indicates the boundary string"""

        content = self.build_content(fields)

        super().__init__(
            content=content,
            status_code=status_code,
            media_type=self.media_type,
            headers={"Content-Type": self.media_type},
        )

    @staticmethod
    def build_headers(field_name: str, content_type: str) -> list[dict[str, str]]:
        return [
            {"Content-Disposition": f'form-data; name="{field_name}"'},
            {"Content-Type": content_type},
        ]

    def build_content(
        self,
        fields: list[MultipartResponseField],
    ) -> Iterator[bytes]:
        """
        Build the content of the multipart response by linking together the prompt, response, and
        metadata as byte streams.

        :param prompt: optional prompt
        :param response: optional response
        :param metadata: required metadata
        :return: byte iterator with the content of the multipart response
        """

        # ensure that metadata is last
        fields.sort(key=lambda f: multipart_field_order(f.name))

        for f in fields:
            prompt_headers = MultipartResponse.build_headers(f.name, f.content_type)
            field_content = encode_multipart_field(
                self.boundary, prompt_headers, f.content
            )
            for chunk in field_content:
                yield chunk

        yield f"--{self.boundary}--\r\n".encode(HEADER_ENCODING)


__all__ = ["MultipartResponse", "MultipartResponseField"]
