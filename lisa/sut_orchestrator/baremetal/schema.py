# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
from dataclasses import dataclass, field
from typing import Any, List, Optional

from dataclasses_json import dataclass_json

from lisa import schema
from lisa.secret import PATTERN_HEADTAIL, add_secret
from lisa.util import field_metadata


@dataclass_json()
@dataclass
class ClientSchema:
    management_port: Optional[int] = field(default=-1)
    iso_http_url: Optional[str] = field(default="")
    connection: Optional[schema.RemoteNode] = field(
        default=None, metadata=field_metadata(required=True)
    )


@dataclass_json()
@dataclass
class ReadyCheckerSchema(schema.TypedSchema, schema.ExtendableSchemaMixin):
    type: str = field(default="file_single", metadata=field_metadata(required=True))
    timeout: int = 300


@dataclass_json()
@dataclass
class FileSchema:
    source: str = field(default="")
    destination: Optional[str] = field(default="")


@dataclass_json()
@dataclass
class BuildSchema(schema.TypedSchema, schema.ExtendableSchemaMixin):
    type: str = field(default="smb", metadata=field_metadata(required=True))
    name: str = ""
    share: str = ""
    files: List[FileSchema] = field(default_factory=list)
    is_copied: bool = False


@dataclass_json()
@dataclass
class ClusterSchema(schema.TypedSchema, schema.ExtendableSchemaMixin):
    type: str = field(default="rackmanager", metadata=field_metadata(required=True))
    build: Optional[BuildSchema] = None
    ready_checker: Optional[ReadyCheckerSchema] = None
    ip_getter: Optional[ReadyCheckerSchema] = None
    client: List[ClientSchema] = field(default_factory=list)


@dataclass_json()
@dataclass
class SourceSchema(schema.TypedSchema, schema.ExtendableSchemaMixin):
    type: str = field(default="ado", metadata=field_metadata(required=True))
    name: str = ""


@dataclass_json()
@dataclass
class ADOSourceSchema(SourceSchema):
    organization_url: str = ""
    project: str = ""
    build_id: int = 0
    pat: str = ""
    artifact_name: str = ""

    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        add_secret(self.pat)


@dataclass_json()
@dataclass
class SMBBuildSchema(BuildSchema):
    username: str = ""
    password: str = ""
    share: str = ""
    server_name: str = ""

    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        add_secret(self.username, PATTERN_HEADTAIL)
        add_secret(self.password)


@dataclass_json()
@dataclass
class IdracSchema(ClusterSchema):
    address: str = ""
    username: str = ""
    password: str = ""

    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        add_secret(self.username, PATTERN_HEADTAIL)
        add_secret(self.password)


@dataclass_json()
@dataclass
class RackManagerSchema(ClusterSchema):
    connection: Optional[schema.RemoteNode] = field(
        default=None, metadata=field_metadata(required=True)
    )


@dataclass_json()
@dataclass
class IpGetterSchema(schema.TypedSchema, schema.ExtendableSchemaMixin):
    type: str = field(default="file_single", metadata=field_metadata(required=True))


@dataclass_json()
@dataclass
class BareMetalPlatformSchema:
    source: Optional[SourceSchema] = field(default=None)
    cluster: List[ClusterSchema] = field(default_factory=list)
