"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import json

import pytest


@pytest.mark.test_of_tests
def test_of_tests(request, data_loader, test_logger):
    expected = "hello world!\n"
    test_logger.debug("Given: the standard data_loader fixtures")
    test_logger.debug("When: the data_loader is given a text file")
    result = data_loader("hello_world.txt")
    test_logger.debug("Then: the text file should be read as-is")
    assert expected == result, f"'{expected}' does not match '{result}'"


@pytest.mark.test_of_tests
def test_json_extraction(data_loader, test_logger):
    test_logger.debug("Given: the standard data_loader fixtures")
    expected = dict(hello="world")
    test_logger.debug("When: the data_loader is given a json file")
    result = data_loader("hello_world.json")
    test_logger.debug("Then: the contents of the file should be interpretted")
    assert expected == result, f"'{expected}' does not match '{result}'"


@pytest.mark.test_of_tests
def test_yaml_extraction(data_loader):
    expected = dict(hello="world")
    result = data_loader("hello_world.yaml")
    assert expected == result, f"'{expected}' does not match '{result}'"


@pytest.mark.test_of_tests
def test_config_extraction(data_loader):
    result = data_loader("hello_world.cfg")
    assert (assertion := result["hello"]["world"]) == (expected := "ellipsoid"), (
        f"{assertion} != {expected}"
    )
    assert (assertion := json.loads(result["solar system"]["planets"])) == (
        expected := [
            "mercury",
            "venus",
            "earth",
            "mars",
            "jupiter",
            "saturn",
            "uranus",
            "neptune",
        ]
    ), f"{assertion} != {expected}"
    print(result)


@pytest.mark.test_of_tests
def test_simple_load(data_loader):
    """Assure that we can load the text file similar to test_of_tests above."""
    to_load = "hello_world.txt"
    assert (result := data_loader(to_load)) == (expected := "hello world!\n"), (
        f"{to_load} was not loaded properly {result} != {expected}"
    )
