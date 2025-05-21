# Contributing to F5 AI Gateway Processor SDK
We want to make contributing to this project as easy and transparent as
possible.

## [Code of Conduct]

F5 has adopted a Code of Conduct that we expect project participants to adhere
to. Please read [the full text](CODE_OF_CONDUCT.md) so that you can understand
what actions will and will not be tolerated.

## Our Development Process

[OUTLINE OF DEVELOPMENT PROCESS]

## Pull Requests
We actively welcome your pull requests.

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
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

<<<<<<< HEAD
```js
/**
 * Copyright (c) F5, Inc.
 *
 * This source code is licensed under the Apache License Version 2.0 found in the
 * LICENSE file in the root directory of this source tree.
 */
=======
### Report a Bug

To report a bug, open an issue on GitHub with the label `bug` using the
available bug report issue template. Please ensure the issue has not already
been reported.

### Suggest an Enhancement

To suggest an enhancement, please create an issue on GitHub with the label
`enhancement` using the available feature issue template.

### Open a Pull Request

* Fork the repo, create a branch, submit a PR when your changes are tested and
  ready for review.
* Fill in [our pull request template](/.github/PULL_REQUEST_TEMPLATE.md)

Note: if you’d like to implement a new feature, please consider creating a
feature request issue first to start a discussion about the feature.

## Style Guides

### Git Style Guide

* Keep a clean, concise and meaningful git commit history on your branch,
  rebasing locally and squashing before submitting a PR
* Use the
  [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) format
  when writing a commit message, so that changelogs can be automatically
  generated
* Follow the guidelines of writing a good commit message as described
  [here](https://chris.beams.io/posts/git-commit/) and summarised in the next
  few points
  * In the subject line, use the present tense
    ("Add feature" not "Added feature")
  * In the subject line, use the imperative mood ("Move cursor to..." not
    "Moves cursor to...")
  * Limit the subject line to 72 characters or fewer
  * Reference issues and pull requests liberally after the subject line
  * Add more detailed description in the body of the git message (
    `git commit -a` to give you more space and time in your text editor to
    write a good message instead of `git commit -am`)

### Code Style Guide

* Python code should conform to the
  [PEP-8 style guidelines](https://www.python.org/dev/peps/pep-0008/)
  whenever possible.
* Where feasible, include unit tests.
* Code should pass `ruff check` with no warnings.

## Development Workflow

*General philosophies:*

* Recommended [to use uv](https://docs.astral.sh/uv/getting-started/installation/)
* Requires python3.11 or higher
* Tests should make use of the testing fixtures and tools on offer

### Getting Started

[mise](https://mise.jdx.dev/) or [asdf](https://asdf-vm.com/) which will use [.tool-versions](./.tool-versions) to automatically ensure you have the correct versions

*For macOS:*
```bash
make deps
```

### Lint Checks

[Depend upon `ruff`](https://github.com/astral-sh/ruff), and can be executed with the following command:
```bash
make lint
```

This fast, lightweight tool handles the linting operations very quickly and efficiently and is performed within the pipeline.

### Executing Tests

```bash
make test
```

*Troubleshooting:*
When discovering the following error:
```
____________________________________________________________________________________________________ ERROR collecting tests/test_processor.py _____________________________________________________________________________________________________
tests/test_processor.py:16: in <module>
    from f5_ai_gateway_sdk.processor import Result, Processor, SYSTEM_INFO
src/f5_ai_gateway_sdk/processor.py:23: in <module>
    SYSTEM_INFO = system_info()
src/f5_ai_gateway_sdk/sysinfo.py:50: in system_info
    "host": host_info(),
src/f5_ai_gateway_sdk/sysinfo.py:18: in host_info
    "ip": socket.gethostbyname(socket.gethostname()),
E   socket.gaierror: [Errno 8] nodename nor servname provided, or not known
_________________________________________________________________________________________________ ERROR collecting tests/test_processor_routes.py _________________________________________________________________________________________________
tests/test_processor_routes.py:4: in <module>
    from f5_ai_gateway_sdk.processor import Processor
src/f5_ai_gateway_sdk/processor.py:23: in <module>
    SYSTEM_INFO = system_info()
src/f5_ai_gateway_sdk/sysinfo.py:50: in system_info
    "host": host_info(),
src/f5_ai_gateway_sdk/sysinfo.py:18: in host_info
    "ip": socket.gethostbyname(socket.gethostname()),
E   socket.gaierror: [Errno 8] nodename nor servname provided, or not known
```
Or similar, please copy the contents of your `hostname`, on the macOS, that's:
```bash
hostname | pdcopy
```
And add it to your `/etc/hosts` file with `127.0.0.1` as `localhost` to reflect something similar to:
```
127.0.0.1   $(hostname)
```
[For more on why this is necessary](https://stackoverflow.com/questions/39970606/gaierror-errno-8-nodename-nor-servname-provided-or-not-known-with-macos-sie) for `starlette`.
>>>>>>> main
