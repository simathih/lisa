# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from typing import Any, Type

from lisa import schema
from lisa.environment import Environment
from lisa.node import quick_connect
from lisa.util.logger import get_logger

from ..schema import RackManagerSchema
from .cluster import Cluster


class RackManager(Cluster):
    def __init__(self, runbook: RackManagerSchema) -> None:
        super().__init__(runbook)
        self.rm_runbook: RackManagerSchema = self.runbook
        self._log = get_logger("rackmanager", self.__class__.__name__)

    @classmethod
    def type_name(cls) -> str:
        return "rackmanager"

    @classmethod
    def type_schema(cls) -> Type[schema.TypedSchema]:
        return RackManagerSchema

    def deploy(self, environment: Environment) -> Any:
        assert self.rm_runbook.connection, "connection is required for rackmanager"
        self.rm_runbook.connection.name = "rackmanager"
        node = quick_connect(self.rm_runbook.connection, logger_name="rackmanager")

        assert self.rm_runbook.client, "client is required for rackmanager"
        for client in self.rm_runbook.client:
            assert (
                client.management_port
            ), "management_port is required for rackmanager client"
            node.execute(f"set system reset -i {client.management_port}")

        self._log.debug("client has been reset successfully")
