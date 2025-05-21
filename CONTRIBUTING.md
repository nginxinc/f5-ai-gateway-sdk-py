# Contributing to F5 AI Gateway Processor SDK

We want to make contributing to this project as easy and transparent as
possible.

## Code of Conduct

F5 has adopted a Code of Conduct that we expect project participants to adhere
to. Please read [the full text](CODE_OF_CONDUCT.md) so that you can understand
what actions will and will not be tolerated.

## Our development process

### General philosophies

- The project uses python3.11 or higher and [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Python code should conform to the
  [PEP-8 style guidelines](https://www.python.org/dev/peps/pep-0008/)
  whenever possible.
- Where feasible, include unit tests.
- Tests should make use of the testing fixtures and tools on offer
- Code should pass `make lint` with no warnings.

### Getting started

> **Note**
>
> For easier dependency management, [mise](https://mise.jdx.dev/) or [asdf](https://asdf-vm.com/) will use [.tool-versions](./.tool-versions) to automatically ensure you have the correct versions of python and uv

### Install Python dependencies

```bash
make deps
```

### Linting code

```bash
make lint
```

### Executing tests

```bash
make test
```

## Report a bug

To report a bug, open an issue on GitHub and choose the type 'Bug report'. Please ensure the issue has not already been reported, and that you fill in the template as provided, as this can reduce turnaround time.

## Suggest a new feature or other improvement

To suggest an new feature or other improvement, create an issue on Github and choose the type 'Feature request'. Please fill in the template as provided.

## Pull requests

We actively welcome your pull requests.

Before working on a pull request which makes significant change, consider opening an associated issue describing the proposed change. This allows the core development team to discuss the potential pull request with you before you do the work.

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
   - This can be done with `make test`
5. Make sure your code lints.
   - This can be done with `make lint`
6. If you haven't already, complete the Contributor License Agreement ("CLA").

## Contributor License Agreement ("CLA")

F5 requires all external contributors to agree to the terms of the F5 CLA (available [here](https://github.com/f5/.github/blob/main/CLA/cla-markdown.md))
before any of their changes can be incorporated into an F5 Open Source repository.

If you have not yet agreed to the F5 CLA terms and submit a PR to this repository, a bot will prompt you to view and
agree to the F5 CLA. You will have to agree to the F5 CLA terms through a comment in the PR before any of your changes
can be merged. Your agreement signature will be safely stored by F5 and no longer be required in future PRs.

## License

By contributing to F5 AI Gateway Processor SDK, you agree that your contributions will be licensed
its Apache Version 2.0 license. Copy and paste this to the top of your new file(s):

```python
"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""
```
