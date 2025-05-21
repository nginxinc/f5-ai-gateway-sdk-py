"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.
"""

from f5_ai_gateway_sdk.sysinfo import SysInfo

import pytest


def test_init():
    sys_info = SysInfo(service_name="service_name", service_version="1.0.0")
    assert isinstance(sys_info, SysInfo)
    assert "service.name" in sys_info
    assert sys_info["service.name"] == "service_name"
    assert "service.version" in sys_info
    assert sys_info["service.version"] == "1.0.0"


def test_init_no_version():
    sys_info = SysInfo(service_name="service_name", service_version=None)
    assert isinstance(sys_info, SysInfo)
    assert "service.name" in sys_info
    assert sys_info["service.name"] == "service_name"
    assert "service.version" not in sys_info


def test_sysinfo_is_immutable():
    with pytest.raises(TypeError):
        sys_info = SysInfo(service_name="service_name", service_version=None)
        sys_info["service_name"] = "service_name"
