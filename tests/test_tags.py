"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from f5_ai_gateway_sdk import Tags


import pytest


def test_tags_init():
    """Test that Tags initializes correctly with various valid inputs and raises appropriate errors for invalid inputs."""
    assert isinstance(Tags(), Tags)
    assert isinstance(Tags({}), Tags)
    assert isinstance(Tags({"a": ["b"]}), Tags)
    assert isinstance(Tags({"a": ["b"], "c": ["d", "e"]}), Tags)

    def check_arg_error(arg):
        with pytest.raises((AttributeError, TypeError)):
            Tags(arg)

    check_arg_error([])
    check_arg_error({"a": "b"})
    check_arg_error({"a": []})
    check_arg_error({"a": [True]})
    check_arg_error({"a": [{}]})


def test_tags_modify():
    """Test that Tags can be modified through add_tag, remove_tag, and remove_key operations."""
    tag = Tags({"a": ["b"]})
    tag.add_tag("c", "d", "e")  # First arg is a tag name.

    assert tag.get_tags("a") == ["b"]
    assert tag.get_tags("b") == [], "no such tag"
    assert set(tag.get_tags("c")) == {"d", "e"}
    assert tag.get_all_tags() == {"a": ["b"], "c": ["d", "e"]}

    tag.remove_key("a")
    assert tag.get_tags("a") == []

    tag.remove_key("a")  # Make sure it doesn't trigger any errors.

    tag.add_tag("c", "f")
    assert set(tag.get_tags("c")) == {"d", "f", "e"}

    tag.remove_tag("c", "e")
    assert set(tag.get_tags("c")) == {"d", "f"}

    tag.remove_tag("c", "e")
    assert set(tag.get_tags("c")) == {"d", "f"}, "tag not found to remove"

    with pytest.raises(TypeError):
        tag.add_tag("c", [])
