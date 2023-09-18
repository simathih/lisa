# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import time
import xml.etree.ElementTree as ETree
from typing import Any, Type

import redfish  # type: ignore

from lisa import schema
from lisa.environment import Environment
from lisa.util import LisaException
from lisa.util.logger import get_logger
from lisa.util.perf_timer import create_timer

from ..schema import ClusterSchema, IdracSchema
from .cluster import Cluster


class Idrac(Cluster):
    def __init__(self, runbook: ClusterSchema) -> None:
        super().__init__(runbook)
        self.idrac_runbook: IdracSchema = self.runbook
        self._log = get_logger("idrac", self.__class__.__name__)

    @classmethod
    def type_name(cls) -> str:
        return "idrac"

    @classmethod
    def type_schema(cls) -> Type[schema.TypedSchema]:
        return IdracSchema

    def deploy(self, environment: Environment) -> Any:
        self.redfish_instance = redfish.redfish_client(
            base_url="https://" + self.idrac_runbook.address,
            username=self.idrac_runbook.username,
            password=self.idrac_runbook.password,
        )
        self._login()
        for client in self.idrac_runbook.client:
            assert client.iso_http_url, "iso_http_url is required for idrac client"
            self._insert_virtual_media(client.iso_http_url)
            self._change_boot_order_once("VCD-DVD")
            self._reboot()
            time.sleep(120)


    def _login(self) -> None:
        self.redfish_instance.login(auth="session")
        self._log.debug(f"Login to {self.redfish_instance.get_base_url()} successful.")

    def _exit(self) -> None:
        self.redfish_instance.logout()

    def _wait_for_completion(self, response: Any, timeout: int = 600) -> None:
        if response.is_processing:
            task = response.monitor(self.redfish_instance)
            timer = create_timer()
            while task.is_processing and timer.elapsed(False) < timeout:
                retry_time = task.retry_after
                time.sleep(retry_time if retry_time else 5)
                task = response.monitor(self.redfish_instance)

        if response.status not in [200, 202, 204]:
            raise LisaException("Failed to complete task! - status:", response.status)

    def _logout(self) -> None:
        self._log.debug("Logging out...")
        self.redfish_instance.logout()

    def _insert_virtual_media(self, iso_http_url: str) -> None:
        self._log.debug("Inserting virtual media...")
        body = {"Image": iso_http_url}
        response = self.redfish_instance.post(
            "/redfish/v1/Managers/iDRAC.Embedded.1/VirtualMedia/CD/Actions/"
            "VirtualMedia.InsertMedia",
            body=body,
        )
        self._wait_for_completion(response)
        self._log.debug("Inserting virtual media completed...")

    def _eject_virtual_media(self) -> None:
        self._log.debug("Ejecting virtual media...")
        response = self.redfish_instance.post(
            "/redfish/v1/Managers/iDRAC.Embedded.1/VirtualMedia/CD/Actions/"
            "VirtualMedia.EjectMedia",
            body={},
        )

        # Ignore return on failure as it is ok if no media was attached
        if response.status in [200, 202, 204]:
            self._wait_for_completion(response)

    def _change_boot_order_once(self, boot_from: str) -> None:
        self._log.debug(f"Updating boot source to {boot_from}")
        sys_config = ETree.Element("SystemConfiguration")
        component = ETree.SubElement(
            sys_config, "Component", {"FQDD": "iDRAC.Embedded.1"}
        )
        boot_once_attribute = ETree.SubElement(
            component, "Attribute", {"Name": "VirtualMedia.1#BootOnce"}
        )
        boot_once_attribute.text = "Enabled"
        first_boot_attribute = ETree.SubElement(
            component, "Attribute", {"Name": "ServerBoot.1#FirstBootDevice"}
        )
        first_boot_attribute.text = boot_from
        import_buffer = ETree.tostring(
            sys_config, encoding="utf8", method="html"
        ).decode()

        body = {"ShareParameters": {"Target": "ALL"}, "ImportBuffer": import_buffer}
        response = self.redfish_instance.post(
            "/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/"
            "EID_674_Manager.ImportSystemConfiguration",
            body=body,
        )

        self._log.debug("Waiting for boot order override task to complete...")
        self._wait_for_completion(response)
        self._log.debug(f"Updating boot source to {boot_from} completed")

    def _reboot(self) -> None:
        body = {"ResetType": "ForceRestart"}
        response = self.redfish_instance.post(
            "/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset",
            body=body,
        )
        self._wait_for_completion(response)
        self._log.debug("reboot initiated successfully.")
