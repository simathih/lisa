# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from typing import Any, List, Type

from lisa import RemoteNode, feature, schema
from lisa.environment import Environment
from lisa.platform_ import Platform
from lisa.util import fields_to_dict
from lisa.util.logger import Logger
from lisa.util.shell import try_connect
from lisa.util.subclasses import Factory

from .. import BAREMETAL
from . import features
from .build import Build
from .cluster.cluster import Cluster
from .context import get_node_context
from .ip_getter import IpGetterChecker
from .readychecker import ReadyChecker
from .schema import BareMetalPlatformSchema, BuildSchema
from .source import Source


class BareMetalPlatform(Platform):
    def __init__(
        self,
        runbook: schema.Platform,
    ) -> None:
        super().__init__(runbook=runbook)

    @classmethod
    def type_name(cls) -> str:
        return BAREMETAL

    @classmethod
    def supported_features(cls) -> List[Type[feature.Feature]]:
        return [features.StartStop, features.SerialConsole]

    def _initialize(self, *args: Any, **kwargs: Any) -> None:
        baremetal_runbook: BareMetalPlatformSchema = self.runbook.get_extended_runbook(
            BareMetalPlatformSchema
        )
        assert baremetal_runbook, "platform runbook cannot be empty"
        self._baremetal_runbook = baremetal_runbook
        self.source_path: str = ""
        self.ready_checker_factory = Factory[ReadyChecker](ReadyChecker)
        self.cluster_factory = Factory[Cluster](Cluster)
        self.ip_getter_factory = Factory[IpGetterChecker](IpGetterChecker)
        self.source_factory = Factory[Source](Source)
        self.build_factory = Factory[Build](Build)

    def _prepare_environment(self, environment: Environment, log: Logger) -> bool:
        return True

    def _deploy_environment(self, environment: Environment, log: Logger) -> None:
        # currently only support one cluster
        assert self._baremetal_runbook.cluster, "no cluster is specified in the runbook"
        cluster_instance = self._baremetal_runbook.cluster[0]

        cluster = self.cluster_factory.create_by_runbook(cluster_instance)
        assert cluster.runbook.client, "no client is specified in the runbook"

        # copy build (shared, check if it's copied)
        if self._baremetal_runbook.source and not self.source_path:
            source = self.source_factory.create_by_runbook(
                self._baremetal_runbook.source
            )
            self._log.debug(f"found build '{source.type_name()}', to expand runbook.")
            self.source_path = source.download()

        # ready checker cleanup
        if cluster_instance.ready_checker:
            ready_checker = self.ready_checker_factory.create_by_runbook(
                cluster_instance.ready_checker
            )
            ready_checker.clean_up()

        # copy build if source exists
        if cluster.runbook.build and cluster.runbook.build.is_copied:
            self.copy(cluster.runbook.build, source_path=self.source_path)
            cluster.runbook.build.is_copied = True

        assert environment.runbook.nodes_requirement, "no node is specified"
        for node_space in environment.runbook.nodes_requirement:
            assert isinstance(
                node_space, schema.NodeSpace
            ), f"actual: {type(node_space)}"
            environment.create_node_from_requirement(node_space)

        for index, node in enumerate(environment.nodes.list()):
            node_context = get_node_context(node)
            node_context.address = cluster.runbook.client[index].connection.address
            node_context.port = cluster.runbook.client[index].connection.port
            node_context.private_key_file = cluster.runbook.client[
                index
            ].connection.private_key_file
            node_context.password = cluster.runbook.client[index].connection.password
            node_context.username = cluster.runbook.client[index].connection.username
            index = index + 1

        # deploy cluster
        cluster.deploy(environment)

        if cluster_instance.ready_checker:
            ready_checker = self.ready_checker_factory.create_by_runbook(
                cluster_instance.ready_checker
            )

        for index, node in enumerate(environment.nodes.list()):
            # ready checker
            if ready_checker:
                ready_checker.is_ready(node)

            # get ip address
            if cluster_instance.ip_getter:
                ip_getter = self.ip_getter_factory.create_by_runbook(
                    cluster_instance.ip_getter
                )
                cluster.runbook.client[index].connection.address = ip_getter.get_ip()

            assert cluster.runbook.client[
                index
            ].connection, "client connection is empty"
            assert cluster.runbook.client[
                index
            ].connection.address, "ip address is empty"
            assert isinstance(
                node, RemoteNode
            ), "The client node must be remote node with connection information"
            node.name = f"node_{index}"
            connection_info = schema.ConnectionInfo(
                address=cluster.runbook.client[index].connection.address,
                port=cluster.runbook.client[index].connection.port,
                username=cluster.runbook.client[index].connection.username,
                private_key_file=cluster.runbook.client[
                    index
                ].connection.private_key_file,
                password=cluster.runbook.client[index].connection.password,
            )
            node.set_connection_info(
                **fields_to_dict(
                    connection_info,
                    ["address", "port", "username", "password", "private_key_file"],
                ),
            )
            try_connect(connection_info)

        self._log.debug(f"deploy environment {environment.name} successfully")

    def copy(self, build_schema: BuildSchema, source_path: str) -> None:
        if source_path:
            build = self.build_factory.create_by_runbook(build_schema)
            build.copy(
                source_path=source_path,
                files_map=build_schema.files,
            )
        else:
            self._log.debug("no source path specified, skip copy")
