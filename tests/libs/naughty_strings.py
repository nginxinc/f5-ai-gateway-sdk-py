"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

import base64
import os.path
from collections.abc import Iterable


class NaughtStringParseException(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class NaughtyStrings(Iterable[str]):
    default_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "blns.base64.txt"
    )

    def __init__(self, path: str | None = None):
        if path is None:
            self.path = NaughtyStrings.default_path

    def __iter__(self):
        # The first comment line in a section of comments describes the category of strings. We use this flag
        # to identify if we are on the first comment line.
        top_comment_line = True
        line_no = 0

        with open(self.path) as f:
            for line in f:
                line_no += 1

                if line.startswith("#"):
                    if top_comment_line:
                        self.section = line[1:].strip()
                        top_comment_line = False
                else:
                    top_comment_line = True
                    try:
                        b64decoded = base64.b64decode(line)
                    except Exception as e:
                        msg = f"Error mime64 decoding line {line_no} in section {self.section}: {line}"
                        raise NaughtStringParseException(msg) from e
                    try:
                        decoded = b64decoded.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        msg = f"Error charset decoding line {line_no} in section {self.section}: {b64decoded}"
                        raise NaughtStringParseException(msg) from e

                    yield decoded
