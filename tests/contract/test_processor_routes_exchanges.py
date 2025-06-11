"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Verify certain contractual exchanges against a stood up processor.
"""

from starlette import status as http_status_codes
from starlette.routing import Mount

from f5_ai_gateway_sdk.processor_routes import ProcessorRoutes
from ..libs.fakes import processors as fake_processors

EXPECTED_API_VERSIONS = 1


def test_processor_routes_simple(processor_routes_client_loader, test_logger):
    """Assure that we can have simplicity."""
    processor_routes = ProcessorRoutes([])
    # one for /api/<version> and a redirect to there from /
    assert len(processor_routes) == 2
    client = processor_routes_client_loader(processor_routes)
    assert (
        response := client.head("/")
    ).status_code == http_status_codes.HTTP_200_OK, (
        f"({response.status_code}) {response.url}"
    )


def test_processor_routes_mounted_routes(processor_routes_client_loader, test_logger):
    """API version mounts are created and populated with /info"""
    processor_routes = ProcessorRoutes([])
    assert len(processor_routes) == 2
    mounts = [route for route in processor_routes if isinstance(route, Mount)]
    assert len(mounts) == EXPECTED_API_VERSIONS
    assert len(mounts[0].routes) == 1
    client = processor_routes_client_loader(processor_routes)
    assert (
        response := client.head("/")
    ).status_code == http_status_codes.HTTP_200_OK, (
        f"({response.status_code}) {response.url}"
    )


def test_processor_routes_get_no_accept(
    data_loader, processor_routes_client_loader, test_logger
):
    """Assure that we can have simplicity."""
    processor_routes = ProcessorRoutes([])
    expected_response = data_loader("empty_processor_routes.json")
    assert len(processor_routes) == 2
    client = processor_routes_client_loader(processor_routes)
    assert (
        response := client.get("/", headers={})
    ).status_code == http_status_codes.HTTP_200_OK, (
        f"({response.status_code}) {response.url}"
    )
    assert (result := response.json()) == expected_response, (
        f"simple get got {result} instead of {expected_response}"
    )


def test_processor_routes_get_empty_accept(processor_routes_client_loader, test_logger):
    """Assure that we can have simplicity."""
    processor_routes = ProcessorRoutes([])
    assert len(processor_routes) == 2
    client = processor_routes_client_loader(processor_routes)
    assert (
        response := client.get("/", headers={"Accept": "text/plain"})
    ).status_code == http_status_codes.HTTP_200_OK, (
        f"({response.status_code}) {response.url}"
    )
    assert (result := response.text) == "", (
        f"received additional text, {result}, outside of an empty GET"
    )


def test_processor_routes_get_accept_json(
    data_loader, processor_routes_client_loader, test_logger
):
    """Assure that we can have simplicity for listing endpoints via json."""
    processor_routes = ProcessorRoutes([])
    expected_response = data_loader("empty_processor_routes.json")
    assert len(processor_routes) == 2
    client = processor_routes_client_loader(processor_routes)
    assert (
        response := client.get("/", headers={"Accept": "application/json"})
    ).status_code == http_status_codes.HTTP_200_OK, (
        f"({response.status_code}) {response.url}"
    )
    assert (result := response.json()) == expected_response, (
        f"simple get got {result} instead of {expected_response}"
    )


def test_processor_routes_get_accept_html(
    data_loader, processor_routes_client_loader, test_logger
):
    """Assure that we can have simplicity for listing empty html result."""
    processor_routes = ProcessorRoutes([])
    expected_response = data_loader("empty_processor_routes.html").strip()
    assert len(processor_routes) == 2
    client = processor_routes_client_loader(processor_routes)
    assert (
        response := client.get("/", headers={"Accept": "text/html"})
    ).status_code == http_status_codes.HTTP_200_OK, (
        f"({response.status_code}) {response.url}"
    )
    print(expected_response)
    assert (result := response.text.strip()) == expected_response, (
        f"simple get got {result} instead of {expected_response}"
    )


def test_processor_routes_get_accept_markdown(
    data_loader, processor_routes_client_loader, test_logger
):
    """Assure that we can have simplicity for listing empty html result."""
    processor_routes = ProcessorRoutes([])
    expected_response = data_loader("empty_processor_routes.md").strip()
    assert len(processor_routes) == 2
    client = processor_routes_client_loader(processor_routes)
    assert (
        response := client.get("/", headers={"Accept": "text/markdown"})
    ).status_code == http_status_codes.HTTP_200_OK, (
        f"({response.status_code}) {response.url}"
    )
    assert (result := response.text.strip()) == expected_response, (
        f"simple get got {result} instead of {expected_response}"
    )


def test_processor_routes_get_with_one_processor(
    data_loader, processor_routes_client_loader, test_logger
):
    html_template = """<!DOCTYPE html><html><head><meta charset="utf-8" /><title>Processor Routes</title><style>body 
{font_family}table {width}th, td {border}th {background}</style></head><body><h2>Processor Routes</h2><table><tr><th>Processor ID</th><th>Simple Path (HEAD, POST)</th><th>Signature Path (GET, POST)</th></tr><tr>
<td>testing:judgy</td><td><a href="./execute/{namespace}/{processor}">/execute/{namespace}/{processor}</a></td><td>
<a href="./signature/testing/judgy">/signature/testing/judgy</a></td></tr></table></body></html> 
    """.replace("\n", "")

    processor_name = "judgy"
    processor_version = "1.1"
    processor_namespace = "testing"
    font_family = "{ font-family: Arial, sans-serif; margin: 20px; }"
    border = "{ border: 1px solid #ddd; padding: 8px; text-align: left; }"
    width = "{ width: 100%; border-collapse: collapse; margin-top: 20px; }"
    background = "{ background-color: #f4f4f4; }"
    expected_response = html_template.format(
        processor=processor_name,
        namespace=processor_namespace,
        font_family=font_family,
        border=border,
        width=width,
        background=background,
    ).strip()
    judgy = fake_processors.JudgyAsync(
        processor_name,
        processor_version,
        processor_namespace,
        parameters_class=fake_processors.JudgyParameters,
    )
    processor_routes = ProcessorRoutes([judgy])
    assert len(processor_routes) == 2
    mounts = [route for route in processor_routes if isinstance(route, Mount)]
    assert len(mounts) == EXPECTED_API_VERSIONS
    assert len(mounts[0].routes) == 2
    client = processor_routes_client_loader(processor_routes)
    print(expected_response)

    assert (
        response := client.get("/", headers={"Accept": "text/html"})
    ).status_code == http_status_codes.HTTP_200_OK, (
        f"({response.status_code}) {response.url}"
    )
    assert (result := response.text.strip()) == expected_response, (
        f"simple get got {result} instead of {expected_response}"
    )
