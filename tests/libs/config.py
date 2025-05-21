"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

Test configuration file detail specifics surrounding the tests.

Contributing:
    1. User overwrites should be in UserOpts if an environment toggle is to be added
    2. Defaults should set default values if its deemed important enough not to be just in the config file

Exceptional values:
    * log_dir - dynamically re-set with each run treating the value assigned as the root directory
        {{ log_dir }}/<exec date>-<idprefix>/logs/ - is a re-assignment of this value
    * template_dir - where captured, interpreted templates are stored
        {{ log_dir }}/<exec date>-<idprefix>/templates/
    * execution_id = unique to this particular execution of the tests and cannot be overwritten
"""

import configparser
import datetime
import logging
import os
import pathlib
import types
import typing
import uuid

from . import filesystem


LOGGER = logging.getLogger(__name__)
parameters = None


class Defaults:
    """Default configuration."""

    log_dir: pathlib.Path = filesystem.get_working_dir().joinpath("test_logs")
    config_file: pathlib.Path = filesystem.get_working_dir().joinpath("tests/config")


class UserOpts:
    """Overwrite defaults with user options as follows, and also tracks what was overwritten.

    For tracking purposes, do not use the Defaults.attr to the default to os.getenv unless this level of tracking is
    unnecessary.
    """

    log_dir: typing.Optional[str] = os.getenv("TEST_LOGS", None)
    config_file: typing.Optional[str] = os.getenv("TEST_CONFIG", None)


class Parameters(configparser.ConfigParser):
    """ConfigParser that consolidates defaults to the configuration that is loaded to the Environment."""

    # TBD: tracking mechanic for reporting or recording when the user overwrites a value

    def __init__(self, *super_args, **super_opts):
        super().__init__(*super_args, **super_opts)
        self.infra_section = infra = "environment"
        self.overwrites = overwrites = "overwrites"
        self.add_section(infra)
        self.add_section(overwrites)

        # - get and read in our config file location
        if (config_file := UserOpts.config_file) is None:
            config_file = Defaults.config_file
        LOGGER.info(
            str(
                dict(
                    message=f"using config from: {config_file}", config_file=config_file
                )
            )
        )
        self.read(str(config_file))

        # - get our defaults or overwrites assigned
        for attr, value in Defaults.__dict__.items():
            if attr.startswith("_"):
                continue
            self["DEFAULT"][attr] = str(value)
            if overwrite := getattr(UserOpts, attr):
                self[infra][attr] = str(overwrite)
                continue
            if self[infra].get(attr, None):
                self[infra][attr] = str(value)

        # - assign any additional overwrites that might exist that may not have defaults
        for attr, value in UserOpts.__dict__.items():
            if attr.startswith("_"):
                continue
            self[overwrites][attr] = str(value)
            if value and not hasattr(Defaults, attr):
                self["environment"][attr] = str(value)

        # - store our config in a recorded space specific to this execution instance
        self.record_and_store()

    def record_and_store(self):
        """Record under the log_dir for this test instance the config file contents."""
        environment = self.infra_section
        record_dir = pathlib.Path(self[environment]["log_dir"])
        now = datetime.datetime.now(datetime.timezone.utc)
        dir_create_stamp = now.strftime("%y-%m-%d")
        execution_id = str(uuid.uuid4())
        self[environment]["record_dir"] = str(
            (record_dir := record_dir.joinpath(f"{dir_create_stamp}_{execution_id}"))
        )
        record_dir.mkdir(parents=True, exist_ok=True)
        self[environment]["log_dir"] = str((log_dir := record_dir.joinpath("logs")))
        log_dir.mkdir(exist_ok=True)
        self["environment"]["template_dir"] = str(
            (template_dir := record_dir.joinpath("templates"))
        )
        template_dir.mkdir(exist_ok=True)
        with open(record_dir.joinpath("config_used.cfg"), "w") as out:
            self.write(out)


def setup_parameters() -> types.SimpleNamespace:
    """Set up actions to parameters."""
    return types.SimpleNamespace(
        **{key: value for key, value in Parameters()["environment"].items()}
    )


parameters = setup_parameters()
__all__ = [parameters]
