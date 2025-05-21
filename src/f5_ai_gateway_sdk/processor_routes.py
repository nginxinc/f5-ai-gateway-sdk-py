"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json
from io import StringIO
from typing import Any
from collections.abc import Iterable, Sequence

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.routing import Route, BaseRoute, Mount
from starlette.status import HTTP_200_OK, HTTP_405_METHOD_NOT_ALLOWED

from f5_ai_gateway_sdk.type_hints import JSON
from f5_ai_gateway_sdk.processor import Processor


class ProcessorRoutes(Route, Sequence[BaseRoute]):
    """
    A collection of routes for a set of processors that can be used to create a Starlette app. Each processor will map
    to multiple Routes.

    :param processors: Processors to load as routes
    :param root_path: Root path of processor server
    """

    sdk_version = "v1"
    api_versions = tuple(["v1"])

    def __init__(self, processors: Iterable[Processor], root_path: str | None = None):
        """
        Create a new ProcessorRoutes object

        :param processors: processors to load as routes
        :param root_path: root path of processor server

        Example::

            routes=ProcessorRoutes([MyProcessor()])

            # Create a Starlette app
            app = Starlette(routes=routes)

            # Or create a FastAPI app
            app = FastAPI(routes=routes)

        """
        super().__init__(
            path="/info",
            name="processor-routes",
            methods=["HEAD", "GET"],
            endpoint=self.handle_request,
        )

        self.root_path = "/" if not root_path else root_path
        self._routes = tuple(
            [
                Mount(
                    f"/api/{version}",
                    routes=[self]
                    + [route for processor in processors for route in processor.routes],
                )
                for version in self.api_versions
            ]
            + [Route("/", endpoint=self.info_redirect)]
        )
        self._processors = tuple(processors)

    def __getitem__(self, index):
        return self._routes[index]

    def __len__(self):
        return len(self._routes)

    def __iter__(self):
        return iter(self._routes)

    def __contains__(self, item):
        return item in self._routes

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, list):
            return self._routes == other
        elif isinstance(other, ProcessorRoutes):
            return self._routes == other._routes
        else:
            return super().__eq__(other)

    def copy(self):
        return ProcessorRoutes(processors=self._processors)

    def processor_simple_path(self, processor: Processor):
        return self.root_path.rstrip("/") + processor.execute_path()

    def processor_signature_path(self, processor: Processor):
        return self.root_path.rstrip("/") + processor.signature_path()

    def to_dict(self):
        def processor_to_dict(processor: Processor):
            processor_dict = processor.to_dict()
            processor_dict["path"] = self.processor_simple_path(processor)
            return processor_dict

        return {
            "name": self.name,
            "id": self.id(),
            "path": self.root_path,
            "methods": sorted(list(self.methods if self.methods else [])),
            "processors": list(map(processor_to_dict, self._processors)),
        }

    def id(self):
        return "processor-routes"

    def routes_as_json(self) -> JSON:
        return json.dumps(
            {
                "api_versions": self.api_versions,
                "processors": [
                    {
                        "name": str(processor.name),
                        "namespace": str(processor.namespace),
                        "id": processor.id(),
                        "available_versions": [processor.version],
                        "latest_version": processor.version,
                        "execute_path": self.processor_simple_path(processor),
                        "signature_path": self.processor_signature_path(processor),
                    }
                    for processor in self._processors
                ],
            }
        )

    def routes_as_plaintext(self) -> str:
        paths = map(self.processor_simple_path, self._processors)
        return "\n".join(paths)

    def routes_as_html(self) -> str:
        appender = StringIO()
        appender.write(
            '<!DOCTYPE html><html><head><meta charset="utf-8" />'
            "<title>Processor Routes</title>"
            "<style>"
            "body { font-family: Arial, sans-serif; margin: 20px; }"
            "table { width: 100%; border-collapse: collapse; margin-top: 20px; }"
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }"
            "th { background-color: #f4f4f4; }"
            "</style>"
            "</head><body>"
            "<h2>Processor Routes</h2>"
            "<table>"
            "<tr><th>Processor ID</th><th>Simple Path (HEAD, POST)</th><th>Signature Path (GET, POST)</th></tr>"
        )

        for processor in self._processors:
            processor_simple_path = self.processor_simple_path(processor)
            processor_signature_path = self.processor_signature_path(processor)

            appender.write(
                f"<tr>"
                f"<td>{processor.id()}</td>"
                f'<td><a href=".{processor_simple_path}">{processor_simple_path}</a></td>'
                f'<td><a href=".{processor_signature_path}">{processor_signature_path}</a></td>'
                f"</tr>"
            )

        appender.write("</table></body></html>")

        return appender.getvalue()

    def routes_as_markdown(self) -> str:
        appender = StringIO()
        appender.write("# Processors\n")

        toc = dict()
        for processor in self._processors:
            if not toc.get(processor.namespace):
                toc[processor.namespace] = [(processor.name, processor.id())]
            else:
                toc[processor.namespace].append((processor.name, processor.id()))

        for namespace, processors in toc.items():
            appender.write(f"- {namespace}\n")
            for processor in processors:
                appender.write(f"\t- [{processor[0]}](#{processor[1]})\n")

        for processor in self._processors:
            # heading
            appender.write(f"## {processor.id()}\n\n")

            if (
                processor.app_details is not None
                and "description" in processor.app_details
            ):
                appender.write(f"{processor.app_details['description']}\n\n")

            appender.write("### Configuration\n")
            # supports input and/or response stages
            allow_input = "Yes" if processor.signature.supports_input() else "No "
            allow_response = "Yes" if processor.signature.supports_response() else "No "
            appender.write(
                "\n| Direction | Supported |\n"
                "| --------- |-----------|\n"
                f"| Input     | {allow_input}       |\n"
                f"| Response  | {allow_response}       |\n"
            )

            appender.write("\n\n### Parameters\n\n")

            param_schema = processor.parameters_class.model_json_schema()
            if description := param_schema.get("description"):
                appender.write(f"{description}\n\n")

            if properties := param_schema.get("properties"):
                if len(properties):
                    appender.write(
                        "| Parameters | Description | Type |Required | Defaults | Examples |\n"
                        "|-|-|-|-|-|-|\n"
                    )
                for prop, details in properties.items():
                    default = details.get("default", "")
                    if default != "":
                        default = f"`{default}`"
                    appender.write(
                        f"| `{prop}` | "
                        f"{details.get('description', '')} |"
                        f"{details.get('type', '')} |"
                        f"{details.get('required', '')} |"
                        f"{default} |"
                        f"{details.get('examples', '')} |\n"
                    )
                appender.write("\n\n")

        return appender.getvalue()

    async def handle_request(self, request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=HTTP_200_OK)
        elif request.method == "GET":
            accept = request.headers.get("Accept") or ""

            if "text/plain" in accept:
                content = self.routes_as_plaintext()
            elif "text/html" in accept:
                content = self.routes_as_html()
            elif "text/markdown" in accept:
                content = self.routes_as_markdown()
            else:
                content = self.routes_as_json()

            return Response(status_code=HTTP_200_OK, content=content)
        else:
            return Response(status_code=HTTP_405_METHOD_NOT_ALLOWED)

    async def info_redirect(self, _: Request) -> Response:
        return RedirectResponse(url=f"/api/{self.api_versions[-1]}/info")


__all__ = ["ProcessorRoutes"]
