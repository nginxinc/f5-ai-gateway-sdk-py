.PHONY: build clean fmt lint lint.fix help test

.DEFAULT_GOAL := help

ROOTDIR           ?= $(shell bash -c "git rev-parse --show-toplevel")
SED               ?= $(shell which gsed 2> /dev/null || which sed 2> /dev/null)
GREP              ?= $(shell which ggrep 2> /dev/null || which grep 2> /dev/null)
ifdef ($(findstring ggrep,$(GREP)))
	VERSION   ?= $(shell bash -c "$(GREP) -Po '^version\s+=\s+\"\K.*?(?=\")' pyproject.toml")
else
	VERSION   ?= $(shell bash -c "grep -e '^version' pyproject.toml | sed 's/.*= //'")
endif

build: # Build the SDK into source distributions and wheel
	uv build

clean:  # Removes local .venv directories and cleans up Docker containers and images associated with this project.
	rm -rf $(ROOTDIR)/.venv

deps: # Installs all dependencies using uv without updating uv.lock.
	uv sync --frozen

fmt: # Runs formatting checks on the project's codebase using ruff format
	uv run ruff format

help: # Show help for each of the Makefile recipes.
	@printf "Make commands for f5-ai-gateway-sdk\nUsage:\n\n"
	@grep -E '^[a-zA-Z0-9 -\.]+:.*#'  Makefile | sort | while read -r l; do printf "\033[1;32m$$(echo $$l | cut -f 1 -d':')\033[00m:$$(echo $$l | cut -f 2- -d'#')\n"; done
	
lint: # Runs code linting checks using ruff check and pyright
	uv run ruff check --preview
	uv run pyright ./src

lint.fix: # Automatically fixes linting issues, attempting to correct them without manual intervention.
	uv run ruff check --fix --preview

test: # Runs test suites in /tests.
	@rm -rf test_logs/
	uv run pytest -svvra -W error::UserWarning --doctest-modules --junitxml=test_logs/results.xml --cov=src --cov-report=xml --cov-report=term  $(ROOTDIR)/tests 

scan: # Scans dependencies for vulnerabilities
	uv run bandit -r src/ --exclude .venv/,tests/
