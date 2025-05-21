"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Starting basis for a centralized pattern for AI GW testing.
"""

import pathlib
import sys
import unittest

# - python pathing magic to add the test suite to path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest

# F401 deals with restricting imports on what is not used, and that breaks importing fixtures pattern
# F811 deals with not redefining a global scope variable, which also breaks fixtures
from .libs.testing_clients.fixtures import processor_client_loader  # noqa: F401
from .libs.testing_clients.fixtures import processor_routes_client_loader  # noqa: F401
from .libs.filesystem import data_loader_factory
from .libs.logs import logging_fx as test_logger  # noqa: F401
from .libs.protocols import url as url_manipulations


# - fixtures
@pytest.fixture(scope="class")
def class_data_loader(request):
    """Add to the class a static method to load any test data file.

    Adds the data_loader fixture functionality to a unittest.TestCase class.

    Use:
        @pytest.mark.usefixture("class_data_loader")
        class TestFeature(unittest.TestCase):
            ...
            self.data_loader("file_reference.txt")
    Example:
        @pytest.mark.usefixture("class_data_loader")
        class TestFeature(unittest.TestCase):
            ...
            def test_feature_aspect_a(self, ...):
                template = self.data_loader("template.json")
                assert (
                    result := some_aspect(template["foo"])
                ) == expected, f"data in {template['foo']} resulted in {result} not {expected}"
        Here, we have `template` housing the decoded contents of `template.json` as part of our test.
    """
    data_loader = data_loader_factory(request)

    def staticmethod_data_loader(_: unittest.TestCase, file_name: str):
        """Dereference the 'self' pass in the "method" call for the overwrite making it a staticmethod."""
        return data_loader(file_name)

    # - "bolt on" the fixture as a static method of sorts
    request.cls.data_loader = staticmethod_data_loader


@pytest.fixture
def data_loader(request):
    """Load, as a file content factory, the filesystem's file location contents.

    Loads the contents of the file given under either this conftest file's directory's data/ path or the test module's
    directory's data/ path.

    Use:
        def test_foo(data_loader):
            test_data = data_loader("feature_file.json")

        Will load the file under:
        ./conftest.py
        ./data/feature_file.json
        and decode the contents to return to test_data by extension.

        def test_featureB(data_loader):
            test_data = data_loader("featureB.json")

        Will load the file under:
        ./path/to/tests/test_featureB.py
        ./path/to/tests/data/featureB.yaml
        and decode the contents to return to test-data by extension.
    """
    return data_loader_factory(request)


@pytest.fixture
def url_fx():
    """Get the url_manipulations library as a direct fixture.

    Gets the functionality stored within the libs.protocols.url under tests such that all methods found within can
    then be referenced from within tests easily.

    Use:
        def test_feature_abc(url_fx):
            local_1234 = url_fx.add_to_url("", host="localhost", port="1234", scheme="https")
            assert str(local_1234) == "https://localhost:1234"
    """
    return url_manipulations
