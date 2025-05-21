"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

House helpers for formatting filenames out of the current test location & naming.
"""

import contextlib
import inspect
import logging
import pathlib
import subprocess
import typing

from .. import exceptions
from ..protocols import url as url_utils
from .. import config


NON_WINDOWS_FRIENDLY = ["#", "<", ">", "%", ":", "/", "\\", '"', "|", "?", "*"]
LOGGER = logging.getLogger(__name__)


class CurrentTest:
    """Helper to assist in getting key information surrounding the test.

    Helps in generating a name suitable to identify which test is being executed at the
    moment by either the pytest-fixture request or the stack leading back to the test
    that was called by pytest.

    Suggested Use:
        log_location = str(pathlib.Path(session.Paramters.logfile).join_path(
            CurrentTest()().file_name_format(suffix=".log")
        ))
        # -- or --
        log_location = CurrentTest()().add_parent(suffix=".log")
    """

    default_separator = "-"
    default_test_separator = "--"
    xray_sep = "."
    xray_test_sep = "."
    default_logdir_child = "configs"

    @classmethod
    def user_test_logs(cls, request=None):
        """Get the user test logs location."""
        test_location = cls(request=request, logdir_child="logs")
        if request is None:
            test_location()
        log_file = test_location.add_parent(make_parent=True, multi_processed=False)
        if (job_url := config.parameters.job_url) != "Local Execution":
            local_path = pathlib.Path(config.parameters.log_dir)
            if ".systest" in str(local_path):
                local_path = local_path.parent
            browse_path = str(log_file).replace(str(local_path), "")
            return url_utils.join_url(
                job_url,
                "artifacts",
                "browse",
                "results",
                *browse_path.split("/"),
            )
        return log_file

    def __init__(self, request=None, logdir_child=None):
        self.logger = logging.getLogger(__name__)
        self._repo_root = None
        self.test_name = None
        self.test_file = None
        logdir_child = str(
            logdir_child if logdir_child is not None else self.default_logdir_child
        )
        self.file_segment_separator = self.default_separator
        self.test_separator = self.default_test_separator
        self.from_request(request)
        self.logdir = pathlib.Path(config.parameters.log_dir).joinpath(logdir_child)
        self.logdir.mkdir(parents=True, exist_ok=True)

    def __call__(self, request=None):
        """Assign test attributes from an optional request pytest fixture, or stack."""
        self.from_request(request)
        if request is None:
            self.from_stack()
        return self

    def __str__(self):
        return f"{self.test_file}::{self.test_name}"

    @property
    def repo_root(self):
        """Get the repo root that should only come from git."""
        if not (root_location := self._repo_root):
            test_dir = str(pathlib.Path(self.test_file).parent)
            root_location = get_root_dir(source=test_dir)
            self._repo_root = root_location
        return root_location

    @repo_root.setter
    def repo_root(self, *_, **__):
        """Raise an error stating that git should only be the source of truth here."""
        raise exceptions.RestrictedOperationError(
            reason="source for repo's root directory should remain git for stability",
            suggested_next_steps="""root dir is only used in deriving a file name

If a test author would like to customize their filenames further, but would like to have
the test name and test file source incorporated, then please consider using 'test_name'
and 'test_file' attributes in a custom name""",
            additional_info="path used tor repo is test_file's parent, and not working",
        )

    @staticmethod
    def iter_segments(path, up_to="", include_extension=False):
        """Iterate through the path starting at the name through parents."""
        name = path.stem
        for remaining in path.suffixes[:-1]:
            # removes all remaining extensions
            name = name.replace(remaining, "")
        if include_extension:
            name = path.name
        parent = path.parent
        yield name
        while parent.name != up_to and parent.name != "":
            yield parent.name
            parent = parent.parent

    def add_parent(
        self,
        parent=None,
        make_parent=False,
        intermediate=None,
        multi_processed=None,
        **file_name_format_opts,
    ) -> pathlib.Path:
        """Add the given parent directory, or default logdir parent.

        Adds a parent directory that can be constructed for the caller if ``make_parent`` is
        True, and adds intermediate directories beneath it as necessary.

        If no parent is specified, then the default ``tests.libs.config.parameters.log-dir`` is
        used, and there are no intermediate directories.

        Lastly, ``file_name_format_opts`` are passed directly to ``file_name_format()`` call to
        determine file name.
        """
        intermediate = intermediate or []
        intermediate = [intermediate] if isinstance(intermediate, str) else intermediate
        parent = parent if parent is not None else self.logdir
        parent = pathlib.Path(parent).joinpath(*intermediate)
        if make_parent:
            parent.mkdir(parents=True, exist_ok=True)
        if not parent.is_dir():
            raise exceptions.TestEnvironmentError(
                message=f"parent directory {parent} does not exist",
                sns=str(
                    "assure that parent directory to file given exists, or use "
                    "make_parent=True as a call option"
                ),
            )
        return parent.joinpath(self.file_name_format(**file_name_format_opts))

    def until_root_intersect(self, file_path):
        """Return path1's lowest tree branches until path2 intersection as a list.

        Determines root directory using git, and then returns, as a list, each segments
        leading up to the root directory name in the path given starting from the base
        name to parent, to parent's parent, etc.

        Example:
            root is root dir's name:
                ./root/path/to/file.out
                returns:
                    ["path", "to", "file.out"]
        """
        repo_root = pathlib.Path(self.repo_root)
        root_dirname = repo_root.name
        segments = list(self.iter_segments(file_path, up_to=root_dirname))
        segments.reverse()
        return self.file_segment_separator.join(
            (path_segment for path_segment in segments)
        )

    def file_name_format(self, suffix=None, prefix=None):
        """Get the file format of the test's file and name."""
        suffix = suffix or ""
        prefix = prefix or ""
        name = self.test_name
        if name is None or self.test_file is None:
            self.from_stack()
            name = self.test_name
        file_path = pathlib.Path(self.test_file)
        path_str = self.until_root_intersect(file_path)
        formatted = f"{path_str}{self.test_separator}{name}"
        if isinstance(prefix, str) and isinstance(suffix, str):
            formatted = prefix + formatted + suffix
        for char in NON_WINDOWS_FRIENDLY:
            formatted = formatted.replace(char, "_")
        return formatted

    def from_request(self, request):
        """Assign values from the given pytest.fixture request."""
        if request is None:
            return
        self.test_name = request.node.name
        test_file = inspect.getfile(request.function)
        test_file = getattr(request.node, "path", test_file)
        self.test_file = test_file

    def from_stack(self):
        """Assign values from the current frame's stack.

        Assigns values from the current frame's stack for either the test that is known
        or the ``pytest.fixture`` that called it.  In this way, it is still a test structure
        that is noted as the value used.
        """
        previous_frame = None
        outer_frames = inspect.getouterframes(inspect.currentframe())
        for cnt, frame in enumerate(outer_frames):
            if "main" in frame.function:
                self.test_name = frame.function
                self.test_file = frame.filename
                break
            if frame.function == "pytest_pyfunc_call":
                self.test_name = outer_frames[cnt - 1].function
                self.test_file = outer_frames[cnt - 1].filename
                break
            if frame.function.startswith("test_") and "test_" in frame.filename:
                self.test_name = frame.function
                self.test_file = frame.filename
                break
            if frame.function.startswith("call_fixture") or frame.function.endswith(
                "_fixture"
            ):
                self.test_name = previous_frame.function
                self.test_file = previous_frame.filename
                break
            previous_frame = frame
        else:
            self.test_name = outer_frames[-1].function
            self.test_file = outer_frames[-1].filename

    def get_xray_format(self):
        """Get Jira XRAY format of the test location."""
        with self._xray_format():
            return self.file_name_format()

    @contextlib.contextmanager
    def _xray_format(self):
        """Transform the delimiters to ones recognized by Jira XRAY."""
        sep_hold = self.file_segment_separator
        test_sep_hold = self.test_separator
        self.file_segment_separator = self.xray_sep
        self.test_separator = self.xray_test_sep
        try:
            yield
        finally:
            self.file_segment_separator = sep_hold
            self.test_separator = test_sep_hold


def get_root_dir(
    source: typing.Optional[typing.Union[str, pathlib.Path]] = None,
) -> pathlib.Path:
    """Get the root directory of the repository from the source or '.'."""
    if (used_source := source) is not None:
        used_source = pathlib.Path()
    else:
        used_source = "."
    used_source = pathlib.Path(used_source)
    root_path = subprocess.check_output(
        f"cd {used_source}; git rev-parse --show-toplevel", shell=True
    )
    return pathlib.Path(root_path.strip().decode())
