# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import random
import re
from typing import List

from assertpy import assert_that

from lisa import (
    Logger,
    Node,
    TestCaseMetadata,
    TestSuite,
    TestSuiteMetadata,
    simple_requirement,
)
from lisa.base_tools.service import Service
from lisa.operating_system import BSD
from lisa.sut_orchestrator.azure.common import (
    add_system_assign_identity,
    assign_access_policy_to_vm,
    check_certificate_existence,
    create_certificate,
    create_keyvault,
    delete_certificate,
    get_identity_id,
    get_node_context,
    get_tenant_id,
    rotate_certificate,
)
from lisa.sut_orchestrator.azure.features import AzureExtension
from lisa.sut_orchestrator.azure.platform_ import AzurePlatform, AzurePlatformSchema
from lisa.testsuite import TestResult
from lisa.tools.ls import Ls
from lisa.util import LisaException


def _check_system_status(node: Node, log: Logger) -> None:
    # Check the status of the akvvm_service service using the Service tool
    service = node.tools[Service]
    if service.is_service_running("akvvm_service.service"):
        log.info("akvvm_service is running")
    else:
        log.info("akvvm_service is not running")
        raise LisaException("akvvm_service is not running. Test case failed.")

    # List the contents of the directory
    ls = node.tools[Ls]
    directory_contents = ls.run(
        "/var/lib/waagent/Microsoft.Azure.KeyVault -la", sudo=True
    ).stdout
    log.info(f"Directory contents: {directory_contents}")


@TestSuiteMetadata(
    area="vm_extension",
    category="functional",
    description="BVT for Azure Key Vault Extension",
    requirement=simple_requirement(unsupported_os=[]),
)
class AzureKeyVaultExtensionBvt(TestSuite):
    @TestCaseMetadata(
        description="""
        The following test case validates the Azure Key Vault Linux
        * Extension while creating the following resources:
        * A Key Vault
        * Two certificates in the Key Vault
        * Retrieval of the certificate's secrets
        through SecretClient class from Azure SDK.
        * Installation of the Azure Key Vault Linux Extension on the VM.
        * Installation of the certs through AKV extension
        * Rotation of the certificates
        * Printing the cert after rotation from the VM
        * Deletion of the resources
        """,
        priority=1,
        requirement=simple_requirement(
            supported_features=[AzureExtension], unsupported_os=[BSD]
        ),
    )
    def verify_key_vault_extension(
        self, log: Logger, node: Node, result: TestResult
    ) -> None:
        # Section for environment setup
        environment = result.environment
        assert environment, "fail to get environment from testresult"
        platform = environment.platform
        assert isinstance(platform, AzurePlatform)
        runbook = platform.runbook.get_extended_runbook(AzurePlatformSchema)
        resource_group_name = runbook.shared_resource_group_name
        vault_name = f"kve-{platform.subscription_id[-6:]}"
        node_context = get_node_context(node)
        tenant_id = get_tenant_id(platform.credential)
        if tenant_id is None:
            raise ValueError("Environment variable 'tenant_id' is not set.")
        object_id = get_identity_id(platform)
        if object_id is None:
            raise ValueError("Environment variable 'object_id' is not set.")

        # Object ID System assignment
        object_id_vm = add_system_assign_identity(
            platform=platform,
            resource_group_name=node_context.resource_group_name,
            vm_name=node_context.vm_name,
            location=node_context.location,
            log=log,
        )

        # Create Key Vault
        keyvault_result = create_keyvault(
            platform=platform,
            resource_group_name=resource_group_name,
            tenant_id=tenant_id,
            object_id=object_id,
            location=node_context.location,
            vault_name=vault_name,
        )

        # Check if KeyVault is successfully created before proceeding
        assert keyvault_result, f"Failed to create KeyVault with name: {vault_name}"

        # Acces policies for VM
        assign_access_policy_to_vm(
            platform=platform,
            resource_group_name=resource_group_name,
            tenant_id=tenant_id,
            object_id_vm=object_id_vm,
            vault_name=vault_name,
        )

        log.info(f"Created Key Vault {keyvault_result.properties.vault_uri}")

        certificates_secret_id: List[str] = []
        # Providing a random Cert name format is: Cert-xxx
        for cert_name in [f"Cert-{random.randint(1, 1000):03}" for _ in range(2)]:
            certificate_secret_id = create_certificate(
                platform=platform,
                vault_url=keyvault_result.properties.vault_uri,
                log=log,
                cert_name=cert_name,
            )
            log.info(f"Certificates created. Cert ID: {certificate_secret_id}, ")
            assert_that(certificate_secret_id).described_as(
                "First certificate created successfully"
            ).is_not_none()
            certificates_secret_id.append(certificate_secret_id)

        # Extension
        extension_name = "KeyVaultForLinux"
        extension_publisher = "Microsoft.Azure.KeyVault"
        extension_version = "2.0"
        settings = {
            "secretsManagementSettings": {
                "autoUpgradeMinorVersion": True,
                "enableAutomaticUpgrade": True,
                "pollingIntervalInS": "360",
                "certificateStoreLocation": "/var/lib/waagent/Microsoft.Azure.KeyVault",
                "observedCertificates": [
                    certificates_secret_id[0],
                    certificates_secret_id[1],
                ],
            }
        }
        extension = node.features[AzureExtension]
        extension_result = extension.create_or_update(
            name=extension_name,
            publisher=extension_publisher,
            type_=extension_name,
            type_handler_version=extension_version,
            auto_upgrade_minor_version=True,
            enable_automatic_upgrade=True,
            settings=settings,
        )
        assert_that(extension_result["provisioning_state"]).described_as(
            "Expected the extension to succeed"
        ).is_equal_to("Succeeded")

        # Rotate certificates
        # Example: "https://example.vault.azure.net/secrets/Cert-123"
        # Expected match: "Cert-123"
        match = re.search(r"/(?P<certificate_name>[^/]+)$", certificates_secret_id[0])
        if match:
            cert_name = match.group("certificate_name")
        else:
            raise LisaException(
                f"Failed to extract certificate name from {certificates_secret_id[0]}"
            )
        rotate_certificate(
            platform=platform,
            vault_url=keyvault_result.properties.vault_uri,
            cert_name=cert_name,
            log=log,
        )

        _check_system_status(node, log)

        for cert_secret_id in certificates_secret_id:
            # Example: "https://example.vault.azure.net/secrets/Cert-123"
            # Expected match for 'certificate_name': "Cert-123"
            match = re.search(r"/(?P<certificate_name>[^/]+)$", cert_secret_id)
            if match:
                cert_name = match.group("certificate_name")
            else:
                raise LisaException(
                    f"Failed to extract certificate name from {cert_secret_id}"
                )
            delete_certificate(
                platform=platform,
                vault_url=keyvault_result.properties.vault_uri,
                cert_name=cert_name,
                log=log,
            )

            certificate_exists = check_certificate_existence(
                log=log,
                platform=platform,
                vault_url=keyvault_result.properties.vault_uri,
                cert_name=cert_name,
            )

            assert_that(certificate_exists).described_as(
                f"The certificate '{cert_name}' was not deleted after 10 attempts."
            ).is_false()

        # Delete VM Extension
        extension.delete("KeyVaultForLinux")

        assert_that(extension.check_exist("KeyVaultForLinux")).described_as(
            "Found the VM Extension still exists on the VM after deletion"
        ).is_false()
