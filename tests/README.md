# Testing

Follows the `pytest` format with the flexibility of adopting `unittest.TestCase` as deemed needed for the flexibility of moving forward quickly.

## Executing Tests

## Prerequisites

```bash
make deps
```

## Run tests

```bash
make test
```

## Clear virtual env

```bash
make clean
```

### `data_loader`s `unittest.TestCase` Support

Comes with the simple addition of the `class` decorator of:

```python
import unittest

import pytest


@pytest.mark.usefixtures("class_data_loader")
class TestFoo(unittest.TestCase):
    def test_foo(self, ...):
        test_data = self.data_loader(...)
```

These are static files that are decoded from either `yaml`, `json`, or plain text based upon extensions, and loaded into the return value.
