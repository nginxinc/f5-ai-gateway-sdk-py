"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import base64
import pytest
from io import BytesIO
from collections.abc import Iterable

from requests_toolbelt.multipart.decoder import MultipartDecoder

from .libs.naughty_strings import NaughtyStrings
from f5_ai_gateway_sdk.multipart_fields import (
    encode_multipart_field,
    HEADER_ENCODING,
    generate_boundary,
)


class MultipartIO(BytesIO):
    def __init__(self, boundary: str):
        super().__init__()
        self.boundary = boundary
        self.content_type = f'multipart/form-data;boundary="{self.boundary}"'

    def write_iterable(self, iterable: Iterable[bytes]) -> None:
        for chunk in iterable:
            self.write(chunk)

        self.write_closing_boundary()

    def write_closing_boundary(self) -> None:
        self.write(f"--{self.boundary}--\r\n".encode(HEADER_ENCODING))
        self.flush()


def test_boundary_generation():
    boundary_size = 64
    boundary_1 = generate_boundary(boundary_size)

    assert len(boundary_1) == boundary_size, "first boundary len"

    boundary_2 = generate_boundary(boundary_size)

    assert len(boundary_2) == boundary_size
    assert boundary_1 != boundary_2, "second boundary len"


def test_boundary_generation_negative_number():
    with pytest.raises(ValueError):
        generate_boundary(-1)


def test_boundary_generation_over_seventy():
    with pytest.raises(ValueError):
        generate_boundary(71)


default_test_headers = [
    {"Content-Disposition": 'form-data; name="content"'},
    {"Content-Type": "text/plain"},
]


def assertMultipartDecodes(
    boundary: str,
    multipart: Iterable[bytes],
    content: str | Iterable[str],
):
    buffer = MultipartIO(boundary)
    with buffer:
        buffer.write_iterable(multipart)
        decoder = MultipartDecoder(
            content=buffer.getvalue(), content_type=buffer.content_type
        )
        actual = decoder.parts[0].text

        expected = "".join(content) if isinstance(content, Iterable) else content
        assert expected == actual, "multipart decode content match"


def test_encode_multipart_field_name_unicode():
    unicode_text = base64.b64decode(b"8J+QjQ==").decode("utf-8")
    headers = [{"Content-Disposition": f'form-data; name="{unicode_text}"'}]
    with pytest.raises(UnicodeEncodeError):
        list(encode_multipart_field("boundary", headers, "content"))


def test_encode_multipart_boundary_unicode():
    unicode_text = base64.b64decode(b"8J+QjQ==").decode("utf-8")
    headers = [{"Content-Disposition": 'form-data; name="content"'}]
    with pytest.raises(UnicodeEncodeError):
        list(encode_multipart_field(unicode_text, headers, "content"))


def test_encode_multipart_field_str():
    content = "\n".join(NaughtyStrings())
    boundary = "boundary"
    multipart = encode_multipart_field(boundary, default_test_headers, content)
    assertMultipartDecodes(boundary, multipart, content)


def test_encode_multipart_field_iter():
    content = NaughtyStrings()
    boundary = "boundary"
    multipart = encode_multipart_field(boundary, default_test_headers, content)
    assertMultipartDecodes(boundary, multipart, content)


def test_encode_multipart_field_with_mixed_line_breaks():
    content = "This is a wacky string\nwith mixed line breaks\r\nand some more\n\r\rI sure hope this encodes!\n"
    boundary = "boundary"
    multipart = encode_multipart_field(boundary, default_test_headers, content)
    assertMultipartDecodes(boundary, multipart, content)
