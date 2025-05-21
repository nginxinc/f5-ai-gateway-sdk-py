"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Verify certain contractual exchanges against a stood up processor.
"""

import io
import json
from collections import namedtuple
from collections.abc import Callable
from typing import Any, AnyStr
import pytest

import urllib3
from pydantic import BaseModel
from starlette import status as http_status_codes
from urllib3.fields import RequestField

from f5_ai_gateway_sdk import errors, multipart_fields
from f5_ai_gateway_sdk.multipart_fields import (
    INPUT_NAME,
    INPUT_PARAMETERS_NAME,
    METADATA_NAME,
    RESPONSE_NAME,
)
from f5_ai_gateway_sdk.parameters import Parameters
from f5_ai_gateway_sdk.processor import Tags
from f5_ai_gateway_sdk.request_input import Message, RequestInput
from f5_ai_gateway_sdk.response_output import Choice, ResponseOutput
from f5_ai_gateway_sdk.result import Result

from ..libs.exceptions import TestTypeError
from ..libs.fakes import processors as fake_processors

PROCESSOR_NAME = "good_judgy"
PROCESSOR_NAMESPACE = "testing"
PROCESSOR_VERSION = "1"
PROCESSOR_PATH = f"execute/{PROCESSOR_NAMESPACE}/{PROCESSOR_NAME}"
SIGNATURE_PATH = f"signature/{PROCESSOR_NAMESPACE}/{PROCESSOR_NAME}"
CONTENT_TYPE = "application/json"


def test_multipart_fields_breaking_change():
    """Verify that the multipart_fields have not changed without this test failing.

    Verifies that SDK does not introduce a breaking change in the multipart field names though the ease of changing
    something in f5_ai_gateway_sdk.multipart_fields and tests continue to pass here due to the dynamic
    continuation of these global values.

    THIS IS VITAL for breaking change detection and should be kept up to date as needed as field names change, but
    the following tests that might identify this type of error will likely not as they use the encoded form.
    """
    expected_metadata_name = "metadata"
    expected_required_multipart_fields = [expected_metadata_name]
    expected_prompt_name = "input.messages"
    expected_prompt_parameters_name = "input.parameters"
    expected_response_name = "response.choices"
    expected_response_parameters_name = "response.parameters"
    expected_reject_name = "reject"
    expected_optional_multipart_fields = [
        expected_prompt_name,
        expected_response_name,
        expected_prompt_parameters_name,
        expected_response_parameters_name,
        expected_reject_name,
    ]
    assert (
        encoded_field := multipart_fields.METADATA_NAME
    ) == expected_metadata_name, (
        f"breaking change detected: {encoded_field} change from {expected_metadata_name}"
    )
    assert (encoded_fields := multipart_fields.INPUT_NAME) == expected_prompt_name, (
        f"breaking change detected: {encoded_fields} change from {expected_optional_multipart_fields}"
    )
    assert (
        encoded_field := multipart_fields.INPUT_PARAMETERS_NAME
    ) == expected_prompt_parameters_name, (
        f"breaking change detected: {encoded_field} change from {expected_prompt_name}"
    )
    assert (
        encoded_field := multipart_fields.RESPONSE_NAME
    ) == expected_response_name, (
        f"breaking change detected: {encoded_field} change from {expected_prompt_name}"
    )
    assert (
        encoded_field := multipart_fields.RESPONSE_PARAMETERS_NAME
    ) == expected_response_parameters_name, (
        f"breaking change detected: {encoded_field} change from {expected_prompt_name}"
    )
    # - validate required versus optional field definitions; order not super important
    assert (expected := set(expected_required_multipart_fields)) == (
        result := set(multipart_fields.REQUIRED_MULTIPART_FIELDS)
    ), f"{result - expected} and {expected - result} should be empty"
    assert (expected := set(expected_optional_multipart_fields)) == (
        result := set(multipart_fields.OPTIONAL_MULTIPART_FIELDS)
    ), f"{result - expected} and {expected - result} should be empty"


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_processor_response_parameters_a_prompt_mismatch(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_message = (
        f"response parameters cannot be present with only a {INPUT_NAME} field"
    )
    expected_response = f'{{"detail": "{expected_message}"}}'
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = fake_judgy(judgy_class)

    test_logger.info("when: client requests a post with prompt and response parameters")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters="{}",
    )
    data[multipart_fields.RESPONSE_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    del data[multipart_fields.INPUT_PARAMETERS_NAME]
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_processor_overload_both_parameters(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_message = (
        f"response parameters cannot be present with only a {INPUT_NAME} field"
    )
    expected_response = f'{{"detail": "{expected_message}"}}'
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = fake_judgy(judgy_class)

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters="{}",
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    data[multipart_fields.RESPONSE_PARAMETERS_NAME] = data[
        multipart_fields.INPUT_PARAMETERS_NAME
    ]
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_processor_500_raising(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_response = """{"detail": "problem executing processor implementation"}"""
    expected_status_code = http_status_codes.HTTP_500_INTERNAL_SERVER_ERROR

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = fake_judgy(judgy_class)
    judgy.raise_error = errors.ProcessorError(
        http_status_codes.HTTP_500_INTERNAL_SERVER_ERROR, "fool of the fools"
    )

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters="{}",
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    response = client.send(request)
    assert response.status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_processor_returns_none(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""

    if judgy_class == fake_processors.Judgy:

        class NoneReturningProcessor(judgy_class):
            def process_input(*_, **__):
                """Return None as a matter of existence."""
                return None

            def process_response(*_, **__):
                """Return None as a matter of existence."""
                return None
    else:

        class NoneReturningProcessor(judgy_class):
            def process(*_, **__):
                """Return None as a matter of existence."""
                return None

    expected_response = (
        """{"detail": "Processor[testing:good_judgy] process() method returned None"}"""
    )
    expected_status_code = http_status_codes.HTTP_500_INTERNAL_SERVER_ERROR

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = NoneReturningProcessor(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )
    judgy.raise_error = TypeError("fool of the fools")

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters="{}",
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_processor_returns_bogus_class(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""

    class BogusClass:
        rejected = False
        modified = False
        metadata = {}
        processor_result = {}
        tags = Tags()
        """Bogus class placeholder that is not a valid response object."""

    if judgy_class == fake_processors.Judgy:

        class BogusClassReturningProcessor(judgy_class):
            """Bogus processor whose process method returns BogusClass type."""

            def process_input(*_, **__):
                """Return BogusClass type as a matter of existence."""
                return BogusClass()
    else:

        class BogusClassReturningProcessor(judgy_class):
            """Bogus processor whose process method returns BogusClass type."""

            def process(*_, **__):
                """Return BogusClass type as a matter of existence."""
                return BogusClass()

    expected_response = """{"detail": "problem creating response object"}"""
    expected_status_code = http_status_codes.HTTP_500_INTERNAL_SERVER_ERROR

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = BogusClassReturningProcessor(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )
    judgy.raise_error = TypeError("fool of the fools")

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters="{}",
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_raising_processor(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will return 500 when it crashes."""
    expected_response = """{"detail": "problem executing processor implementation"}"""
    expected_status_code = http_status_codes.HTTP_500_INTERNAL_SERVER_ERROR

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )
    judgy.raise_error = TypeError("fool of the fools")

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters="{}",
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_no_prompt(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_error = (
        f'{{"detail": "{INPUT_NAME} (prompt) and {RESPONSE_NAME} (response) fields are missing -'
        f' at least one is required"}}'
    )
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(data_loader, metadata="{}", parameters="{}")
    data[multipart_fields.INPUT_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_error} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_error, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_error}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_null_parameters(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_response = """{"detail": "invalid parameters submitted", "messages": ["Input should be an object"]}"""
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters="{}",
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME] = b"null"
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_empty_metadata(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_response = '{"detail": "Unable to parse JSON field [metadata]: Expecting value: line 1 column 1 (char 0)"}'
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
    )
    data[multipart_fields.METADATA_NAME] = b""
    data[multipart_fields.INPUT_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_invalid_metadata(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_response = """{"detail": "invalid metadata submitted"}"""
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME] = json.dumps(
        data_loader("judgy_parameters.yaml")
    )
    data[multipart_fields.INPUT_NAME] = RequestField(
        multipart_fields.INPUT_NAME,
        data[multipart_fields.INPUT_NAME],
    )
    data[multipart_fields.INPUT_NAME].make_multipart(
        f'form-data; name="{multipart_fields.INPUT_NAME}"', "text/plain", ""
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME] = RequestField(
        name=multipart_fields.INPUT_PARAMETERS_NAME,
        data=data[multipart_fields.INPUT_PARAMETERS_NAME],
    )
    data[multipart_fields.INPUT_PARAMETERS_NAME].make_multipart(
        f'form-data; name="{multipart_fields.INPUT_PARAMETERS_NAME}"',
        "application/json",
        "parameters.json",
    )
    data[multipart_fields.METADATA_NAME] = RequestField(
        name=multipart_fields.METADATA_NAME,
        data=b"",
        filename="foo.jpeg",
    )
    data[multipart_fields.METADATA_NAME].make_multipart(
        f'attachment; name="{multipart_fields.METADATA_NAME}"',
        "image/jpeg",
        "meta.jpeg",
    )
    header, retrieval = multipart_framing([value for value in data.values()])
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_string_metadata(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_response = """{"detail": "metadata must be a JSON object"}"""
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = fake_judgy(judgy_class)

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
    )
    data[METADATA_NAME] = b"null"
    data[INPUT_NAME] = b"Why are dogs so friendly?"
    data[INPUT_PARAMETERS_NAME] = json.dumps(data_loader("judgy_parameters.yaml"))
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_response} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_response, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_response}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_query_get_command(processor_client_loader, test_logger, judgy_class):
    """Verify that with a ?command=parameters we get the parameters back."""
    expected_status_code = http_status_codes.HTTP_200_OK

    method = "get"

    test_logger.info(f"given: processor with path: {SIGNATURE_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )

    test_logger.info(
        f"when: client requests a get with no prompt, and the query {SIGNATURE_PATH}"
    )
    client = processor_client_loader(judgy)

    test_logger.info(
        "then: request response should be {expected_status_code}: {expected_error}"
    )
    response = client.get(SIGNATURE_PATH)

    assert response.status_code == expected_status_code, (
        f"{response.status_code} != {expected_status_code} for {method}({response.url})"
    )
    assert response.json()["parameters"] == judgy.parameters_class.model_json_schema()


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_query_post_command_invalid_json(
    processor_client_loader, test_logger, judgy_class
):
    """Verify that with a ?command=parameters we get the parameters back."""
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {SIGNATURE_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyRequiredParameters,
    )

    test_logger.info(
        f"when: client requests a get with no prompt, and the query {SIGNATURE_PATH}"
    )
    client = processor_client_loader(judgy)

    test_logger.info(
        "then: request response should be {expected_status_code}: {expected_error}"
    )
    request = client.build_request(
        url=SIGNATURE_PATH,
        method=method,
        headers={"Content-Type": "application/json"},
        content="",
    )
    response = client.send(request)

    assert response.status_code == expected_status_code, (
        f"{response.status_code} != {expected_status_code} for {method}({response.url})"
    )
    result = response.json()
    assert result["parameters"] == judgy.parameters_class.model_json_schema()
    assert not result["validation"]["valid"]
    assert result["validation"]["errors"] == [
        "Invalid JSON: EOF while parsing a value at line 1 column 0"
    ]


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_query_post_command_invalid_parameters(
    processor_client_loader, test_logger, judgy_class
):
    """Verify that with a ?command=parameters we get the parameters back."""
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {SIGNATURE_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyRequiredParameters,
    )

    test_logger.info(
        f"when: client requests a get with no prompt, and the query {SIGNATURE_PATH}"
    )
    client = processor_client_loader(judgy)

    test_logger.info(
        "then: request response should be {expected_status_code}: {expected_error}"
    )
    request = client.build_request(
        url=SIGNATURE_PATH,
        method=method,
        headers={"Content-Type": "application/json"},
        content='{"message":"test"}',
    )
    response = client.send(request)

    assert response.status_code == expected_status_code, (
        f"{response.status_code} != {expected_status_code} for {method}({response.url})"
    )
    result = response.json()
    assert result["parameters"] == judgy.parameters_class.model_json_schema()
    assert not result["validation"]["valid"]
    assert result["validation"]["errors"] == ["Field required: required_message"], (
        result["validation"]["errors"]
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_invalid_parameters(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_error = """{"detail": "invalid parameters submitted", "messages": ["Input should be a valid boolean: modified"]}"""
    expected_status_code = http_status_codes.HTTP_400_BAD_REQUEST

    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )

    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    parameters = data_loader("judgy_parameters.yaml")
    parameters["modified"] = "Lucy in the sky with diamonds"
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters=parameters,
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_status_code} code and {expected_error} prompt"
    )
    assert (response := client.send(request)).status_code == expected_status_code, (
        f"({response.status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_error, (
        f"{method}{PROCESSOR_PATH} had mismatching errors {result} vs {expected_error}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_required_parameters_missing(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_error = """{"detail": "invalid parameters submitted", "messages": ["Field required: required_message"]}"""
    expected_invalid_status_code = http_status_codes.HTTP_400_BAD_REQUEST
    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyRequiredParameters,
    )

    test_logger.info("when: client requests a post without a required parameter")
    client = processor_client_loader(judgy)
    parameters_missing_required = {"reject": False}
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters=parameters_missing_required,
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_invalid_status_code} code and {expected_error} prompt"
    )
    response = client.send(request)
    assert response.status_code == expected_invalid_status_code, (
        f"({response.status_code} != {expected_invalid_status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (result := response.text) == expected_error, (
        f"{method}{PROCESSOR_PATH} had mismatching errors \n{result} \nvs \n{expected_error}: {content}"
    )
    assert (content_type := response.headers["Content-Type"]) == CONTENT_TYPE, (
        f"expected {CONTENT_TYPE} for Content-Type; instead got {content_type}"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_required_parameters_present(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_valid_status_code = http_status_codes.HTTP_400_BAD_REQUEST
    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyRequiredParameters,
    )

    test_logger.info("when: client requests a post without a required parameter")
    client = processor_client_loader(judgy)
    parameters_with_required = {"reject": False, "required_message": "hello world"}
    data = build_processor_prompt_content(
        data_loader,
        prompt=None,
        metadata="{}",
        parameters=parameters_with_required,
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(f"then: response should have {expected_valid_status_code} code")
    response = client.send(request)
    assert response.status_code == expected_valid_status_code, (
        f"({response.status_code} != {expected_valid_status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert (
        "input.messages (prompt) and response.choices (response) fields are missing - at least one is required"
        in response.text
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_required_metadata_response_fields(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that metadata responses contain required fields."""
    expected_valid_status_code = http_status_codes.HTTP_200_OK
    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = fake_judgy(judgy_class)

    test_logger.info("when: client requests a post without a required parameter")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
        parameters={"skip_metadata": True, "modified": True},
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(f"then: response should have {expected_valid_status_code} code")
    response = client.send(request)
    assert response.status_code == expected_valid_status_code, (
        f"({response.status_code} != {expected_valid_status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert "processor_id" in response.text
    assert "processor_version" in response.text


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_request_required_parameters_missing_multipart(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_error = """{"detail": "invalid parameters submitted", "messages": ["Field required: required_message"]}"""
    expected_valid_status_code = http_status_codes.HTTP_400_BAD_REQUEST
    method = "post"

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyRequiredParameters,
    )

    test_logger.info("when: client requests a post with no params but a required field")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        metadata="{}",
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(
        f"then: response should have {expected_valid_status_code} code and {expected_error} prompt"
    )
    response = client.send(request)
    assert response.status_code == expected_valid_status_code, (
        f"({response.status_code} != {expected_valid_status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert response.text == expected_error, (
        f"expected '{expected_error}' but got '{response.text}'"
    )


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_modification_with_reject(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Verify that with a stood up processor that the request will reject a request with no prompt."""
    expected_valid_status_code = http_status_codes.HTTP_400_BAD_REQUEST
    method = "post"

    if judgy_class == fake_processors.Judgy:

        class ModifyAndRejectProcessor(judgy_class):
            def process_input(*_, **__):
                """Return None as a matter of existence."""
                return Result(
                    modified_prompt=RequestInput(
                        messages=[Message(content="foo-input")]
                    ),
                    modified_response=ResponseOutput(
                        choices=[Choice(message=Message(content="bar-output"))]
                    ),
                )
    else:

        class ModifyAndRejectProcessor(judgy_class):
            def process(*_, **__):
                """Return None as a matter of existence."""
                return Result(
                    modified_prompt=RequestInput(
                        messages=[Message(content="foo-input")]
                    ),
                    modified_response=ResponseOutput(
                        choices=[Choice(message=Message(content="bar-output"))]
                    ),
                )

    test_logger.info(f"given: processor with path: {PROCESSOR_PATH}")
    judgy = ModifyAndRejectProcessor(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
    )

    test_logger.info("when: client requests a post without a required parameter")
    client = processor_client_loader(judgy)
    data = build_processor_prompt_content(
        data_loader,
        prompt=RequestInput(messages=[Message(content="hello world")]),
        response=ResponseOutput(
            choices=[Choice(message=Message(content="goodbye world"))]
        ),
        parameters={"reject": True, "modify": True},
        metadata="{}",
    )
    header, retrieval = multipart_framing(data)
    request = client.build_request(
        url=PROCESSOR_PATH,
        method=method,
        headers={"Content-Type": header},
        content=(content := retrieval()),
    )

    test_logger.info(f"then: response should have {expected_valid_status_code} code")
    response = client.send(request)
    assert response.status_code == expected_valid_status_code, (
        f"({response.status_code} != {expected_valid_status_code}) from {method}({PROCESSOR_PATH}): {content}"
    )
    assert "mutually exclusive" in response.text


@pytest.mark.parametrize(
    "judgy_class", [(fake_processors.Judgy), (fake_processors.DeprecatedJudgy)]
)
def test_get_signature_definition(
    data_loader, processor_client_loader, test_logger, judgy_class
):
    """Assure that the signature returned from the processor /signature endpoint matches the processor's signature"""
    expected_status_code = http_status_codes.HTTP_200_OK
    method = "get"

    test_logger.info(f"given: processor with path: {SIGNATURE_PATH}")
    judgy = fake_judgy(judgy_class)
    test_logger.info("when: client requests a post with no prompt")
    client = processor_client_loader(judgy)
    request = client.build_request(
        url=SIGNATURE_PATH, method=method, headers={"Accept": "application/json"}
    )

    test_logger.info(f"then: response should have {expected_status_code} code")
    response = client.send(request)

    assert expected_status_code == response.status_code, (
        f"({response.status_code}) from {method}({SIGNATURE_PATH})"
    )
    signature_as_json = response.json()["fields"]
    assert signature_as_json == judgy.signature.to_list()


def build_processor_prompt_content(
    data_loader: Callable[[str], Any],
    metadata: AnyStr | None = None,
    prompt: RequestInput | None = None,
    parameters: Parameters | None = None,
    response: ResponseOutput | None = None,
    **other,
) -> dict[str, AnyStr | bytes | RequestField]:
    """Build the content for a request from the provided, anticipated fields."""

    def encode_to_bytes(given) -> bytes:
        """Encode the given into a bytes format."""
        if isinstance(given, (expected := bytes)):
            return given
        if isinstance(given, (expected := (str, expected))):
            return given.encode()
        if isinstance(given, (expected := (list, dict, *expected))):
            return json.dumps(given).encode()
        if issubclass(type(given), BaseModel):
            return bytes(given.model_dump_json(), "utf-8")
        raise TestTypeError(given=type(given), expected=type(expected))

    def screen_other():
        """Screens the content of ``other``."""
        for field, entry in other.items():
            yield field, encode_to_bytes(entry)

    fields = {}
    if metadata:
        fields[multipart_fields.METADATA_NAME] = encode_to_bytes(metadata)
    if prompt:
        fields[multipart_fields.INPUT_NAME] = encode_to_bytes(prompt)
    if response:
        fields[multipart_fields.RESPONSE_NAME] = encode_to_bytes(response)
    if parameters:
        fields[
            multipart_fields.RESPONSE_PARAMETERS_NAME
            if response
            else multipart_fields.INPUT_PARAMETERS_NAME
        ] = encode_to_bytes(parameters)

    fields.update({field: entry for field, entry in screen_other()})
    return {field: entry.strip() for field, entry in fields.items()}


def multipart_framing(multipart_prompt, chunk=None, as_iterator=False):
    """Get a multipart header and prompt retreiever method."""
    multipart = namedtuple("Multipart", "header, retrieve_prompt")
    prompt, header = urllib3.encode_multipart_formdata(multipart_prompt)

    def retrieval_iterator():
        reader = io.BytesIO(prompt)
        if chunk is None:
            for line in iter(reader):
                yield line
        else:
            reader = io.BytesIO(prompt)
            while contents := reader.read(chunk):
                yield contents

    def retrieval():
        return prompt

    if as_iterator:
        return multipart(header, retrieval_iterator)
    return multipart(header, retrieval)


def fake_judgy(judgy_class=fake_processors.Judgy) -> fake_processors.Judgy:
    return judgy_class(
        PROCESSOR_NAME,
        PROCESSOR_VERSION,
        PROCESSOR_NAMESPACE,
        parameters_class=fake_processors.JudgyParameters,
    )
