"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json

from starlette.requests import Request

from f5_ai_gateway_sdk.request_input import RequestInput
from f5_ai_gateway_sdk.response_output import ResponseOutput
from f5_ai_gateway_sdk.signature import BOTH_SIGNATURE
from f5_ai_gateway_sdk.parameters import EmptyParameters
from f5_ai_gateway_sdk.processor import Processor
from f5_ai_gateway_sdk.processor_routes import ProcessorRoutes
from f5_ai_gateway_sdk.result import Result
from f5_ai_gateway_sdk.type_hints import (
    Metadata,
    StreamingResponse,
)


class FakeProcessorOne(Processor):
    def process(
        self,
        prompt: RequestInput,
        response: ResponseOutput,
        metadata: Metadata,
        parameters: EmptyParameters,
        request: Request,
    ) -> Result:
        pass

    def __init__(self):
        super().__init__(
            prompt_class=RequestInput,
            response_class=ResponseOutput,
            name="processor-one",
            namespace="fake",
            signature=BOTH_SIGNATURE,
            version="v1",
        )


class FakeProcessorTwo(Processor):
    def process(
        self,
        prompt: RequestInput,
        response: ResponseOutput,
        metadata: Metadata,
        parameters: EmptyParameters,
        request: Request,
    ) -> Result:
        pass

    def __init__(self):
        super().__init__(
            prompt_class=RequestInput,
            response_class=StreamingResponse,
            name="processor-two",
            namespace="fake",
            signature=BOTH_SIGNATURE,
            version="v1",
        )


FAKE_PROCESSOR_ONE = FakeProcessorOne()
FAKE_PROCESSOR_TWO = FakeProcessorTwo()


def fake_processor_routes():
    return ProcessorRoutes([FAKE_PROCESSOR_ONE, FAKE_PROCESSOR_TWO])


def test_routes_as_plaintext():
    processor_routes = fake_processor_routes()
    as_plaintext = processor_routes.routes_as_plaintext()

    processors = [FAKE_PROCESSOR_ONE, FAKE_PROCESSOR_TWO]
    processor_paths = map(processor_routes.processor_simple_path, processors)
    expected = "\n".join(processor_paths)
    assert expected == as_plaintext


def test_routes_as_json():
    processor_routes = fake_processor_routes()
    as_json = processor_routes.routes_as_json()
    expected_processor_keys = [
        "name",
        "namespace",
        "id",
        "available_versions",
        "latest_version",
        "execute_path",
        "signature_path",
    ]
    as_dict = json.loads(as_json)

    assert "processors" in as_dict
    assert "api_versions" in as_dict
    assert len(as_dict["processors"]) == len(processor_routes)
    assert len(as_dict["api_versions"]) == 1
    for processor in as_dict["processors"]:
        for key in expected_processor_keys:
            assert key in processor, f"expected {key} in {processor}"


def test_list_extensions():
    """Verify that ProcessorRoutes implements list-like behaviors such as iteration, indexing, length, membership testing, copying, and equality comparison."""
    processor_routes = fake_processor_routes()
    assert (
        vanilla_order := tuple([proc for proc in iter(processor_routes)])
    ) == processor_routes._routes
    assert processor_routes[0] == vanilla_order[0]
    assert len(processor_routes) == len(vanilla_order)
    assert vanilla_order[1] in processor_routes
    assert str(processor_routes.copy()) == str(processor_routes)
    assert vanilla_order[-1] == processor_routes[-1]
    assert processor_routes.count(processor_routes._routes[0]) == 1
    assert processor_routes != []
