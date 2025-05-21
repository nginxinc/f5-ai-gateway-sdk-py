"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import secrets
import string
from collections.abc import Iterable, Generator

DEFAULT_ENCODING = "utf-8"
HEADER_ENCODING = "us-ascii"

ALLOWED_ENCODINGS = frozenset(["utf-8", "us-ascii", "latin-1", "iso-8859-1"])

INPUT_NAME = "input.messages"
INPUT_PARAMETERS_NAME = "input.parameters"
RESPONSE_NAME = "response.choices"
RESPONSE_PARAMETERS_NAME = "response.parameters"
METADATA_NAME = "metadata"
REJECT_NAME = "reject"

REQUIRED_MULTIPART_FIELDS = frozenset([METADATA_NAME])
OPTIONAL_MULTIPART_FIELDS = frozenset(
    [
        INPUT_NAME,
        RESPONSE_NAME,
        INPUT_PARAMETERS_NAME,
        RESPONSE_PARAMETERS_NAME,
        REJECT_NAME,
    ]
)

RNG_SOURCE = secrets.SystemRandom()


def generate_boundary(length: int) -> str:
    """
    Generate a random boundary string for a multipart/form-data response.
    :param length: length of string to be generated
    :return: string of random alphanumeric characters
    """

    if length < 1:
        raise ValueError("Boundary length must be greater than 0 characters")
    if length > 70:
        raise ValueError("Boundary length must be less than 70 characters")

    return "".join(RNG_SOURCE.choices(string.ascii_letters + string.digits, k=length))


def encode_multipart_field(
    boundary: str, headers: Iterable[dict[str, str]], content: str | Iterable[str]
) -> Generator[bytes, None, None]:
    """
    Encode a field using the multipart/form-data MIME format.

    :param boundary: Boundary string used to separate fields.
    :param headers: list of headers to be sent with the content.
    :param content: Content to be sent encoded as multipart.
    """
    if not boundary:
        raise ValueError("boundary must be provided")
    if not content:
        raise ValueError("content must be provided")

    # Write out the boundary and headers before sending the content
    yield f"--{boundary}\r\n".encode(HEADER_ENCODING)
    for header in headers:
        for key, value in header.items():
            yield f"{key}: {value}\r\n".encode(HEADER_ENCODING)
    yield b"\r\n"

    if isinstance(content, str):
        yield content.encode(DEFAULT_ENCODING)
    elif hasattr(content, "__iter__"):
        for line in content:
            yield line.encode(DEFAULT_ENCODING)
    else:
        raise ValueError("content must be a string or an iterable of strings")

    yield b"\r\n"


def multipart_field_order(field: str) -> int:
    """key to order fields by where metadata is always last"""
    return {INPUT_NAME: 0, RESPONSE_NAME: 1, REJECT_NAME: 2, METADATA_NAME: 3}.get(
        field, 0
    )


__all__ = [
    "DEFAULT_ENCODING",
    "HEADER_ENCODING",
    "ALLOWED_ENCODINGS",
    "INPUT_NAME",
    "INPUT_PARAMETERS_NAME",
    "RESPONSE_NAME",
    "RESPONSE_PARAMETERS_NAME",
    "METADATA_NAME",
    "REQUIRED_MULTIPART_FIELDS",
    "OPTIONAL_MULTIPART_FIELDS",
    "RNG_SOURCE",
    "generate_boundary",
    "encode_multipart_field",
]
