"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json
import unittest
from io import BytesIO
from typing import Any
from collections.abc import Iterable, Mapping

import pytest
from parameterized import parameterized
from requests_toolbelt import MultipartEncoder
from starlette.datastructures import FormData, Headers
from starlette.requests import Request
from starlette.responses import (
    Response as HttpResponse,
)
from starlette.responses import (
    StreamingResponse as HttpStreamingResponse,
)
from starlette.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_415_UNSUPPORTED_MEDIA_TYPE,
)
from starlette.types import Receive

from f5_ai_gateway_sdk.errors import ProcessorError
from f5_ai_gateway_sdk.multipart_fields import (
    DEFAULT_ENCODING,
    INPUT_NAME,
    INPUT_PARAMETERS_NAME,
    METADATA_NAME,
    RESPONSE_NAME,
)
from f5_ai_gateway_sdk.multipart_response import MultipartResponse
from f5_ai_gateway_sdk.parameters import DefaultParameters
from f5_ai_gateway_sdk import Processor, Result, Reject, RejectCode, Tags
from f5_ai_gateway_sdk.request_input import Message, RequestInput
from f5_ai_gateway_sdk.response_output import ResponseOutput
from f5_ai_gateway_sdk.signature import (
    ALL_PREDEFINED_SIGNATURES,
    BOTH_RESPONSE_PROMPT_SIGNATURE,
    BOTH_SIGNATURE,
    INPUT_ONLY_SIGNATURE,
    RESPONSE_AND_PROMPT_SIGNATURE,
    RESPONSE_ONLY_SIGNATURE,
    Signature,
)
from f5_ai_gateway_sdk.type_hints import (
    Metadata,
    StreamingPrompt,
    StreamingResponse,
)

from .multipart_decoder_helper import MultipartDecoderHelper

FAKE_NAME = "test"
FAKE_VERSION = "1"
FAKE_NAMESPACE = "testing"
APP_DETAILS = {"version": "1.0.0"}
TEST_MESSAGE = Message(content="Are cats better than dogs?")
TEST_REQ_INPUT = RequestInput(messages=[TEST_MESSAGE])


def fake_processor(
    result: Result | Reject | None = None, a_signature: Signature = BOTH_SIGNATURE
) -> Processor:
    class FakeProcessor(Processor):
        def __init__(self, name: str, namespace: str, version: str):
            super().__init__(
                prompt_class=RequestInput,
                response_class=ResponseOutput,
                name=name,
                namespace=namespace,
                version=version,
                signature=a_signature,
                app_details=APP_DETAILS,
            )

        def process(
            self,
            prompt: RequestInput,
            response: ResponseOutput,
            metadata: Metadata,
            parameters: DefaultParameters,
            request: Request,
        ) -> Result | Reject:
            return result or Result()

    return FakeProcessor(FAKE_NAME, FAKE_NAMESPACE, FAKE_VERSION)


class MinimalFakeProcessor(Processor):
    def process():
        return Result()


def fake_request(
    method: str,
    headers: Mapping[str, str] | None = None,
    receive: Receive | None = None,
) -> Request:
    scope = {
        "type": "http",
        "path": f"/execute/{FAKE_NAMESPACE}/{FAKE_NAME.lower()}",
        "method": method,
        "path_params": {"command": "execute"},
    }
    if receive is None:
        request = Request(scope=scope)
    else:
        request = Request(scope=scope, receive=receive)

    request._headers = Headers(headers)

    return request


def fake_multipart_request(
    prompt: RequestInput | StreamingPrompt | None = None,
    response: ResponseOutput | StreamingResponse | None = None,
    metadata: Metadata | None = None,
    parameters: Mapping[str, Any] | None = None,
    with_filenames: bool = False,
) -> Request:
    boundary = "boundary"
    encoding = "utf-8"

    fields = {}
    if metadata:
        metadata_json = json.dumps(metadata)
        filename = "metadata.json" if with_filenames else None
        fields[METADATA_NAME] = (filename, metadata_json, "application/json")
    if prompt:
        filename = "prompt.txt" if with_filenames else None
        fields[INPUT_NAME] = (filename, prompt, f"text/plain;charset={encoding}")
    if response:
        filename = "response.txt" if with_filenames else None
        fields[RESPONSE_NAME] = (filename, response, f"text/plain;charset={encoding}")
    if parameters:
        parameters_json = json.dumps(parameters)
        filename = "parameters.json" if with_filenames else None
        fields[INPUT_PARAMETERS_NAME] = (filename, parameters_json, "application/json")

    multipart_data = MultipartEncoder(
        fields=fields, encoding=encoding, boundary=boundary
    )

    async def receive():
        return {"type": "http.request", "body": multipart_data.to_string()}

    return fake_request(
        method="POST",
        headers={"content-type": f"multipart/form-data;boundary={boundary}"},
        receive=receive,
    )


FAKE_TAGS = Tags({"test1": ["a", "b"]})


# noinspection PyTestUnpassedFixture
@pytest.mark.usefixtures("class_data_loader")
class ProcessorTest(unittest.IsolatedAsyncioTestCase):
    maxDiff = None

    async def test_handle_head_request(self):
        request = fake_request("HEAD")
        processor = fake_processor()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)

    async def test_handle_unsupported_method(self):
        unsupported_methods = [
            "GET",
            "PUT",
            "DELETE",
            "PATCH",
            "OPTIONS",
            "TRACE",
            "CONNECT",
            "UNKNOWN",
        ]
        processor = fake_processor()
        for method in unsupported_methods:
            request = fake_request(method)

            response = await processor.handle_request(request)

            self.assertStatusCodeEqual(response, HTTP_405_METHOD_NOT_ALLOWED)
            body = json.loads(response.body)
            self.assertEqual("Only POST requests are supported", body.get("message"))

    async def test_no_headers_set(self):
        request = fake_request("POST")
        processor = fake_processor()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(response.body, b'{"detail": "Content-Type header missing"}')

    async def test_empty_content_type(self):
        request = fake_request(method="POST", headers={"content-type": ""})
        processor = fake_processor()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(b'{"detail": "Content-Type header is empty"}', response.body)

    async def test_incorrect_content_type(self):
        request = fake_request(
            method="POST", headers={"content-type": "application/json"}
        )
        processor = fake_processor()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(
            b'{"detail": "Content-Type header mismatch - expecting: multipart/form-data"}',
            response.body,
        )

    async def test_content_type_with_no_boundary(self):
        request = fake_request(
            method="POST", headers={"content-type": "multipart/form-data"}
        )
        processor = fake_processor()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(
            b'{"detail": "Content-Type header missing boundary"}', response.body
        )

    async def test_handle_missing_parameters_metadata_and_body(self):
        async def receive():
            return {"type": "http.request"}

        request = fake_request(
            method="POST",
            headers={"content-type": "multipart/form-data;boundary=12345678"},
            receive=receive,
        )
        processor = fake_processor()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_400_BAD_REQUEST)
        self.assertEqual(b'{"detail": "metadata part is missing"}', response.body)

    async def test_handle_missing_prompt_and_response(self):
        metadata = {"key": "value"}
        request = fake_multipart_request(metadata=metadata)
        processor = fake_processor()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_400_BAD_REQUEST)
        self.assertEqual(
            b'{"detail": "input.messages (prompt) and response.choices (response) fields are missing'
            b' - at least one is required"}',
            response.body,
            "expected error message not found",
        )

    async def test_handle_malformed_metadata(self):
        body = (
            self.data_loader("malformed_metadata_body.txt")
            .replace("\n", "\r\n")
            .replace('name="body"', f'name="{INPUT_NAME}"')
        )

        async def receive():
            return {"type": "http.request", "body": body.encode()}

        request = fake_request(
            method="POST",
            headers={"content-type": "multipart/form-data;boundary=boundary"},
            receive=receive,
        )
        processor = fake_processor(a_signature=INPUT_ONLY_SIGNATURE)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_400_BAD_REQUEST)

        expected_error_msg = (
            "Unable to parse JSON field [metadata]: Unterminated string starting at: "
            + """line 1 column 3 (char 2)"""
        )
        expected_detail = '{"detail": "' + expected_error_msg + '"}'
        actual_detail = response.body.decode(DEFAULT_ENCODING)
        self.assertEqual(expected_detail, actual_detail, "expected error message")

    async def test_handle_valid_prompt_with_none_processor_result(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(prompt=prompt, metadata=metadata)
        result = Result(processor_result=None)
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_204_NO_CONTENT)
        self.assertEqual(b"", response.body, "expected empty body")

    async def test_handle_valid_prompt_with_tags_processor_result(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt,
            metadata=metadata,
            parameters={"annotate": True},
        )
        result = Result(
            metadata=metadata,
            processor_result=None,
            tags=FAKE_TAGS,
        )
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)
        content = await self.buffer_response(response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=response.headers["Content-Type"]
        )
        multipart_metadata = multipart.metadata

        self.assertIn("test1", multipart_metadata.content, "expected tags in response")

    async def test_handle_valid_prompt_with_empty_processor_result(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(prompt=prompt, metadata=metadata)
        result = Result(modified_prompt=None, metadata=None, processor_result=None)
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_204_NO_CONTENT)
        self.assertEqual(b"", response.body, "expected empty body")

    async def test_handle_valid_prompt_with_processor_result(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt,
            metadata=metadata,
            parameters={"modify": True, "annotate": True},
        )
        result = Result(
            metadata=metadata, processor_result={"unit_test": True}, tags=FAKE_TAGS
        )
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)

        content = await self.buffer_response(response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=response.headers["Content-Type"]
        )
        self.assertFalse(
            multipart.has_prompt(),
            "prompt should not be in the response because it was not modified",
        )

        multipart_metadata = multipart.metadata
        self.assertEqual(
            MultipartResponse.JSON_CONTENT_TYPE, multipart_metadata.content_type()
        )
        response_metadata = multipart_metadata.as_json()

        expected_response_metadata = self.data_loader(
            "multipart_response_metadata.json"
        )
        expected_response_metadata.update(
            dict(
                app_details=APP_DETAILS,
                processor_id=processor.id(),
                processor_version=processor.version,
            )
        )

        self.assertDictEqual(expected_response_metadata, response_metadata)

    async def test_handle_rejected_prompt(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value", "step_id": "12345", "request_id": "09876"}
        request = fake_multipart_request(
            prompt=prompt,
            metadata=metadata,
            parameters={"reject": True, "annotate": True},
        )
        result = Reject(
            metadata=metadata,
            code=RejectCode.POLICY_VIOLATION,
            detail="dangerous question asked",
            tags=FAKE_TAGS,
        )
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)

        content = await self.buffer_response(response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=response.headers["Content-Type"]
        )

        self.assertFalse(
            multipart.has_prompt(), "the rejected prompt should not be in the response"
        )

        multipart_metadata = multipart.metadata
        self.assertEqual(
            MultipartResponse.JSON_CONTENT_TYPE, multipart_metadata.content_type()
        )
        response_metadata = multipart_metadata.as_json()

        expected_response_metadata = dict(
            app_details=APP_DETAILS,
            processor_id=processor.id(),
            processor_version=processor.version,
            tags={"test1": ["a", "b"]},
        )
        for k, v in metadata.items():
            expected_response_metadata[k] = v

        self.assertDictEqual(expected_response_metadata, response_metadata)

    async def test_handle_rejected_prompt_with_result(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value", "step_id": "12345", "request_id": "09876"}
        request = fake_multipart_request(
            prompt=prompt,
            metadata=metadata,
            parameters={"reject": True, "annotate": True},
        )
        result = Reject(
            metadata=metadata,
            code=RejectCode.POLICY_VIOLATION,
            detail="dangerous question asked",
            tags=FAKE_TAGS,
            processor_result={"confidence": 0.99},
        )
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)

        content = await self.buffer_response(response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=response.headers["Content-Type"]
        )

        self.assertFalse(
            multipart.has_prompt(), "the rejected prompt should not be in the response"
        )

        multipart_metadata = multipart.metadata
        self.assertEqual(
            MultipartResponse.JSON_CONTENT_TYPE, multipart_metadata.content_type()
        )
        response_metadata = multipart_metadata.as_json()

        expected_response_metadata = dict(
            app_details=APP_DETAILS,
            processor_id=processor.id(),
            processor_result={"confidence": 0.99},
            processor_version=processor.version,
            tags={"test1": ["a", "b"]},
        )
        for k, v in metadata.items():
            expected_response_metadata[k] = v

        self.assertDictEqual(expected_response_metadata, response_metadata)

    async def test_handle_modified_prompt(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt,
            metadata=metadata,
            parameters={"modify": True, "annotate": True},
        )
        result = Result(
            modified_prompt=RequestInput(
                messages=[Message(content="Can you tell that this had been modified?")]
            ),
            metadata=metadata,
            processor_result={"unit_test": "true"},
            tags=FAKE_TAGS,
        )
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)

        content = await self.buffer_response(response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=response.headers["Content-Type"]
        )

        self.assertTrue(
            multipart.has_prompt(),
            "the rewritten/modified prompt should always be in the response",
        )

        multipart_prompt = multipart.prompt

        self.assertEqual(
            MultipartResponse.JSON_CONTENT_TYPE, multipart_prompt.content_type()
        )
        parsed_multipart_content = RequestInput.model_validate_json(
            multipart_prompt.content
        )
        self.assertEqual(
            result.modified_prompt,
            parsed_multipart_content,
        )

        multipart_metadata = multipart.metadata
        self.assertEqual(
            MultipartResponse.JSON_CONTENT_TYPE, multipart_metadata.content_type()
        )
        response_metadata = multipart_metadata.as_json()

        expected_response_metadata = self.data_loader(
            "multipart_response_metadata.json"
        )
        expected_response_metadata.update(
            dict(
                app_details=APP_DETAILS,
                processor_id=processor.id(),
                processor_version=processor.version,
            )
        )

        self.assertEqual(
            multipart_metadata.headers["Content-Disposition"],
            f'form-data; name="{METADATA_NAME}"',
        )
        self.assertEqual(
            multipart_metadata.headers["Content-Type"],
            MultipartResponse.JSON_CONTENT_TYPE,
        )
        expected_response_metadata["processor_result"]["unit_test"] = "true"

        self.assertDictEqual(expected_response_metadata, response_metadata)

    async def test_handle_unmodified_prompt(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt,
            metadata=metadata,
            parameters={"modify": True, "annotate": True},
        )
        result = Result(
            modified_prompt=RequestInput(messages=[TEST_MESSAGE]),
            metadata=metadata,
            processor_result={"unit_test": "true"},
            tags=FAKE_TAGS,
        )
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)

        content = await self.buffer_response(response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=response.headers["Content-Type"]
        )

        self.assertFalse(
            multipart.has_prompt(),
            "the unmodified prompt should not be in the response",
        )

        multipart_metadata = multipart.metadata
        self.assertEqual(
            MultipartResponse.JSON_CONTENT_TYPE, multipart_metadata.content_type()
        )
        response_metadata = multipart_metadata.as_json()

        expected_response_metadata = self.data_loader(
            "multipart_response_metadata.json"
        )
        expected_response_metadata.update(
            dict(
                app_details=APP_DETAILS,
                processor_id=processor.id(),
                processor_version=processor.version,
            )
        )

        self.assertEqual(
            multipart_metadata.headers["Content-Disposition"],
            f'form-data; name="{METADATA_NAME}"',
        )
        self.assertEqual(
            multipart_metadata.headers["Content-Type"],
            MultipartResponse.JSON_CONTENT_TYPE,
        )
        expected_response_metadata["processor_result"]["unit_test"] = "true"

        self.assertDictEqual(expected_response_metadata, response_metadata)

    async def test_handle_modification_of_prompt_object(self):
        """
        Verifies that process functions which modify the object
        directly correctly detect modifications
        """
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt,
            metadata=metadata,
            parameters={"modify": True, "annotate": True},
        )

        class DirectObjectModificationProc(Processor):
            def __init__(self):
                super().__init__(
                    name="DirectObjectModificationProc",
                    namespace="Test",
                    version="v1",
                    signature=INPUT_ONLY_SIGNATURE,
                )

            def process_input(self, prompt, metadata, parameters, request) -> Result:
                prompt.messages.append(Message(content="Test message"))
                return Result(modified_prompt=prompt)

        processor = DirectObjectModificationProc()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)

        content = await self.buffer_response(response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=response.headers["Content-Type"]
        )

        self.assertTrue(
            multipart.has_prompt(),
            "prompt should be in the response",
        )

        multipart_prompt = multipart.prompt
        assert "Test message" in multipart_prompt.content

    async def test_prompt_send_with_file_header(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt, metadata=metadata, with_filenames=True
        )
        result = Result(metadata=None, processor_result=None)
        processor = fake_processor(result=result)

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_204_NO_CONTENT)
        self.assertEqual(b"", response.body, "expected empty body")

    def test_to_dict(self):
        processor = fake_processor()
        expected = self.data_loader("processor_as_dict.yaml")
        expected.update(
            dict(
                path=f"/execute/{expected['namespace']}/{expected['name']}",
                signature_path=f"/signature/{expected['namespace']}/{expected['name']}",
            )
        )
        expected["methods"] = ["GET", "HEAD", "POST"]
        actual = processor.to_dict()
        self.assertDictEqual(
            expected,
            actual,
            "processor conversion to dict did not match expected result",
        )

    def test_name_whitespace_error(self):
        """Verify that a ValueError is issued when Processor is created with a name that contains whitespace."""
        expected_message = "Processor name cannot contain whitespace"
        with pytest.raises(ValueError) as err:
            MinimalFakeProcessor("foo bar", "", "", BOTH_SIGNATURE)
        self.assertIn(expected_message, err.value.args, str(err.value.args))

    def test_version_whitespace_error(self):
        """Verify that a ValueError is issued when Processor is created with a version that contains whitespace."""
        expected_message = "Processor version cannot contain whitespace"
        with pytest.raises(ValueError) as err:
            MinimalFakeProcessor("foo_bar", "1 1", "namespace", BOTH_SIGNATURE)
        self.assertIn(expected_message, err.value.args, str(err.value.args))

    def test_processor_neq_other_type(self):
        """Verify that a False is issued when a processor is compared to a different type."""

        class Foo:
            pass

        processor = MinimalFakeProcessor("foo_bar", "namespace", "1.1", BOTH_SIGNATURE)
        self.assertNotEqual(processor, Foo())

    def test_processor_eq_processor(self):
        """Verify two processors created the same are equal."""
        name = "foo_bar"
        version = "1.1"
        namespace = "namespace"
        processor1 = MinimalFakeProcessor(name, version, namespace, BOTH_SIGNATURE)
        processor2 = MinimalFakeProcessor(name, version, namespace, BOTH_SIGNATURE)
        self.assertEqual(processor1, processor2)

    @parameterized.expand(
        [
            (
                [METADATA_NAME, INPUT_NAME],
                [INPUT_ONLY_SIGNATURE, BOTH_SIGNATURE, BOTH_RESPONSE_PROMPT_SIGNATURE],
            ),
            ([METADATA_NAME, RESPONSE_NAME], [RESPONSE_ONLY_SIGNATURE, BOTH_SIGNATURE]),
            (
                [METADATA_NAME, RESPONSE_NAME, INPUT_NAME],
                [RESPONSE_AND_PROMPT_SIGNATURE, BOTH_RESPONSE_PROMPT_SIGNATURE],
            ),
        ]
    )
    def test_multipart_field_validation_valid(
        self, signature_fields: Iterable[str], signatures: Iterable[Signature]
    ):
        """Verify that the multipart field validation passes when all required fields are present."""
        for signature in signatures:
            processor = fake_processor(a_signature=signature)
            fields: list[tuple[str, str]] = list(
                map(lambda s: (s, ""), signature_fields)
            )
            # noinspection PyTypeChecker
            form_data = FormData(fields)
            self.assertIsNone(processor._validate_and_find_parameters_name(form_data))

    @parameterized.expand(
        [
            ([], ALL_PREDEFINED_SIGNATURES),
            ([METADATA_NAME], ALL_PREDEFINED_SIGNATURES),
            (
                [METADATA_NAME, INPUT_NAME],
                [RESPONSE_ONLY_SIGNATURE, RESPONSE_AND_PROMPT_SIGNATURE],
            ),
            (
                [METADATA_NAME, RESPONSE_NAME],
                [INPUT_ONLY_SIGNATURE, RESPONSE_AND_PROMPT_SIGNATURE],
            ),
            ([METADATA_NAME, "unknown field"], ALL_PREDEFINED_SIGNATURES),
        ]
    )
    def test_multipart_field_validation_invalid(
        self, signature_fields: Iterable[str], signatures: Iterable[Signature]
    ):
        """Verify that the multipart field validation fails when a required field is missing or wrongly assigned."""
        for signature in signatures:
            processor = fake_processor(a_signature=signature)
            fields: list[tuple[str, str]] = list(
                map(lambda s: (s, ""), signature_fields)
            )
            # noinspection PyTypeChecker
            form_data = FormData(fields)
            error_found = False
            try:
                processor._validate_and_find_parameters_name(form_data)
            except ProcessorError:
                error_found = True

            self.assertTrue(
                error_found,
                f"ProcessorError was not raised for fields: {signature_fields} "
                f"and signature: {signature}",
            )

    def test_no_subclass(self):
        expected_message = (
            "Processor is an abstract base class and cannot be instantiated directly."
        )
        with pytest.raises(TypeError) as err:
            Processor(
                "attempt-direct-processor-use", "v1", "test", signature=BOTH_SIGNATURE
            )
        self.assertIn(expected_message, err.value.args, str(err.value.args))

    def test_none_implemented(self):
        expected_message = (
            "Cannot create concrete class NonImplementedProcessor. "
            "It must override AT LEAST ONE of the following methods: "
            "'process_input', 'process_response'. "
            "Or alternatively the DEPRECATED 'process' method."
        )

        with pytest.raises(TypeError) as err:

            class NonImplementedProcessor(Processor):
                def __init__(self):
                    super().__init__(
                        name="non-implemented-processor",
                        namespace="fake",
                        signature=BOTH_SIGNATURE,
                        version="v1",
                    )

            NonImplementedProcessor()
        self.assertIn(expected_message, err.value.args, str(err.value.args))

    def test_all_implemented(self):
        expected_message = (
            "Cannot create concrete class AllImplementedProcessor. "
            "The DEPRECATED 'process' method must not be implemented "
            "alongside 'process_input' or 'process_response'."
        )

        with pytest.raises(TypeError) as err:

            class AllImplementedProcessor(Processor):
                def __init__(self):
                    super().__init__(
                        name="non-implemented-processor",
                        namespace="fake",
                        signature=BOTH_SIGNATURE,
                        version="v1",
                    )

                def process(self):
                    return Result()

                def process_input(self):
                    return Result()

                def process_response(self):
                    return Result()

            AllImplementedProcessor()
        self.assertIn(expected_message, err.value.args, str(err.value.args))

    def test_async_implemented(self):
        class AsyncImplementedProcessor(Processor):
            def __init__(self):
                super().__init__(
                    name="non-implemented-processor",
                    namespace="fake",
                    signature=BOTH_SIGNATURE,
                    version="v1",
                )

            async def process_input(self):
                return Result()

            async def process_response(self):
                return Result()

        self.assertIsNotNone(AsyncImplementedProcessor())

    async def test_async_message(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt,
            metadata=metadata,
            parameters={"modify": True, "annotate": True},
        )

        class AsyncInputProcessor(Processor):
            def __init__(self):
                super().__init__(
                    name="async-input-processor",
                    namespace="fake",
                    signature=INPUT_ONLY_SIGNATURE,
                    version="v1",
                )

            async def process_input(
                self, prompt, metadata, parameters, request
            ) -> Result:
                prompt.messages.append(Message(content="Test message"))
                return Result(modified_prompt=prompt)

        processor = AsyncInputProcessor()

        response = await processor.handle_request(request)

        self.assertStatusCodeEqual(response, HTTP_200_OK)

        content = await self.buffer_response(response)
        multipart = MultipartDecoderHelper(
            content=content, content_type=response.headers["Content-Type"]
        )

        self.assertTrue(
            multipart.has_prompt(),
            "prompt should be in the response",
        )

        multipart_prompt = multipart.prompt
        assert "Test message" in multipart_prompt.content

    def test_async_process_implemented(self):
        expected_message = (
            "Cannot create concrete class AsyncProcessImplementedProcessor. "
            "The DEPRECATED 'process' method does not support async. "
            "Implement 'process_input' and/or 'process_response' instead."
        )

        with pytest.raises(TypeError) as err:

            class AsyncProcessImplementedProcessor(Processor):
                def __init__(self):
                    super().__init__(
                        name="non-implemented-processor",
                        namespace="fake",
                        signature=BOTH_SIGNATURE,
                        version="v1",
                    )

                async def process(self):
                    return Result()

            AsyncProcessImplementedProcessor()
        self.assertIn(expected_message, err.value.args, str(err.value.args))

    def test_input_signature_match(self):
        """Verify we can instantiate a correct input-only processor"""

        class InputMatchProcessor(Processor):
            def __init__(self):
                super().__init__(
                    name="non-implemented-processor",
                    namespace="fake",
                    signature=INPUT_ONLY_SIGNATURE,
                    version="v1",
                )

            def process_input(self):
                return Result()

        InputMatchProcessor()

    def test_input_signature_mismatch(self):
        expected_message = (
            "Cannot create concrete class InputMismatchProcessor. "
            "Provided Signature supports input but 'process_input' "
            "is not implemented."
        )

        with pytest.raises(TypeError) as err:

            class InputMismatchProcessor(Processor):
                def __init__(self):
                    super().__init__(
                        name="non-implemented-processor",
                        namespace="fake",
                        signature=BOTH_SIGNATURE,
                        version="v1",
                    )

                def process_response(self):
                    return Result()

            InputMismatchProcessor()
        self.assertIn(expected_message, err.value.args, str(err.value.args))

    def test_response_signature_match(self):
        """Verify we can instantiate a correct response-only processor"""

        class ResponseMatchProcessor(Processor):
            def __init__(self):
                super().__init__(
                    name="non-implemented-processor",
                    namespace="fake",
                    signature=RESPONSE_ONLY_SIGNATURE,
                    version="v1",
                )

            def process_response(self):
                return Result()

        ResponseMatchProcessor()

    def test_response_signature_mismatch(self):
        expected_message = (
            "Cannot create concrete class ResponseMismatchProcessor. "
            "Provided Signature supports response but 'process_response' "
            "is not implemented."
        )

        with pytest.raises(TypeError) as err:

            class ResponseMismatchProcessor(Processor):
                def __init__(self):
                    super().__init__(
                        name="non-implemented-processor",
                        namespace="fake",
                        signature=BOTH_SIGNATURE,
                        version="v1",
                    )

                def process_input(self):
                    return Result()

            ResponseMismatchProcessor()
        self.assertIn(expected_message, err.value.args, str(err.value.args))

    def test_deprecated_process_signature_match(self):
        class DeprecatedProcessor(Processor):
            def __init__(self):
                super().__init__(
                    name="non-implemented-processor",
                    namespace="fake",
                    signature=BOTH_SIGNATURE,
                    version="v1",
                )

            def process(self):
                return Result()

        DeprecatedProcessor()

    # HELPER METHODS #

    async def buffer_response(self, response: HttpResponse) -> bytes:
        self.assertIsInstance(response, MultipartResponse)
        multipart_response: MultipartResponse = response

        buffer = BytesIO()
        async for chunk in multipart_response.body_iterator:
            buffer.write(chunk)

        return buffer.getvalue()

    def assertStatusCodeEqual(self, response: HttpResponse, status_code: int):
        if not response:
            self.fail("Response is None")

        self.assertIsInstance(
            response, HttpResponse, f"Expected HttpResponse, got {type(response)}"
        )

        if response.status_code != status_code:
            if not hasattr(response, "body") or isinstance(
                response.body, HttpStreamingResponse
            ):
                self.fail(
                    f"Expected status code {status_code}, got {response.status_code}"
                )
            else:
                self.fail(
                    f"Expected status code {status_code}, got {response.status_code}. "
                    f"Server response: \n{response.body}"
                )

    async def test_not_allowed_modify_dropped(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(prompt=prompt, metadata=metadata)
        result = Result(
            modified_prompt={"messages": [{"content": "Are bats better than dogs?"}]},
        )
        processor = fake_processor(result=result)

        with self.assertLogs("root", level="WARN") as lw:
            response = await processor.handle_request(request)
            self.assertEqual(
                lw.output,
                [
                    "WARNING:root:FakeProcessor tried to modify request when parameters.modify was set to false, modification will be dropped",
                ],
            )

        self.assertStatusCodeEqual(response, HTTP_200_OK)

    async def test_not_allowed_annotate_dropped(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt, metadata=metadata, parameters={"annotate": False}
        )
        result = Result(tags=FAKE_TAGS)
        processor = fake_processor(result=result)

        with self.assertLogs("root", level="WARN") as lw:
            response = await processor.handle_request(request)
            self.assertEqual(
                lw.output,
                [
                    "WARNING:root:FakeProcessor tried to annotate request with tags when parameters.annotate was set to false, tags will be dropped",
                ],
            )

        self.assertStatusCodeEqual(response, HTTP_200_OK)

    async def test_not_allowed_reject_dropped(self):
        prompt = TEST_REQ_INPUT.model_dump_json()
        metadata = {"key": "value"}
        request = fake_multipart_request(
            prompt=prompt, metadata=metadata, parameters={"reject": False}
        )
        result = Reject(code=RejectCode.POLICY_VIOLATION, detail="", tags=FAKE_TAGS)
        processor = fake_processor(result=result)

        with self.assertLogs("root", level="WARN") as lw:
            response = await processor.handle_request(request)
            self.assertEqual(
                lw.output,
                [
                    "WARNING:root:FakeProcessor tried to reject request when parameters.reject was set to false, rejection will be dropped",
                ],
            )

        self.assertStatusCodeEqual(response, HTTP_200_OK)
