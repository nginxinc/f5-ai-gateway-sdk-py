"""
Processor SDK for F5 AI Gateway

Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

# F403 - deals with ruff's detection of underpinning objects beneath '*' to determine whether they are used here or not
from f5_ai_gateway_sdk.errors import *  # noqa: F403
from f5_ai_gateway_sdk.processor import *  # noqa: F403
from f5_ai_gateway_sdk.processor_routes import *  # noqa: F403
from f5_ai_gateway_sdk.result import *  # noqa: F403
from f5_ai_gateway_sdk.signature import *  # noqa: F403
from f5_ai_gateway_sdk.parameters import *  # noqa: F403
from f5_ai_gateway_sdk.request_input import *  # noqa: F403
from f5_ai_gateway_sdk.response_output import *  # noqa: F403
from f5_ai_gateway_sdk import multipart_fields
from f5_ai_gateway_sdk import multipart_response
from f5_ai_gateway_sdk import type_hints
from f5_ai_gateway_sdk import Tags


# F405 - deals with non-explicitly defined variables within the namespace that are imported via '*'
__all__ = [
    "ALL_PREDEFINED_SIGNATURES",  # noqa: F405
    "BOTH_RESPONSE_PROMPT_SIGNATURE",  # noqa: F405
    "BOTH_SIGNATURE",  # noqa: F405
    "INPUT_ONLY_SIGNATURE",  # noqa: F405
    "Choice",  # noqa: F405
    "Parameters",  # noqa: F405
    "ProcessExecutionError",  # noqa: F405
    "Processor",  # noqa: F405
    "ProcessorError",  # noqa: F405
    "ProcessorRoutes",  # noqa: F405
    "RESPONSE_AND_PROMPT_SIGNATURE",  # noqa: F405
    "RESPONSE_ONLY_SIGNATURE",  # noqa: F405
    "Result",  # noqa: F405
    "Reject",  # noqa: F405
    "RejectCode",  # noqa: F405
    "RequestInput",  # noqa: F405
    "ResponseOutput",  # noqa: F405
    "Signature",  # noqa: F405
    "SignatureField",  # noqa: F405
    "Message",  # noqa: F405
    "MessageRole",  # noqa: F405
    "multipart_fields",
    "multipart_response",  # noqa: F405
    "type_hints",
    "Tags",  # noqa: F405
]
