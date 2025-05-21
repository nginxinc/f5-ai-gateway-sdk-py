"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Logging infrastructure for fixtures and tests.
"""

from collections import namedtuple
import datetime
from dataclasses import dataclass
import json
import logging
import sys
import traceback
import typing

import os
import pytest

from .filesystem import locations


DEFAULT_TERMINAL_LOGGING_LEVEL = logging.getLevelName(logging.INFO)


@dataclass
class LogLocation:
    """Hold details of where a log took place in code."""

    file: str
    function: str
    line: typing.Union[str, int]

    def as_dict(self):
        """Get the dict form of the object."""
        return {attr: getattr(self, attr) for attr in self.__match_args__}


@dataclass
class LogMetadata:
    """Hold details of when and where the log took place."""

    # time: typing.Union[str, datetime.datetime]
    log_level: str
    location: typing.Union[LogLocation, dict[str, typing.Union[str, int]]]

    def __init__(self, *as_args, **as_kwargs):
        self._time = None
        if not as_args and not as_kwargs:
            return
        if as_args:
            for count, attr in enumerate(self.__match_args__):
                try:
                    setattr(self, attr, as_args[count])
                except IndexError:
                    raise NameError(
                        f"failed due to absent values for: {self.__match_args__[count:]}"
                    )
            return
        expected = set(self.__match_args__)
        if (intersection := expected.intersection(as_kwargs.keys())) != expected:
            raise NameError(f"missing {expected - intersection} fields in given")
        for attr in self.__match_args__:
            setattr(self, attr, as_kwargs[attr])

    def as_dict(self):
        """Get the dict form of the object."""
        return {attr: getattr(self, attr) for attr in self.__match_args__}

    @property
    def time(self):
        """Get the time value as a string in iso format."""
        if isinstance((my_time := self._time), str):
            return my_time
        if isinstance(my_time, datetime.datetime):
            return my_time.isoformat()
        if isinstance(my_time, (float, int)):
            return datetime.fromtimestamp(my_time, datetime.timezone.utc).isoformat()
        raise TypeError(f"unknown type assigned to {self}.time")

    @time.setter
    def time(self, given):
        """Set the value of time."""
        if not isinstance(given, (expected := (str, float, int, datetime.datetime))):
            raise TypeError(
                f"time given is not {expected}, but instead a {type(given)}"
            )
        self._time = given


@dataclass
class Log:
    """Hold the definition of a single log entry."""

    metadata: typing.Union[LogMetadata, dict[str, typing.Union[str, typing.Any]]]
    log: str

    def as_dict(self):
        """Get the dict form of the object."""
        return {attr: getattr(self, attr) for attr in self.__match_args__}


@pytest.fixture
def logging_fx(request: pytest.FixtureRequest):
    """Communicate and handle testing logging."""
    debug = os.environ.get("DEBUG", "false") == "true"
    term_level = os.environ.get(
        "log_level",
        os.environ.get("LOG_LEVEL", DEFAULT_TERMINAL_LOGGING_LEVEL),
    )
    term_level = getattr(logging, term_level.upper(), DEFAULT_TERMINAL_LOGGING_LEVEL)
    logger = logging.getLogger()
    set_other_handlers(logger, term_level, debug)
    encoded_format = Log(
        metadata=LogMetadata(
            time="%(asctime)s",
            log_level="%(levelname)s",
            location=LogLocation(
                file="%(filename)s",
                function="%(funcName)s",
                line="%(lineno)d",
            ).as_dict(),
        ).as_dict(),
        log="%(message)s",
    ).as_dict()
    log_format = logging.Formatter(json.dumps(encoded_format))
    test_location = locations.CurrentTest(request=request, logdir_child="logs")
    file_handler = set_file_handler(logger, request, log_format, test_location)
    start = datetime.datetime.now(datetime.timezone.utc)
    try:
        yield logger
    finally:
        logger.info(
            f"test duration: {datetime.datetime.now(datetime.timezone.utc) - start}"
        )
        if (exc := get_last_exception()) is not None:
            logger.error("".join(traceback.format_exception(*exc)))
        file_handler.flush()
        file_handler.close()
        logger.removeHandler(file_handler)


def get_last_exception():
    """Return (type, value, traceback) tuple for last exception."""
    # - we have to go through these getattr gyrations to keep pylint quiet
    #   (otherwise it complains because the sys.last_* properties are not
    #   available at lint time)
    if hasattr(sys, "last_type") and getattr(sys, "last_type"):
        return namedtuple("Exception", "type, value, trace")(
            getattr(sys, "last_type"),
            getattr(sys, "last_value"),
            getattr(sys, "last_traceback"),
        )
    return None


def set_file_handler(
    logger: logging.Logger,
    request: pytest.FixtureRequest,
    log_format: logging.Formatter,
    test_location: locations.CurrentTest,
):
    """Set the default file handler for each test."""
    log_file = test_location.add_parent(make_parent=True, multi_processed=False)
    handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(log_format)
    logger.addHandler(handler)
    return handler


def set_other_handlers(root: logging.Logger, term_level: int, debug: bool):
    """Configure the root logger.

    Configures the root logger for all expressed logging.
    """
    log = root.info
    msg = f"set root logger handlers to {logging.getLevelName(term_level)}"
    if debug:
        term_level = logging.DEBUG
        log = root.warning
        msg = "set root logger handlers to DEBUG"
    # capture log level for everyone
    root.setLevel(logging.DEBUG)
    # filter what is seen everywhere
    for handler in root.handlers:
        handler.setLevel(term_level)
    log(msg)
