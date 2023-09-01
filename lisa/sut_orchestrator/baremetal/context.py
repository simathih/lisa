from dataclasses import dataclass

from lisa.environment import Environment
from lisa.node import Node


@dataclass
class EnvironmentContext:
    ssh_public_key: str = ""


@dataclass
class NodeContext:
    address: str = ""
    username: str = ""
    password: str = ""
    private_key_file: str = ""
    port: int = 22


def get_environment_context(environment: Environment) -> EnvironmentContext:
    return environment.get_context(EnvironmentContext)


def get_node_context(node: Node) -> NodeContext:
    return node.get_context(NodeContext)
