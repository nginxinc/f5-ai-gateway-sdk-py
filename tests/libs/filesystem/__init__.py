"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Basic hierarchy of libraries for testing involving filesystem objects.
"""

import inspect
import pathlib
import types
import typing

from .. import exceptions
from . import decoders


def data_loader_factory(pytest_request: types.FunctionType):
    """Get a file contents loader as a factory that searches for where the given file exists.

    Gets a factory method that takes a file name and searches for it within 'data' directories found under this
    module's directory or the pytest_request.function (test method being executed)'s directory.  If the file
    cannot be found, then a general 'open' will be issued assuming that the given file name references a path to
    the test data to load.

    Use:
        decoded = data_loader("feature.json")
        print(decoded["field"])

    Expectation:
        "feature.json", or the string passed must match the file stem of a file located at either:
            * ./data/ - of this ``conftest.py``
            * concerning test's parent directory's ./data/
            * (not recommended) is a fully-quantified file location (or relative location) on the filesystem
    """

    if not (code_construct := getattr(pytest_request, "cls")):
        code_construct = (
            pytest_request.function
        )  # cannot be referenced in class-scoped fixtures
    path_candidates = tuple(
        [
            pathlib.Path(__file__).parent.joinpath("data"),
            pathlib.Path(inspect.getfile(code_construct)).parent.joinpath("data"),
            pathlib.Path().absolute().joinpath("data"),
        ]
    )

    def load_file(given_file: pathlib.Path):
        """Load the file and decode its contents by extension."""
        return decoders.decode_file(given_file)

    def loader_factory(file_name: typing.Union[str, pathlib.Path]):
        """Load the given file_name either in this or other data directory file locations."""
        if not isinstance(
            (candidate := file_name), (expected := (str, bytes, pathlib.Path))
        ):
            raise exceptions.TypeError(expected=expected, given=candidate)
        candidate = pathlib.Path(
            candidate
        )  # if it is already a path, it will come back immediately
        if candidate.is_file():
            return load_file(candidate)
        for location in path_candidates:
            if (found := location.joinpath(candidate)).is_file():
                return load_file(found)
        raise exceptions.TestEnvironmentError(
            message=f"{file_name} is not found in any of {path_candidates} locations and is not a file itself",
        )

    return loader_factory


def get_working_dir(as_str: bool = False) -> typing.Union[str, pathlib.Path]:
    """Get the working directory as a pathlib.Path or as str if as_str is True."""
    working = pathlib.Path().absolute()
    if as_str:
        return str(working)
    return working
