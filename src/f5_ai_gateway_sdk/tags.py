"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import copy
from typing import cast

from pydantic import BaseModel, JsonValue


class Tags(BaseModel):
    """
    Dictionary of keys with a list of tags associated with a prompt response for annotating a transaction with notable properties.
    All keys and values are stored in lowercase.
    """

    _tags: dict[str, list[str]] = {}

    def __init__(self, initial_tags: dict[str, list[str]] | None = None):
        """Initialize the Tags object with an optional initial dictionary.

        Example::

            tags = Tags({"topics_detected": ["security", "ai"]})


        :param initial_tags: An optional dictionary of key-value pairs with list of strings.
        """

        super().__init__()

        if initial_tags is not None:
            for key, value in initial_tags.items():
                self._validate_tag(key, value)

            # lowercase all keys and values
            self._tags = {
                key.lower(): [value.lower() for value in values]
                for key, values in initial_tags.items()
            }

    def _validate_key(self, key: str) -> None:
        """Validate key string of the tag.

        :param key: The key to validate.
        """

        if not key or not isinstance(key, str):
            raise TypeError(f"Invalid key '{key}': All keys must be non-empty strings")

    def _validate_value(self, value: list) -> None:
        """Validate value list of strings of the tag.

        :param value: The list of tags to validate.
        """

        if not isinstance(value, list) or len(value) < 1:
            raise TypeError(
                f"Invalid list '{value}': Must be an list with at least one element"
            )

        for el in value:
            self._validate_value_element(el)

    def _validate_value_element(self, element: str) -> None:
        """Validate tags list element of the tag.

        :param element: Tags list element to validate.
        """

        if not element or not isinstance(element, str):
            raise TypeError(
                f"Invalid list element '{element}': All values in list must be non-empty strings"
            )

    def _validate_tag(self, key: str, value: list[str]) -> None:
        """Validate key-value pair of the tag.

        :param key: The key to validate.
        :param value: The list of tags to validate.
        """

        self._validate_key(key)
        self._validate_value(value)

    def add_tag(self, key: str, *values: str) -> None:
        """Add a tag to the given key.

        :param key: The key to which the tag will be added.
        :param values: The values of the tags to be added.
        """
        tags = list(values)
        self._validate_tag(key, tags)
        key = key.lower()
        tags = [tag.lower() for tag in tags]

        if key not in self._tags:
            self._tags[key] = tags

        else:
            self._tags[key].extend(tags)

            # remove duplicates
            self._tags[key] = list(set(self._tags[key]))

    def remove_tag(self, key: str, value: str) -> None:
        """Remove a tag from the given key.

        :param key: The key from which the tag will be removed.
        :param value: The value of the tag that will be removed.
        """

        self._validate_key(key)
        self._validate_value_element(value)

        key = key.lower()
        value = value.lower()

        if key in self._tags and value in self._tags[key]:
            self._tags[key].remove(value)
            if not self._tags[key]:
                del self._tags[key]

    def get_tags(self, key: str) -> list[str]:
        """Get all tags associated with the given key.

        :param key: The key to retrieve tags for.
        :return: A set of all tags associated with the given key. If no tags are found, an empty list is returned.
        """

        self._validate_key(key)
        return self._tags.get(key.lower(), []).copy()

    def get_all_tags(self) -> JsonValue:
        """Get the entire tags dictionary."""
        return cast(JsonValue, copy.deepcopy(self._tags))

    def remove_key(self, key: str) -> None:
        """Remove a key from the tags object.

        :param key: The key to be removed.
        """

        self._validate_key(key)
        key = key.lower()

        if key in self._tags:
            del self._tags[key]

    def to_response(self) -> JsonValue:
        """
        Convert Tags with are string dict with sets to dicts with lists for JSON serialization
        :return: A dictionary where each key has a list of strings as its value.
        """
        return self.get_all_tags()

    def __str__(self):
        """Return a user-friendly string representation of the Tags object."""
        return ", ".join(
            f"{key}: [{', '.join(values)}]" for key, values in self._tags.items()
        )

    def __bool__(self):
        return len(self) > 0

    def __len__(self):
        return len(self._tags.keys())
