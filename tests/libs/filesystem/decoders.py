"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Simple decoder suite that offers helper methods to quickly decode text to interpreted meaning.
"""

import configparser
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
import pathlib
import json
import typing

import yaml

from .. import exceptions


# - outside interfaces
def decode_file(file_path) -> str:
    """Load the given file and decode if a decoder is available."""
    if not isinstance((given_file := file_path), pathlib.Path):
        given_file = pathlib.Path(given_file)
    elected_decoder = DecoderSuite.by_extension(given_file)
    with open(given_file, "r") as fh:
        return elected_decoder.method(source=fh)


# - can be used from outside, but nested logic
def decode_config(
    text: str = None, source: typing.TextIO = None
) -> configparser.ConfigParser:
    """Decode the given contents (or pointer to) for the given config."""
    check_for_something(text, source)
    cached_input = source
    if text:
        cached_input = StringIO(text)
    parser = configparser.ConfigParser()
    parser.read_file(iter(cached_input))
    return parser


def decode_json(text: str = None, source: typing.TextIO = None) -> typing.Any:
    """Decode the given text or IO stream and decodes the contents."""
    check_for_something(text, source)
    if text:
        return json.loads(text)
    return json.load(source)


def decode_yaml(text: str = None, source: typing.TextIO = None) -> typing.Any:
    """Decode the given text or IO stream and decodes the contents."""
    check_for_something(text, source)
    cached_input = source
    if text:
        cached_input = StringIO(text)
    return yaml.load(cached_input, yaml.Loader)


def straight_text(text: str = None, source: typing.TextIO = None) -> typing.AnyStr:
    """Loads straight text out of what's given running text if given."""
    check_for_something(text, source)
    if text:
        return text
    return source.read()


# - Helper abstractions that make life easier, but fairly security and robust
def check_for_something(
    text: typing.Optional[str], source: typing.Optional[typing.TextIO]
):
    """Check that we were at least given something between text or source."""
    if text is None and source is None:
        raise exceptions.TestTypeError(
            given="NoneType for both text and source",
            expected="one to be populated",
        )


@dataclass
class Decoder:
    """Handle data management of a single caller."""

    method: Callable
    name: str
    extensions: typing.Union[list[str], tuple[list[str]]]


class DecoderSuite:
    """Handle decoder suite extension matching or management."""

    config = Decoder(decode_config, "config", tuple([".config", ".cfg"]))
    json = Decoder(decode_json, "json", tuple([".json"]))
    plain_text = Decoder(
        straight_text, "plaintext", tuple([".txt", "", ".text", ".md", ".html"])
    )
    yaml = Decoder(decode_yaml, "yaml", tuple([".yaml", ".yml"]))

    @classmethod
    def by_extension(cls, filepath: pathlib.Path) -> Decoder:
        """Given the filepath, supply the suggested decoder."""
        extension = filepath.suffix
        if extension == ".j2" and len(filepath.suffixes) > 1:
            extension = tuple(filepath.suffixes[-2:])
        for attr in dir(cls):
            decoder = getattr(cls, attr)
            if not isinstance(decoder, Decoder):
                continue
            if extension in decoder.extensions:
                return decoder
        raise exceptions.TestValueError(
            value=str(filepath),
            message=f"do not know how to decode {extension} type files",
        )
