"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json
import unittest
from io import BytesIO

from parameterized import parameterized
import pytest

from f5_ai_gateway_sdk.request_input import RequestInput, Message
from f5_ai_gateway_sdk.multipart_fields import (
    INPUT_NAME,
    RESPONSE_NAME,
    METADATA_NAME,
)
from f5_ai_gateway_sdk.multipart_response import (
    MultipartResponse,
)
from f5_ai_gateway_sdk.response_output import Choice, ResponseOutput
from f5_ai_gateway_sdk.result import convert_metadata_to_multipart_field

from .multipart_decoder_helper import MultipartDecoderHelper

PROMPT_FIELD = bytes(INPUT_NAME, "us-ascii")
RESPONSE_FIELD = bytes(RESPONSE_NAME, "us-ascii")
METADATA_FIELD = bytes(METADATA_NAME, "us-ascii")
TEST_MESSAGE = Message(content="Are cats better than dogs?")


@pytest.mark.usefixtures("class_data_loader")
class MultipartResponseTest(unittest.IsolatedAsyncioTestCase):
    def test_consequence_invalid_status_code(self):
        """Verify that the status code of 4xx send to MultipartResponse raises."""
        metadata = {
            "user_id": "1234",
            "processor_result": {"processor": "testing"},
            "tags": {"status": ["bad status"]},
        }

        status_code = 600

        with pytest.raises(ValueError) as err:
            MultipartResponse(
                fields=[convert_metadata_to_multipart_field(metadata)],
                status_code=status_code,
            )
        self.assertIn("Invalid HTTP status code", err.value.args)

    def test_consequence_undefined_metadata(self):
        """Verify, as far as render_multipart is, that a default metadata raises."""

        with pytest.raises(ValueError) as err:
            # noinspection PyTypeChecker
            MultipartResponse(status_code=200)
        self.assertIn("Metadata is required", err.value.args)

    @parameterized.expand(
        [
            (
                [
                    RequestInput(messages=[TEST_MESSAGE]).to_multipart_field(),
                    ResponseOutput(
                        choices=[Choice(message=Message(content="Yes they are"))]
                    ).to_multipart_field(),
                ],
                {
                    "user_id": "12345",
                    "processor_result": {"processor": "test"},
                    "tags": ["test", "canine"],
                },
            ),
            (
                [RequestInput(messages=[TEST_MESSAGE]).to_multipart_field()],
                {"user_id": "54321", "processor_result": {"processor": "test2"}},
            ),
            (
                [RequestInput(messages=[TEST_MESSAGE]).to_multipart_field()],
                {"user_id": "54321", "processor_result": {"processor": "test2"}},
            ),
            (
                [
                    RequestInput(messages=[TEST_MESSAGE]).to_multipart_field(),
                ],
                {"processor": "test2"},
            ),
            (
                [
                    RequestInput(messages=[TEST_MESSAGE]).to_multipart_field(),
                ],
                {},
            ),
        ]
    )
    async def test_render_multipart(self, fields, metadata):
        expected_response_metadata = metadata.copy()
        fields.append(convert_metadata_to_multipart_field(metadata))

        multipart_response = MultipartResponse(
            fields=fields,
            status_code=200,
        )

        content = await MultipartResponseTest.buffer_response(multipart_response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=multipart_response.headers["Content-Type"]
        )

        def assert_multipart_field(field_name, expected_value, content_type):
            if expected_value is None:
                self.assertEqual(False, multipart.has(field_name))
            else:
                self.assertEqual(True, multipart.has(field_name))
                multipart_field = multipart.get(field_name)
                self.assertIsNotNone(multipart_field)
                expected_content_disposition = f'form-data; name="{field_name}"'
                self.assertEqual(
                    expected_content_disposition, multipart_field.content_disposition()
                )
                self.assertEqual(content_type, multipart_field.content_type())
                self.assertEqual(expected_value, multipart_field.content)

        for f in fields:
            assert_multipart_field(
                f.name,
                f.content,
                f.content_type,
            )
        assert_multipart_field(
            field_name=METADATA_NAME,
            expected_value=json.dumps(expected_response_metadata),
            content_type=MultipartResponse.JSON_CONTENT_TYPE,
        )
        self.assertIsNotNone(multipart.metadata)
        response_metadata = multipart.metadata.as_json()

        self.assertEqual(expected_response_metadata, response_metadata)
        self.assertEqual(
            multipart.field_order[-1], METADATA_NAME, "metadata should be last field"
        )

    @staticmethod
    async def buffer_response(response: MultipartResponse) -> bytes:
        buffer = BytesIO()
        async for chunk in response.body_iterator:
            buffer.write(chunk)

        return buffer.getvalue()
