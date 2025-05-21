[![ci](https://github.com/nginxinc/f5-ai-gateway-sdk-py/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nginxinc/f5-ai-gateway-sdk-py/actions/workflows/ci.yml)
[![FOSSA Status](https://app.fossa.com/api/projects/custom%2B5618%2Ff5-ai-gateway-sdk-py.svg?type=shield&issueType=license)](https://app.fossa.com/projects/custom%2B5618%2Ff5-ai-gateway-sdk-py?ref=badge_shield&issueType=license)
[![FOSSA Status](https://app.fossa.com/api/projects/custom%2B5618%2Ff5-ai-gateway-sdk-py.svg?type=shield&issueType=security)](https://app.fossa.com/projects/custom%2B5618%2Ff5-ai-gateway-sdk-py?ref=badge_shield&issueType=security)

# F5 AI Gateway Processor SDK

This project is a Python SDK for the F5 AI Gateway Processors specification. 
It is designed to be used as a base for building a [Starlette](https://www.starlette.io/) application that
implements Python based Processors for the AI Gateway.

## Creating a processor

[Processor development quickstart tutorial](https://aigateway.clouddocs.f5.com/sdk/python/tutorial.html)

## Testing

[Instructions for running the tests](./tests/README.md#executing-tests).

## Formatting and ilnting

This project uses [Ruff](https://docs.astral.sh/ruff/) for formatting and linting.

## Make targets

Run `make help` to see available make targets, such as `fmt`, `lint`, `test`.
