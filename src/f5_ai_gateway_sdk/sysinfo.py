# Copyright (c) F5, Inc.
# This source code is licensed under the Apache License Version 2.0 found in the
# LICENSE file in the root directory of this source tree.

# This file is adapted from this code:
# https://github.com/dekobon/flask-management-endpoints/blob/master/src/flask_management_endpoints/info.py
# The original work is licensed under the BSD 3-Clause License:
# Copyright (c) 2021, Elijah Zupancic
# All rights reserved.
#
# Elijah Zupancic has transferred all rights for use of this code to F5 without
# condition.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import platform
import re
import socket
import sys
import tempfile
import uuid
from abc import ABC
from typing import Any

from opentelemetry.attributes import BoundedAttributes
from opentelemetry.semconv.resource import ResourceAttributes

# Regex that validates and parses a k8s pod name from a network hostname
pod_name_re = re.compile(r"(\w+)-([a-z0-9]{9})-([a-z0-9]{5})")


class SysInfo(BoundedAttributes, ABC):
    """
    Class providing information about the running application and host system. The data
    returned from this class is roughly in the same form as returned by Spring Actuator's
    /info endpoint with supplemental trace attributes that are in the Open Telemetry
    Resource format.
    """

    def __init__(
        self,
        service_name: str,
        service_version: str | None = None,
        enable_service_instance_id: bool = False,
    ):
        super().__init__(immutable=False)
        self.service_attributes(
            service_name=service_name, service_version=service_version
        )
        self.trace_attributes(
            service_name=service_name,
            enable_service_instance_id=enable_service_instance_id,
        )
        self._immutable = True

    def service_attributes(
        self, service_name: str | None = None, service_version: str | None = None
    ):
        """
        Method providing information about the running application.
        :param service_name: name of application
        :param service_version: version of application
        """
        if service_name:
            self[ResourceAttributes.SERVICE_NAME] = service_name
        if service_version:
            self[ResourceAttributes.SERVICE_VERSION] = service_version

    def trace_attributes(
        self, service_name: str, enable_service_instance_id: bool = False
    ):
        """
        Method providing trace information in the Open Telemetry Resource format.
        :param service_name: name of service
        :param enable_service_instance_id: when true a unique service instance is generated and stored on disk
        :return: dictionary containing Open Telemetry resource attributes
        """
        self.update(SysInfo.host_info())
        self.update(SysInfo.os_info())
        self.update(SysInfo.process_info())
        machine_id_self = SysInfo.machine_id()
        if machine_id_self:
            self.update(machine_id_self)
        container_id_self = SysInfo.container_id()
        if container_id_self:
            self.update(container_id_self)
        if enable_service_instance_id:
            service_instance_id = SysInfo.service_instance_id(service_name=service_name)
            if service_instance_id:
                self.update(service_instance_id)
        k8s_self = SysInfo.k8s()
        if k8s_self:
            self.update(k8s_self)

    @staticmethod
    def host_info(
        hostname: str | None = os.getenv("HOSTNAME") or socket.gethostname(),
    ) -> dict[str, str]:
        """
        Method providing information about the underlying host.
        :param hostname: network hostname
        """
        attributes = {
            ResourceAttributes.HOST_ARCH: platform.machine().replace("x86_64", "amd64"),
            ResourceAttributes.HOST_NAME: platform.node(),
        }

        if hostname:
            attributes["host.hostname"] = hostname

        return attributes

    @staticmethod
    def os_info() -> dict:
        """
        Method providing information about the underlying OS.
        """
        return {
            ResourceAttributes.OS_DESCRIPTION: f"{platform.system()} {platform.release()}",
            ResourceAttributes.OS_TYPE: platform.system().lower(),
        }

    @staticmethod
    def process_info() -> dict[str, Any]:
        """
        Method providing information about the application's running process.
        """
        return {
            ResourceAttributes.PROCESS_PID: os.getpid(),
            ResourceAttributes.PROCESS_COMMAND_LINE: " ".join(sys.argv),
            ResourceAttributes.PROCESS_EXECUTABLE_PATH: sys.executable,
            ResourceAttributes.PROCESS_RUNTIME_DESCRIPTION: " ".join(
                platform.python_build()
            ),
            ResourceAttributes.PROCESS_RUNTIME_NAME: platform.python_implementation(),
            ResourceAttributes.PROCESS_RUNTIME_VERSION: platform.python_version(),
        }

    @staticmethod
    def machine_id(machine_id_file: str = "/etc/machine-id") -> dict[str, str]:
        """
        Method that returns a unique machine id as read from a file on the local filesystem.
        :param machine_id_file: path to file containing machine id file
        """
        attributes = {}

        file_content = SysInfo.read_first_line(machine_id_file)
        if file_content:
            attributes["machine.id"] = file_content

        return attributes

    @staticmethod
    def container_id(cpuset_file: str = "/proc/1/cpuset") -> dict[str, str]:
        """
        Method that returns the running container id if available.
        :param cpuset_file: path to file containing cpuset details
        """
        attributes = {}

        file_content = SysInfo.read_first_line(cpuset_file)
        if file_content:
            tokens = file_content.split("/")
            if len(tokens) > 0:
                container_id = tokens[len(tokens) - 1]
                if container_id != "":
                    attributes[ResourceAttributes.CONTAINER_ID] = container_id

        return attributes

    @staticmethod
    def service_instance_id(
        service_name: str, service_instance_id_file: str | None = None
    ):
        """
        Method that generates a unique service id and stores it on a file in the file system. This
        service id would remain constant for the life of an application on a given host.
        :param service_name: name of application
        :param service_instance_id_file: name of file to store service instance id in
        """
        if not service_instance_id_file:
            tempdir = tempfile.gettempdir()
            filename = f"{service_name}-service-instance-id"
            service_instance_id_file = os.path.join(tempdir, filename)

        attributes = {}

        service_instance_id = SysInfo.read_first_line(service_instance_id_file)
        if not service_instance_id:
            with open(service_instance_id_file, "wt") as file:
                service_instance_id = str(uuid.uuid1()).replace("-", "")
                file.write(service_instance_id)
                file.write("\n")

        attributes[ResourceAttributes.SERVICE_INSTANCE_ID] = service_instance_id

        return attributes

    @staticmethod
    def k8s(
        hostname: str | None = os.getenv("HOSTNAME") or socket.gethostname(),
        namespace: str | None = os.getenv("NAMESPACE"),
    ) -> dict | None:
        """
        Method that returns details about the running Kubernetes environment.
        :param hostname: network hostname from which the pod name will be parsed
        :param namespace: kubernetes namespace
        :return:
        """
        if not hostname and not namespace:
            return None

        attributes = {}
        if hostname:
            pod_name_pattern = pod_name_re.match(hostname)
            if pod_name_pattern:
                attributes[ResourceAttributes.K8S_POD_NAME] = hostname
                attributes[ResourceAttributes.K8S_CONTAINER_NAME] = (
                    pod_name_pattern.group(1)
                )

        if namespace:
            attributes[ResourceAttributes.K8S_NAMESPACE_NAME] = namespace

        return attributes

    @staticmethod
    def read_first_line(file: str) -> str | None:
        """
        Utility method that reads the first 1024 characters from a file into a string.
        :param file: file to read
        :return: string containing contents of file
        """
        if os.path.isfile(file):
            # noinspection PyBroadException
            try:
                with open(file, "rt") as reader:
                    content = reader.readline(1024).strip()
                    if content == "":
                        return None
                    else:
                        return content
            except Exception:
                return None

        return None


__all__ = ["SysInfo"]
