"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import inspect
import json
import logging
from abc import ABC
from io import TextIOWrapper, StringIO
from json import JSONDecodeError
from typing import Generic, Any, TypeVar
from collections.abc import Callable, Mapping
import warnings

from pydantic import JsonValue, ValidationError
from pydantic_core import ErrorDetails
import python_multipart.multipart
from starlette.datastructures import FormData, UploadFile
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_404_NOT_FOUND,
    HTTP_501_NOT_IMPLEMENTED,
)

from opentelemetry import trace
from opentelemetry.semconv.trace import SpanAttributes

from f5_ai_gateway_sdk.result import Result, Reject
from f5_ai_gateway_sdk.signature import Signature
from f5_ai_gateway_sdk.multipart_fields import (
    INPUT_NAME,
    INPUT_PARAMETERS_NAME,
    RESPONSE_NAME,
    RESPONSE_PARAMETERS_NAME,
    METADATA_NAME,
    REQUIRED_MULTIPART_FIELDS,
    OPTIONAL_MULTIPART_FIELDS,
    DEFAULT_ENCODING,
    ALLOWED_ENCODINGS,
    HEADER_ENCODING,
)
from f5_ai_gateway_sdk.errors import (
    ResponseObjectError,
    MissingMultipartFieldError,
    MetadataParseError,
    ProcessExecutionError,
    ProcessorError,
    UnexpectedContentTypeError,
    ParametersParseError,
    MissingPromptAndResponseError,
    MultipartParseError,
    PromptParseError,
    ResponseParseError,
    InvalidMultipartFields,
    InvalidEncoding,
)
from f5_ai_gateway_sdk.request_input import RequestInput, Message
from f5_ai_gateway_sdk.response_output import ResponseOutput, Choice
from f5_ai_gateway_sdk.parameters import DefaultParameters, Parameters, EmptyParameters
from f5_ai_gateway_sdk.tags import Tags
from f5_ai_gateway_sdk.type_hints import (
    PROMPT,
    RESPONSE,
    Metadata,
    PARAMS,
    StreamingPrompt,
    StreamingResponse,
)

tracer = trace.get_tracer("processor_sdk")

T = TypeVar("T")
Transformer = Callable[[str | UploadFile], T]


class Processor(ABC, Generic[PROMPT, RESPONSE, PARAMS]):
    """
    Base class for a processor. A processor is a route that processes
    a prompt and metadata and returns a result.
    """

    def __init__(
        self,
        name: str,
        version: str,
        namespace: str,
        signature: Signature,
        prompt_class: type[PROMPT] = RequestInput,
        response_class: type[RESPONSE] = ResponseOutput,
        parameters_class: type[PARAMS] | None = None,
        app_details: dict[str, JsonValue] | None = None,
    ):
        """
        Creates a new instance of a Processor.

        :param name: name of processor (used in API definition)
        :param version: version of processor (used in API definition)
        :param namespace: optional namespace used to identify a group of processors
        :param signature: used to validate incoming requests
        :param prompt_class: type for class that defines the prompt class for the processor
        :param response_class: type for class that defines the response class for the processor
        :param parameters_class: type for class that defines the config parameters for the processor
        :param app_details: optional dictionary of application details (e.g. version, description)

        Example::

            class ExampleProcessor(Processor):
                def __init__(self):
                    super().__init__(
                        name="example-processor",
                        version="v1",
                        namespace="tutorial",
                        signature = BOTH_SIGNATURE
                    )

        """
        if type(self) is Processor:  # pylint: disable=unidiomatic-typecheck
            # this needs to be type() rather than isinstance() to avoid
            # subclass matching
            raise TypeError(
                "Processor is an abstract base class and cannot be instantiated directly."
            )
        if self.__contains_whitespace(name):
            raise ValueError("Processor name cannot contain whitespace")
        if self.__contains_whitespace(version):
            raise ValueError("Processor version cannot contain whitespace")
        if self.__contains_whitespace(namespace):
            raise ValueError("Processor namespace cannot contain whitespace")
        if parameters_class is not None and not issubclass(
            parameters_class, Parameters
        ):
            raise ValueError("parameters_class must be a subclass of Parameters")
        elif parameters_class == EmptyParameters:
            msg = "EmptyParameters will be deprecated. Please use DefaultParameters instead."
            warnings.warn(
                msg,
                DeprecationWarning,
                stacklevel=2,
            )
            logging.warning(msg)

        if signature is None:
            raise ValueError("Processor subclass must define signature")

        self._validate_supported_direction(signature)

        self.prompt_type = prompt_class
        """Type of the prompt content"""
        self.response_type = response_class
        """Type of the response content"""
        self.app_details = app_details
        """Runtime details of the application using the processor"""
        self.name = name
        """Name of the processor (without spaces)"""
        self.version = version
        """Version of the processor (independent of API version)"""
        self.namespace = namespace
        """Namespace of the processor (used to group processors)"""
        self.parameters_class = parameters_class or DefaultParameters
        """Class that defines the configuration parameters for the processor"""
        self.namespaced_path = f"{namespace.lower()}/{name.lower()}"
        """Namespaced path for the processor API"""
        self.path = f"/{{command:path}}/{self.namespaced_path}"
        """Path for the processor API that can be extended for subcommands"""
        self.methods = ["HEAD", "POST", "GET"]
        """Supported HTTP methods for the processor API"""
        self.signature = signature
        """Signature of the processor (used to verify requests)"""
        self.routes = [
            Route(
                path=self.path,
                methods=self.methods,
                name=self.name,
                endpoint=self.handle_request,
            ),
        ]
        self.span_attributes = {
            "processor_id": self.id(),
            "processor_version": self.version,
        }
        for key, value in (app_details or {}).items():
            self.span_attributes[f"app_{key}"] = str(value)

        """Starlette routes for the processor API"""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # Check if the subclass (cls) has provided its own implementations,
        # different from the ones in the Processor base class.
        is_process_overridden = cls.process is not Processor.process
        is_process_input_overridden = cls.process_input is not Processor.process_input
        is_process_response_overridden = (
            cls.process_response is not Processor.process_response
        )

        # A processor is considered validly defined if:
        # 1. It overrides the deprecated 'process' method and not the new methods.
        # OR
        # 2. It overrides AT LEAST ONE of the new methods ('process_input' or 'process_response')
        #    and not the deprecated method
        if not (
            is_process_input_overridden
            or is_process_response_overridden
            or is_process_overridden
        ):
            raise TypeError(
                f"Cannot create concrete class {cls.__name__}. "
                "It must override AT LEAST ONE of the following methods: "
                "'process_input', 'process_response'. "
                "Or alternatively the DEPRECATED 'process' method."
            )
        elif is_process_overridden and (
            is_process_input_overridden or is_process_response_overridden
        ):
            raise TypeError(
                f"Cannot create concrete class {cls.__name__}. "
                "The DEPRECATED 'process' method must not be implemented "
                "alongside 'process_input' or 'process_response'."
            )
        if is_process_overridden and inspect.iscoroutinefunction(cls.process):
            # we don't want to add async capabilities to the deprecated function
            raise TypeError(
                f"Cannot create concrete class {cls.__name__}. "
                "The DEPRECATED 'process' method does not support async. "
                "Implement 'process_input' and/or 'process_response' instead."
            )

        return

    def _validate_supported_direction(self, signature: Signature):
        """Validate that provided signature can be supported by implementation"""
        supports_input = self._is_method_overridden(
            "process"
        ) or self._is_method_overridden("process_input")

        if signature.supports_input() and not supports_input:
            raise TypeError(
                f"Cannot create concrete class {self.__class__.__name__}. "
                "Provided Signature supports input but 'process_input' "
                "is not implemented."
            )

        supports_response = self._is_method_overridden(
            "process"
        ) or self._is_method_overridden("process_response")
        if signature.supports_response() and not supports_response:
            raise TypeError(
                f"Cannot create concrete class {self.__class__.__name__}. "
                "Provided Signature supports response but 'process_response' "
                "is not implemented."
            )

    def id(self) -> str:
        if self.namespace is not None:
            return f"{self.namespace}:{self.name}"
        else:
            return self.name

    def execute_path(self) -> str:
        return f"/execute/{self.namespaced_path}"

    def signature_path(self) -> str:
        return f"/signature/{self.namespaced_path}"

    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "namespace": self.namespace or "",
            "id": self.id(),
            "path": self.execute_path(),
            "methods": sorted(list(self.methods)),
            "signature_path": self.signature_path(),
        }

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Processor):
            return (
                self.name == other.name
                and self.version == other.version
                and self.namespace == other.namespace
            )
        else:
            return False

    @staticmethod
    def __contains_whitespace(test: str) -> bool:
        return any(char.isspace() for char in test)

    def choose_span(self, name: str):
        """
        This method chooses the current span to use for the processor. If the current span is not recording,
        then it will return the current span which means that we don't start a new span that starts recording
        when we don't want it to. If the current span is recording, then we start a new span which automatically
        becomes a sub-span of the current span.

        :param name: name of span
        :return: current non-recording span or a new span
        """
        current_span = trace.get_current_span()
        if not current_span.is_recording():
            span = current_span
        else:
            span = tracer.start_span(name=name, attributes=self.span_attributes)

        return span

    async def handle_request(self, request: Request) -> Response:
        """
        This method handles all requests from the Starlette route and handles
        any errors that may occur during the processor execution.

        :param request: HTTP request in the AI Gateway Processor format
        :return: HTTP response in the AI Gateway Processor format
        """

        # noinspection PyUnusedLocal
        response = Response(status_code=HTTP_501_NOT_IMPLEMENTED)

        with self.choose_span(name="handle_request") as span:
            content_length = request.headers.get("Content-Length")
            if content_length:
                span.set_attribute(
                    SpanAttributes.HTTP_REQUEST_CONTENT_LENGTH, content_length
                )
            transfer_encoding = request.headers.get("Transfer-Encoding")
            if transfer_encoding:
                span.set_attribute("http.request_transfer_encoding", transfer_encoding)

            if request.method == "HEAD":
                response = Response(
                    status_code=HTTP_200_OK,
                    headers={
                        "Content-Type": f"multipart/form-data;charset={DEFAULT_ENCODING}"
                    },
                )
            else:
                # We wrap the main processing logic in a try-except block to catch any errors,
                # so that we can return a proper HTTP response to the client.
                try:
                    response = await self._handle_command(request)
                except ProcessorError as e:
                    # Only log errors that are not client errors
                    if e.status_code > 499:
                        span.record_exception(e)
                        logging.log(logging.ERROR, "%s", e, exc_info=True)
                    # Propagate the error to the client with json error detail
                    response = Response(
                        status_code=e.status_code,
                        headers={"Content-Type": "application/json"},
                        content=e.json_error(),
                    )

            span.set_attribute(
                SpanAttributes.HTTP_RESPONSE_STATUS_CODE, response.status_code
            )

        return response

    async def _handle_command(self, request: Request) -> Response:
        """
        This method handles requests that are routed to a command sub-route of a processor.
        :param request: request to be treated as a command
        :return: a response object with the appropriate status code and content for the command or an error response
        """

        default_response = Response(
            status_code=HTTP_404_NOT_FOUND,
            headers={"Content-Type": "application/json"},
            content=self._response_content(
                status_code=HTTP_404_NOT_FOUND,
                message="Not found",
            ),
        )

        if "command" not in request.path_params:
            return default_response

        # If the request is a POST request and the command is "execute",
        # try to process and return the request
        if request.path_params["command"] == "execute":
            if request.method != "POST":
                return Response(
                    status_code=HTTP_405_METHOD_NOT_ALLOWED,
                    headers={"Content-Type": "application/json"},
                    content=self._response_content(
                        status_code=HTTP_405_METHOD_NOT_ALLOWED,
                        message="Only POST requests are supported",
                    ),
                )

            response = await self._parse_and_process(request)
            return response

        # If the request is a GET request and the command is "signature",
        # return a JSON blob representing the signature of the processor - that is
        # what types of inputs are valid for the processor.
        elif request.path_params["command"] == "signature":
            if request.method != "GET" and request.method != "POST":
                return Response(
                    status_code=HTTP_405_METHOD_NOT_ALLOWED,
                    headers={"Content-Type": "application/json"},
                    content=self._response_content(
                        status_code=HTTP_405_METHOD_NOT_ALLOWED,
                        message="Only GET requests are supported",
                    ),
                )

            content = {
                "fields": self.signature.to_list(),
                "parameters": self.parameters_class.model_json_schema(),
            }
            status_code = HTTP_200_OK
            if request.method == "POST":
                # If the request is a POST request, validate that the provided
                # parameters are valid for the parameters class that this
                # processor expects. AIGW will use this endpoint to verify
                # that configuration in aigw.yaml is valid for a processor.
                validation = {"valid": True, "errors": []}
                body = await request.body()
                try:
                    self.parameters_class.model_validate_json(
                        json_data=body, strict=True
                    )
                except ValidationError as e:
                    validation["errors"] = _validation_error_as_messages(e)
                    validation["valid"] = False
                    status_code = HTTP_400_BAD_REQUEST
                content["validation"] = validation

            return Response(
                status_code=status_code,
                headers={"Content-Type": "application/json"},
                content=json.dumps(content),
            )

        return default_response

    @staticmethod
    def _extract_charset_encoding(
        content_type: str | None, fallback_encoding: str
    ) -> str:
        if not content_type:
            encoding = fallback_encoding
        else:
            _, params = python_multipart.multipart.parse_options_header(content_type)
            charset = params.get(b"charset")
            encoding = (
                charset.decode("us-ascii").lower() if charset else fallback_encoding
            )

        if encoding not in ALLOWED_ENCODINGS:
            raise InvalidEncoding(f"Unsupported text encoding: {encoding}")

        return encoding

    @staticmethod
    def _extract_multipart_field(
        form: FormData,
        field_name: str,
        error_class: type[MultipartParseError],
        root_content_type_encoding: str | None = None,
        transform_function: Transformer | None = None,
    ) -> Any:
        try:
            field = form.get(field_name)
            if field is None:
                return None
            elif transform_function:
                transformed = transform_function(field)
            elif isinstance(field, UploadFile):
                # Use the encoding specified in the content type header if available
                # Otherwise, use the default encoding
                fallback_encoding = (
                    root_content_type_encoding
                    if root_content_type_encoding
                    else DEFAULT_ENCODING
                )
                encoding = Processor._extract_charset_encoding(
                    field.content_type, fallback_encoding
                )
                transformed = TextIOWrapper(field.file, encoding=encoding)
            else:
                transformed = field

            return transformed
        except (UnicodeDecodeError, UnicodeError) as e:
            raise MultipartParseError(
                detail=f"Unable to decode field [{field_name}]: {e}"
            ) from e
        except ValidationError as e:
            raise error_class(messages=_validation_error_as_messages(e)) from e
        except ValueError as e:
            raise error_class() from e

    @staticmethod
    def _field_to_str(field_name: str, field_body: str | UploadFile) -> str:
        """
        Loads a multipart field into a string, conditionally forking logic
        based on whether we were passed a string or an UploadFile object.

        :param field_name: name of the field being loaded
        :param field_body: object to be loaded into JSON
        :param object_hook: optional deserialization handler
        :return: json object
        """
        if isinstance(field_body, UploadFile):
            with field_body.file as reader:
                data = reader.read().decode()
        elif isinstance(field_body, str):
            data = field_body
        else:
            raise ValueError(f"field must be a string or UploadFile [{field_name}]")

        return data

    @staticmethod
    def _field_to_json(
        field_name: str, field_body: str | UploadFile, object_hook=None
    ) -> Mapping[str, JsonValue]:
        """
        Loads a multipart field into a JSON object, conditionally forking logic
        based on whether we were passed a string or an UploadFile object.

        :param field_name: name of the field being loaded
        :param field_body: object to be loaded into JSON
        :param object_hook: optional deserialization handler
        :return: json object
        """
        if isinstance(field_body, UploadFile):
            with field_body.file as reader:
                json_content = json.load(reader, object_hook=object_hook)
        elif isinstance(field_body, str):
            try:
                json_content = json.loads(field_body, object_hook=object_hook)
            except JSONDecodeError as e:
                raise MultipartParseError(
                    detail=f"Unable to parse JSON field [{field_name}]: {e}"
                ) from e
        else:
            raise ValueError("field must be a string or UploadFile")

        return json_content

    def _parameters_transform(self, field_body: str | UploadFile) -> Parameters:
        span = trace.get_current_span()
        if field_body is None:
            span.set_attribute("parameters", "None")
            try:
                parameters = self.parameters_class()
            except ValidationError as e:
                raise ParametersParseError(
                    messages=_validation_error_as_messages(e)
                ) from e
        else:
            json_str = self._field_to_str(
                field_name="parameters",
                field_body=field_body,
            )
            try:
                parameters = self.parameters_class.model_validate_json(
                    json_data=json_str, strict=True
                )
                if span.is_recording():
                    for key, attribute in parameters.otel_attributes():
                        span.set_attribute(key, attribute)
            except ValidationError as e:
                raise ParametersParseError(
                    messages=_validation_error_as_messages(e)
                ) from e
            except TypeError as e:
                raise ParametersParseError() from e

        return parameters

    def _metadata_transform(self, field_body: str | UploadFile) -> Metadata:
        span = trace.get_current_span()

        if field_body is None:
            metadata = Metadata()
        else:
            json_content = self._field_to_json(
                field_name=METADATA_NAME, field_body=field_body
            )
            if not isinstance(json_content, dict):
                raise MetadataParseError(detail="metadata must be a JSON object")
            metadata = Metadata(**json_content)

        if span.is_recording():
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"metadata.{key}", value)
                else:
                    span.set_attribute(f"metadata.{key}", json.dumps(value))

        return metadata

    def _input_transform(self, field_body: str | UploadFile) -> RequestInput:
        if field_body is None:
            prompt = RequestInput(messages=[])
        else:
            prompt = self._field_to_json(
                field_name=INPUT_NAME,
                field_body=field_body,
            )
            prompt = RequestInput.model_validate(prompt)
            if not isinstance(prompt, RequestInput):
                raise MetadataParseError(detail="input.messages must be a JSON object")
        return prompt

    def _response_transform(self, field_body: str | UploadFile) -> ResponseOutput:
        if field_body is None:
            response = ResponseOutput(choices=[])
        else:
            response = self._field_to_json(
                field_name=RESPONSE_NAME,
                field_body=field_body,
            )
            response = ResponseOutput.model_validate(response)
            if not isinstance(response, ResponseOutput):
                raise MetadataParseError(
                    detail="response.choices must be a JSON object"
                )
        return response

    def _validate_and_find_parameters_name(self, form: FormData) -> str | None:
        """
        Validates the multipart form fields and returns the name of the parameters field if present.

        :param form: form containing fields
        :return: parameters field name if found, otherwise None
        :raises MissingMultipartFieldError: if a required field is missing
        :raises MissingPromptAndResponseError: if both prompt and response are missing
        :raises InvalidMultipartFields: if both prompt and response parameters are present
        """
        matched_input = False
        matched_response = False
        matched_input_parameters = False
        matched_response_parameters = False

        for required in REQUIRED_MULTIPART_FIELDS:
            if required not in form:
                raise MissingMultipartFieldError(field_name=required)

        # Modify the default values of the fields to True if they are present in the form
        for field in form:
            if field == INPUT_NAME:
                matched_input = True
            if field == RESPONSE_NAME:
                matched_response = True
            if field == INPUT_PARAMETERS_NAME:
                matched_input_parameters = True
            if field == RESPONSE_PARAMETERS_NAME:
                matched_response_parameters = True

        # We are processing a prompt response ONLY if it contains the RESPONSE_NAME field.
        # Otherwise, implicitly it is a prompt request.
        is_response_request = matched_response
        is_prompt_request = not is_response_request

        # Validate that either a prompt or a prompt response has been submitted
        if not matched_input and not matched_response:
            raise MissingPromptAndResponseError()

        if is_response_request:
            if not self.signature.supports_response():
                raise InvalidMultipartFields(
                    "Processor signature does not allow response fields"
                )

            if self.signature.required is not None:
                for required in map(lambda f: f.value, self.signature.required):
                    if required not in form:
                        raise InvalidMultipartFields(
                            f"Missing required field for response: {required}"
                        )

        if is_prompt_request:
            if not self.signature.supports_input():
                raise InvalidMultipartFields(
                    "Processor signature does not allow input fields"
                )

            if self.signature.required is not None:
                for required in map(lambda f: f.value, self.signature.required):
                    if required not in form:
                        raise InvalidMultipartFields(
                            f"Missing required field for input: {required}"
                        )

        # Validate that the correct parameters are being used
        if is_response_request and matched_input_parameters:
            raise InvalidMultipartFields(
                f"prompt parameters cannot be present with {RESPONSE_NAME} field"
            )
        if is_prompt_request and matched_response_parameters:
            raise InvalidMultipartFields(
                f"response parameters cannot be present with only a {INPUT_NAME} field"
            )

        # Choose the right parameters field based on the request type
        if matched_input_parameters:
            return INPUT_PARAMETERS_NAME
        elif matched_response_parameters:
            return RESPONSE_PARAMETERS_NAME
        else:
            return None

    @staticmethod
    async def _parse_and_validate_content_type_header(
        request: Request,
    ) -> tuple[bytes, dict[bytes, bytes]]:
        """
        Validates the headers of the incoming request to ensure that the
        Content-Type header is present, that it is a multipart/form-data,
        and that it contains a boundary parameter.
        :param request: request to read headers from
        :raises MultipartRequestError: if the headers are invalid"""

        raw_request_content_type = request.headers.get("Content-Type")
        if raw_request_content_type is None:
            raise UnexpectedContentTypeError(detail="Content-Type header missing")
        content_type, params = python_multipart.multipart.parse_options_header(
            raw_request_content_type
        )
        if not content_type or len(content_type) == 0:
            raise UnexpectedContentTypeError(detail="Content-Type header is empty")
        if content_type != b"multipart/form-data":
            raise UnexpectedContentTypeError(
                detail="Content-Type header mismatch - expecting: multipart/form-data"
            )
        if params.get(b"boundary") is None:
            raise UnexpectedContentTypeError(
                detail="Content-Type header missing boundary"
            )

        return content_type, params

    @staticmethod
    def _response_content(
        status_code: int,
        message: str,
    ) -> str:
        return json.dumps(
            {
                "message": message,
                "status_code": status_code,
            }
        )

    async def _parse_multipart_fields(
        self, root_content_type_encoding: str, form: FormData
    ) -> tuple:
        """
        Extract each expected multipart field from the form and transform it using predefined
        functions. Then, the prompt and response are converted to the appropriate type based on
        the processor's prompt_type and response_type. If there is no need for conversion,
        they are left as-is.

        :param root_content_type_encoding: character set encoding specified for the HTTP request (not multipart field)
        :param form: multipart form field to parse
        :return: tuple of metadata, parameters, prompt, and response
        """

        span = trace.get_current_span()
        span.set_attribute("multipart.fields", ", ".join(form.keys()))

        parameters_field = self._validate_and_find_parameters_name(form)
        # PARAMETERS
        if parameters_field:
            parameters = Processor._extract_multipart_field(
                form=form,
                field_name=parameters_field,
                error_class=ParametersParseError,
                transform_function=self._parameters_transform,
            )
        else:
            try:
                parameters = self.parameters_class()
            except ValidationError as e:
                raise ParametersParseError(
                    messages=_validation_error_as_messages(e)
                ) from e
            except Exception as e:
                raise ProcessExecutionError() from e

        # METADATA
        metadata = Processor._extract_multipart_field(
            form=form,
            field_name=METADATA_NAME,
            error_class=MetadataParseError,
            transform_function=self._metadata_transform,
        )
        # INPUT
        prompt = Processor._extract_multipart_field(
            form=form,
            field_name=INPUT_NAME,
            root_content_type_encoding=root_content_type_encoding,
            transform_function=self._input_transform,
            error_class=PromptParseError,
        )
        # RESPONSE
        response = Processor._extract_multipart_field(
            form=form,
            field_name=RESPONSE_NAME,
            root_content_type_encoding=root_content_type_encoding,
            transform_function=self._response_transform,
            error_class=ResponseParseError,
        )

        # This logic is to handle the conversion of the prompt and response fields to the appropriate type.
        # When a multipart field is received and contains a `filename` parameter in the Content-Disposition
        # header, Starlette will return an UploadFile object. This means that depending on the parameters
        # set in Content-Disposition, the field could be either a subclass of IO or a string.
        #
        # Unfortunately, there is a conflict between this behavior and the behavior possible in a subclass of
        # Processor. The prompt and response fields are expected to be of the type defined by the processor's
        # prompt_type and response_type (matching the generic type definition). As such, we may end up in a
        # situation where we need to convert a string to an IO object or vice versa.
        #
        # Ultimately, a comprehensive fix will involve a PR to Starlette or us no longer using the integrated
        # Starlette multipart form parsing. For now, we will handle the conversion here. Please note that despite
        # a prompt or response having a type of StreamingPrompt or StreamingResponse, the field may still
        # end up being loaded into memory before it is converted into a IO object.
        if self.prompt_type == StreamingPrompt and isinstance(prompt, str):
            prompt = StringIO(prompt)
        elif self.prompt_type == RequestInput and isinstance(prompt, TextIOWrapper):
            with prompt as reader:
                text = reader.read()
            prompt = RequestInput(messages=[Message(content=text)])
        if self.response_type == StreamingResponse and isinstance(response, str):
            response = StringIO(response)
        elif self.response_type == ResponseOutput and isinstance(
            response, TextIOWrapper
        ):
            with response as reader:
                text = reader.read()
            response = ResponseOutput(choices=[Choice(message=Message(content=text))])

        return metadata, parameters, prompt, response

    @tracer.start_as_current_span("parse_and_process")
    async def _parse_and_process(self, request: Request) -> Response:
        """
        This method executes the processor for the received request and will
        raise errors that inherit from ProcessorError.

        :param request: HTTP request in the AI Gateway Processor format
        :return: HTTP response in the AI Gateway Processor format
        """

        (
            _,
            content_type_params,
        ) = await Processor._parse_and_validate_content_type_header(request)
        charset = content_type_params.get(b"charset")
        root_content_type_encoding = (
            charset.decode(HEADER_ENCODING).lower() if charset else DEFAULT_ENCODING
        )
        max_fields = len(REQUIRED_MULTIPART_FIELDS) + len(OPTIONAL_MULTIPART_FIELDS)

        async with request.form(max_fields=max_fields, max_files=max_fields) as form:
            metadata, parameters, prompt, response = await self._parse_multipart_fields(
                root_content_type_encoding=root_content_type_encoding, form=form
            )
            input_direction = prompt is not None and response is None

            if metadata is None:
                raise MissingMultipartFieldError(field_name=METADATA_NAME)

            # This must be under the async block otherwise the IO streams will be closed
            with tracer.start_span(name="process") as span:
                try:
                    prompt_hash, response_hash = (None, None)
                    if input_direction:
                        prompt_hash = prompt.hash()
                        result = await self._handle_process_function(
                            self.process_input,
                            metadata=metadata,
                            parameters=parameters,
                            prompt=prompt,
                            request=request,
                        )

                    else:
                        response_hash = response.hash()
                        result = await self._handle_process_function(
                            self.process_response,
                            metadata=metadata,
                            parameters=parameters,
                            prompt=prompt,
                            response=response,
                            request=request,
                        )

                    if not result:
                        raise ProcessExecutionError(
                            detail=f"Processor[{self.id()}] process() method returned None"
                        )

                    # unless the response is empty we create a metadata to
                    # store common fields. The empty case results in a 204
                    if result.metadata is None and not result.is_empty:
                        result.metadata = Metadata()

                    if result.metadata is not None:
                        result.metadata["processor_id"] = self.id()
                        result.metadata["processor_version"] = self.version

                        if "request_id" in metadata:
                            result.metadata["request_id"] = metadata["request_id"]
                        if "step_id" in metadata:
                            result.metadata["step_id"] = metadata["step_id"]

                        if self.app_details is not None:
                            result.metadata["app_details"] = self.app_details

                    attributes = {
                        "metadata": json.dumps(result.metadata or {}),
                        "rejected": False,
                        "modified": False,
                    }

                    if result.tags:
                        attributes["tags"] = str(result.tags)

                    match result:
                        case Result():
                            # check if prompt or reponse are different from what
                            # was submitted
                            modified = (
                                result.modified_prompt is not None
                                and prompt_hash != result.modified_prompt.hash()
                            ) or (
                                result.modified_response is not None
                                and response_hash != result.modified_response.hash()
                            )

                            # No modification detect, avoid sending back
                            # unmodified data
                            if not modified and (
                                result.modified_prompt is not None
                                or result.modified_response is not None
                            ):
                                result.modified_prompt = None
                                result.modified_response = None

                            # validate if modifications are allowed after
                            # resetting any no-change modifications above
                            result.validate_allowed(
                                self.__class__.__name__,
                                parameters.annotate,
                                parameters.modify,
                            )

                            attributes["modified"] = modified
                            if result.processor_result:
                                attributes["processor_result"] = json.dumps(
                                    result.processor_result
                                )

                        case Reject():
                            if not parameters.reject:
                                logging.warning(
                                    "%s tried to reject request when parameters.reject was set to false, rejection will be dropped",
                                    self.__class__.__name__,
                                )
                                result = Result(metadata=result.metadata)
                            else:
                                attributes["rejected"] = True
                        case _:
                            logging.error(
                                "%s invokation returned an unexpected response type '%s' instead of Result or Reject",
                                self.__class__.__name__,
                                type(result),
                            )
                            raise ResponseObjectError()

                    span.add_event(name="result", attributes=attributes)

                except (ProcessExecutionError, ResponseObjectError) as e:
                    raise e
                except Exception as e:
                    raise ProcessExecutionError() from e

        if result is None:
            raise ProcessExecutionError(
                detail=f"Processor[{self.id()}] process() method returned None"
            )

        try:
            return result.to_response()
        except Exception as e:
            raise ResponseObjectError() from e

    def _is_method_overridden(self, method_name: str) -> bool:
        """
        Checks if a method is overridden in a subclass.
        Compares the method object (function) in the instance's class
        to the method object (function) in this base Processor class.
        """
        # Get the method (which is a function object) from the instance's actual class.
        # If not overridden, this will resolve to the method in the base class via MRO.
        instance_class_method_obj = getattr(type(self), method_name, None)

        # Get the method (function object) directly from the Processor base class.
        base_class_method_obj = getattr(Processor, method_name, None)

        if instance_class_method_obj is None or base_class_method_obj is None:
            # This might happen if method_name is misspelled, or if a method was expected
            # to be in Processor but isn't, or if it was somehow removed from a subclass.
            # For the check "is overridden", if one of them doesn't exist, it's safer to say no.
            return False

        # If the method object found via the instance's class is different from
        # the method object directly from the Processor class, then it has been overridden.
        return instance_class_method_obj is not base_class_method_obj

    async def _process_fallback(self, **kwargs) -> Result | Reject:
        warnings.warn(
            f"{type(self).__name__} uses the deprecated 'process' method. "
            "Implement 'process_input' and/or 'process_response' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self._handle_process_function(self.process, **kwargs)

    async def process_input(
        self,
        prompt: PROMPT,
        metadata: Metadata,
        parameters: PARAMS,
        request: Request,
    ) -> Result | Reject:
        """
        This abstract method is for implementors of the processor to define
        with their own custom logic. Errors should be raised as a subclass
        of ProcessorError. The return value should be a Result or Reject object.

        :param prompt: Optional prompt content to be evaluated
        :param metadata: Prompt/Response metadata
        :param parameters: Processor parameters - configuration sent by gateway
        :param request: Original HTTP request
        :return: Result object indicating if the request was rejected, accepted, or modified

        Example::

            def process_input(self, prompt, response, metadata, parameters, request):
                target_found = False
                target_str = "target"

                target_found = any(target_str in message.content for message in prompt.messages)
                result = Metadata({"target_found": target_found})

                return Result(processor_result=result)
        """
        if not self._is_method_overridden("process"):
            raise NotImplementedError(
                f"{type(self).__name__} must implement 'process_input' or the "
                "deprecated 'process' method to handle input."
            )
        return await self._process_fallback(
            prompt=prompt,
            response=None,
            metadata=metadata,
            parameters=parameters,
            request=request,
        )

    async def process_response(
        self,
        prompt: PROMPT | None,
        response: RESPONSE,
        metadata: Metadata,
        parameters: PARAMS,
        request: Request,
    ) -> Result | Reject:
        """
        This abstract method is for implementors of the processor to define
        with their own custom logic. Errors should be raised as a subclass
        of ProcessorError. The return value should be a Result or Reject object.

        :param prompt: Optional prompt content to be evaluated
        :param response: Optional response content to be evaluated
        :param metadata: Prompt/Response metadata
        :param parameters: Processor parameters - configuration sent by gateway
        :param request: Original HTTP request
        :return: Result object indicating if the request was rejected, accepted, or modified

        Example::

            def process_response(self, prompt, response, metadata, parameters, request):
                target_found = False
                target_str = "target"

                target_found = any(
                    target_str in choice.message.content for choice in response.choices
                )
                result = Metadata({"target_found": target_found})

                return Result(processor_result=result)
        """

        if not self._is_method_overridden("process"):
            raise NotImplementedError(
                f"{type(self).__name__} must implement 'process_response' or the "
                "deprecated 'process' method to handle input."
            )
        return await self._process_fallback(
            prompt=prompt,
            response=response,
            metadata=metadata,
            parameters=parameters,
            request=request,
        )

    def process(
        self,
        prompt: PROMPT | None,
        response: RESPONSE | None,
        metadata: Metadata,
        parameters: PARAMS,
        request: Request,
    ) -> Result | Reject:
        """
        DEPRECATED: Implement 'process_input' and/or 'process_response' instead.

        This abstract method is for implementors of the processor to define
        with their own custom logic. Errors should be raised as a subclass
        of ProcessorError. The return value should be a Result or Reject object.

        :param prompt: Optional prompt content to be evaluated
        :param response: Optional response content to be evaluated
        :param metadata: Prompt/Response metadata
        :param parameters: Processor parameters - configuration sent by gateway
        :param request: Original HTTP request
        :return: Result object indicating if the request was rejected, accepted, or modified

        Example::

            def process(self, prompt, response, metadata, parameters, request):
                target_found = False
                target_str = "target"

                if response:
                    target_found = any(
                        target_str in choice.message.content for choice in response.choices
                    )
                elif prompt:
                    target_found = any(target_str in message.content for message in prompt.messages)

                result = Metadata({"target_found": target_found})

                return Result(processor_result=result)
        """
        raise NotImplementedError(
            "Processor subclasses must implement 'process' (deprecated) or "
            "'process_input'/'process_response'."
        )

    async def _handle_process_function(self, func, **kwargs) -> Result | Reject:
        if inspect.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = func(**kwargs)
        return result


def _validation_error_as_messages(err: ValidationError) -> list[str]:
    return [_error_details_to_str(e) for e in err.errors()]


def _error_details_to_str(err: ErrorDetails) -> str:
    """
    Returns a string summary of a pydantic ErrorDetails object.

    :param err: ErrorDetails object to summarize
    :return: String summary of the error
    """
    message = err["msg"] if "msg" in err else "unknown error"
    if "msg" not in err:
        logging.log(logging.WARNING, "no details found in error: %s", err)
    if "loc" in err and len(err["loc"]) > 0:
        loc_strings = [str(loc) for loc in err["loc"]]
        message = f"{message}: {','.join(loc_strings)}"
    return message


__all__ = ["Processor", "Result", "Reject", "Tags"]
