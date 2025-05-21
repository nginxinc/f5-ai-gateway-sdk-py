"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import logging
from typing import final, Any
from collections.abc import Mapping, Iterator

from opentelemetry.util.types import AttributeValue
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Parameters(BaseModel):
    """
    Configuration parameters sent to a processor to customize its behavior.
    This class must be subclassed to define custom parameters for a processor.
    This class uses Pydantic for data validation
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Default parameters

    annotate: bool = Field(
        default=True,
        description="Whether the processor can annotate the input with tags.",
    )
    modify: bool = Field(
        default=False,
        description="Whether the processor can modify the input.",
    )
    reject: bool = Field(
        default=False,
        description="Whether the processor can reject requests.",
    )

    @model_validator(mode="after")
    def check_not_reject_and_modify(self):
        if self.reject and self.modify:
            raise ValueError("Modify and Reject modes are mutually exclusive")
        return self

    def otel_attributes(
        self, key_prefix: str = "parameters."
    ) -> Iterator[tuple[str, AttributeValue]]:
        """Return OpenTelemetry attributes to be sent with the processor span."""

        def sequence_attributes(element: Any) -> Any:
            if isinstance(element, (str, int, float, bool)):
                return element
            else:
                return str(object=element)

        def dict_attributes(
            _value: Mapping[str, Any], prefix: str
        ) -> Iterator[tuple[str, AttributeValue]]:
            for _k, _v in _value.items():
                if isinstance(_v, (str, int, float, bool)):
                    yield f"{prefix}{_k}", _v
                    continue
                if isinstance(_v, (list, tuple, set, frozenset)):
                    yield f"{prefix}{_k}", list(map(sequence_attributes, _v))
                    continue
                elif isinstance(_v, dict):
                    yield from dict_attributes(_v, f"{prefix}{_k}.")
                    continue
                else:
                    yield key, str(object=_value)

        for field_name, field_value in self.model_dump().items():
            key = f"{key_prefix}{field_name}"

            try:
                if isinstance(field_value, (str, int, float, bool)):
                    yield key, field_value
                    continue
                if isinstance(field_value, (list, tuple, set, frozenset)):
                    yield key, list(map(sequence_attributes, field_value))
                    continue
                elif isinstance(field_value, dict):
                    yield from dict_attributes(field_value, key + ".")
                    continue
                else:
                    yield key, str(object=field_value)
            except Exception as e:
                logging.warning(
                    f"Unsupported type for attribute [{key}: {type(field_value)}]: {e}"
                )


@final
class DefaultParameters(Parameters):
    """
    Default empty parameters class for processors that do not require parameters.
    This class should not be inherited from.
    """

    model_config = ConfigDict(title="Default Parameters", frozen=True)


# EmptyParameters has been deprecated. DefaultParameters should be used instead.
EmptyParameters = DefaultParameters


__all__ = ["Parameters", "DefaultParameters", "EmptyParameters"]
