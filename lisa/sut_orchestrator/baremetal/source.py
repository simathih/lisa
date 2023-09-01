# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import re
import zipfile
from typing import Type

import requests
from azure.devops.connection import Connection  # type: ignore
from msrest.authentication import BasicAuthentication

from lisa import schema
from lisa.util import InitializableMixin, constants, get_matched_str, subclasses
from lisa.util.logger import get_logger

from .schema import ADOSourceSchema, SourceSchema


class Source(subclasses.BaseClassWithRunbookMixin, InitializableMixin):
    def __init__(self, runbook: SourceSchema) -> None:
        super().__init__(runbook=runbook)
        self._log = get_logger("source", self.__class__.__name__)

    @classmethod
    def type_schema(cls) -> Type[schema.TypedSchema]:
        return SourceSchema

    def download(self) -> str:
        raise NotImplementedError()


class ADOSource(Source):
    __file_format = re.compile(r"format=(?P<format>.*)", re.M)

    def __init__(self, runbook: ADOSourceSchema) -> None:
        super().__init__(runbook)
        self.ado_runbook: ADOSourceSchema = self.runbook
        self._log = get_logger("ado", self.__class__.__name__)

    @classmethod
    def type_name(cls) -> str:
        return "ado"

    @classmethod
    def type_schema(cls) -> Type[schema.TypedSchema]:
        return ADOSourceSchema

    def download(self) -> str:
        personal_access_token = self.ado_runbook.pat
        organization_url = self.ado_runbook.organization_url
        credentials = BasicAuthentication("", personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)
        project_name = self.ado_runbook.project
        artifact_name = self.ado_runbook.artifact_name

        pipeline_client = connection.clients.get_build_client()
        build_id = self.ado_runbook.build_id

        artifact = pipeline_client.get_artifact(project_name, build_id, artifact_name)
        download_url = artifact.resource.download_url
        working_path = constants.RUN_LOCAL_WORKING_PATH
        self._log.info(f"Artifact download url: {download_url}")

        working_path.mkdir(parents=True, exist_ok=True)
        file_extension = get_matched_str(download_url, self.__file_format)
        artifact_path = working_path / f"{artifact.name}.{file_extension}"
        with open(
            artifact_path,
            "wb",
        ) as download_file:
            response = requests.get(
                download_url, auth=("", personal_access_token), timeout=600
            )
            download_file.write(response.content)

        if file_extension == "zip":
            with zipfile.ZipFile(artifact_path, "r") as zip_ref:
                zip_ref.extractall(working_path)
        source_path = str(working_path / f"{artifact.name}")
        self._log.info(f"Artifact extracted to {source_path}")
        return source_path
