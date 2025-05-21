"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind

SUPPRESSED_EVENT_TYPES = {"http.request", "http.response.start", "http.response.body"}

EVENT_TYPE_KEY = "asgi.event.type"


class QuieterBatchSpanProcessor(BatchSpanProcessor):
    """
    Span processor that filters out excessive FastAPI spans.
    :see: https://github.com/open-telemetry/opentelemetry-python-contrib/issues/831
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_end(self, span: ReadableSpan) -> None:
        if span.kind == SpanKind.INTERNAL and span.attributes:
            event_type = span.attributes.get(EVENT_TYPE_KEY, None)
            if event_type and event_type in SUPPRESSED_EVENT_TYPES:
                return

        super().on_end(span=span)
