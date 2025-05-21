"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Offers a means to stand up starlette testclient's without having to import or handle anything in tests.
"""

import pytest
from starlette.applications import Starlette
from starlette import testclient

from f5_ai_gateway_sdk.processor import Processor
from f5_ai_gateway_sdk.processor_routes import ProcessorRoutes
from tests.libs import exceptions


@pytest.fixture
def processor_client_loader():
    """Loader factory for loading any processor that fulfills the python-starlet-processor SDK."""

    def get_testclient(processor: Processor) -> testclient.TestClient:
        """Generate a TestClient based upon the provided Processor."""
        # - verify given
        if not isinstance(processor, (expected := Processor)):
            raise exceptions.TestTypeError(
                f"expected {expected} type not {type(processor)}"
            )

        # - generate and return client
        constructed_app = Starlette(debug=True, routes=processor.routes)
        client = testclient.TestClient(app=constructed_app)
        return client

    return get_testclient


@pytest.fixture
def processor_routes_client_loader():
    """Loader for creating a ProcessorRoutes object."""

    def get_testclient(routes: ProcessorRoutes) -> testclient.TestClient:
        """Generate and return, as a factory, starlette test clients from provided ProcessorRoutes."""
        # - verify given
        if not isinstance(routes, (expected := ProcessorRoutes)):
            raise exceptions.TestTypeError(
                f"expected {expected} type not {type(routes)}"
            )

        # - generate and return client
        constructed_app = Starlette(debug=True, routes=routes)
        return testclient.TestClient(constructed_app)

    return get_testclient
