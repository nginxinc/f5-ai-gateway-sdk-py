"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

SDK Processor that is dynamically judgy based upon the request and is self-aware for reporting.
"""

import asyncio
import functools
from pydantic import Field
from starlette.requests import Request

from f5_ai_gateway_sdk import errors
from f5_ai_gateway_sdk.request_input import RequestInput
from f5_ai_gateway_sdk.response_output import ResponseOutput
from f5_ai_gateway_sdk.parameters import Parameters
from f5_ai_gateway_sdk.processor import Processor
from f5_ai_gateway_sdk.result import Reject, Result, RejectCode
from f5_ai_gateway_sdk.signature import BOTH_SIGNATURE
from f5_ai_gateway_sdk.type_hints import Metadata


class JudgyParameters(Parameters):
    """Held mechanics around controlling Judgy, the Processor.

    Holds useful requirements around how Judgy, the Processor, will behave during runtime as it governs itself within
    its sphere of influence.
    """

    # Controls:
    # ToDo: update these controls as the MultipartResponse changes this
    # whether to reject all that was given
    should_reject: bool | None = Field(default=None)
    # what to reject with
    reject_reason: dict[str, str] | None = Field(default=None)
    # whether to flag the response as modified
    modified: bool | None = Field(default=None)
    # what is modified
    modified_result: dict[str, str] | None = Field(default=None)
    # why modification took place
    modified_reason: str | None = Field(default=None)
    # raise if raising == prompt and they're of the same type
    raising: str | None = None
    # add a set type which cannot be represented in JSON to verify pydantic conversion
    set_data: set[str] = Field(default_factory=set)
    # skip setting metadata on the response
    skip_metadata: bool = False

    def __post_init__(self):
        """Verify that each of the types are as expected.

        Verifies, as a Parameters class could use built-in errors for Processor, the contents of the dataclass by
        types as expected by definition.
        """
        if any(
            (
                illegal_types := {
                    attr: getattr(self, attr)
                    for attr in ["reject", "modified"]
                    if not isinstance(getattr(self, attr), (bool, type(None)))
                }
            )
        ):
            raise TypeError(f"illegal non-boolean values in {illegal_types}")
        if any(
            (
                illegal_types := {
                    attr: getattr(self, attr)
                    for attr in ["reject_reason", "modified_result"]
                    if not isinstance(getattr(self, attr), (dict, type(None)))
                }
            )
        ):
            raise TypeError(f"illegal non-dict values in {illegal_types}")
        if any(
            (
                illegal_types := {
                    attr: getattr(self, attr)
                    for attr in ["modified_reason"]
                    if not isinstance(getattr(self, attr), (str, type(None)))
                }
            )
        ):
            raise TypeError(f"illegal non-str values in {illegal_types}")


class JudgyRequiredParameters(JudgyParameters):
    required_message: str


class JudgySync(Processor):
    """Complete processor that behaves differently depending on JudgyParameters settings."""

    @classmethod
    def uses_process_method(cls):
        return False

    def __init__(self, *processor_args, **processor_kwargs):
        """Allow for exceptions to be raised from Judgy during process()."""
        self.raise_error = None
        super().__init__(signature=BOTH_SIGNATURE, *processor_args, **processor_kwargs)

    async def process_input(
        self,
        prompt: RequestInput,
        metadata: Metadata,
        parameters: JudgyParameters,
        request: Request,
    ) -> Result | Reject:
        return self._internal_process(
            prompt=prompt,
            metadata=metadata,
            parameters=parameters,
            request=request,
        )

    async def process_response(
        self,
        prompt: RequestInput,
        response: ResponseOutput,
        metadata: Metadata,
        parameters: JudgyParameters,
        request: Request,
    ) -> Result | Reject:
        return self._internal_process(
            prompt=prompt,
            response=response,
            metadata=metadata,
            parameters=parameters,
            request=request,
        )

    def _internal_process(
        self,
        prompt: RequestInput,
        metadata: Metadata,
        parameters: JudgyParameters,
        request: Request,
        response: ResponseOutput | None = None,
    ) -> Result | Reject:
        """Respond dynamically based upon parameters given to the object initially by the test."""
        if isinstance((raise_error := self.raise_error), Exception):
            raise raise_error
        if not isinstance((used_parameters := parameters), JudgyParameters):
            used_parameters = self.parameters
        if used_parameters.should_reject:
            reject = Reject(
                code=RejectCode.POLICY_VIOLATION,
                detail="",
            )
            if not parameters.skip_metadata:
                reject.metadata = metadata
            return reject
        my_response = dict()
        if not parameters.skip_metadata:
            my_response["metadata"] = metadata
        if reason := used_parameters.modified_reason:
            my_response["processor_result"] = dict(reason=reason)
        if prompt and used_parameters.modified:
            my_response["modified_prompt"] = prompt
        if response and used_parameters.modified:
            my_response["modified_response"] = response
        if (
            isinstance(prompt, type(parameters.raising))
            and prompt == parameters.raising
        ):
            raise errors.ProcessExecutionError(
                f"judgy: {prompt} matches {parameters.raising}"
            )
        return Result(**my_response)


class JudgyAsync(Processor):
    """
    Implementation using async methods for process_input and process_response
    """

    @classmethod
    def uses_process_method(cls):
        return False

    def __init__(self, *processor_args, **processor_kwargs):
        """Allow for exceptions to be raised from Judgy during process()."""
        self.raise_error = None
        self._internal_judgy = JudgySync(*processor_args, **processor_kwargs)
        super().__init__(signature=BOTH_SIGNATURE, *processor_args, **processor_kwargs)

    async def process_input(self, **kwargs) -> Result | Reject:
        if isinstance((raise_error := self.raise_error), Exception):
            raise raise_error
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(self._internal_judgy._internal_process, **kwargs)
        )

    async def process_response(self, **kwargs) -> Result | Reject:
        if isinstance((raise_error := self.raise_error), Exception):
            raise raise_error
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(self._internal_judgy._internal_process, **kwargs)
        )


class DeprecatedJudgy(Processor):
    """
    Implementation using the deprecated process method instead of process_input and process_response
    """

    @classmethod
    def uses_process_method(cls):
        return True

    def __init__(self, *processor_args, **processor_kwargs):
        """Allow for exceptions to be raised from Judgy during process()."""
        self.raise_error = None
        self._internal_judgy = JudgySync(*processor_args, **processor_kwargs)
        super().__init__(signature=BOTH_SIGNATURE, *processor_args, **processor_kwargs)

    def process(self, **kwargs) -> Result | Reject:
        """Respond dynamically based upon parameters given to the object initially by the test."""
        if isinstance((raise_error := self.raise_error), Exception):
            raise raise_error
        return self._internal_judgy._internal_process(**kwargs)
