# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from typing import Any, List, Type, Union, cast

from dataclasses_json import dataclass_json

from lisa import features, schema, search_space
from lisa.environment import Environment
from lisa.feature import Feature
from lisa.features.security_profile import FEATURE_NAME_SECURITY_PROFILE, SecurityProfileType
from lisa.sut_orchestrator.libvirt.context import get_node_context
from lisa.util import constants, field_metadata

# FEATURE_NAME_GUEST_VM_PROFILE = "GUEST_VM_TYPE"


# class GuestVMProfileType(str, Enum):
#     CVM = constants.GUEST_VM_TYPE_CVM
#     NON_CVM = constants.GUEST_VM_TYPE_NON_CVM


# guest_vm_profile_priority: List[GuestVMProfileType] = [
#     GuestVMProfileType.NON_CVM,
#     GuestVMProfileType.CVM,
# ]


# @dataclass_json()
# @dataclass()
# class GuestVMProfileSettings(schema.FeatureSettings):
#     type: str = FEATURE_NAME_GUEST_VM_PROFILE
#     guest_vm_profile: Union[
#         search_space.SetSpace[GuestVMProfileType], GuestVMProfileType
#     ] = field(  # type:ignore
#         default_factory=partial(
#             search_space.SetSpace,
#             items=[
#                 GuestVMProfileType.NON_CVM,
#                 GuestVMProfileType.CVM,
#             ],
#         ),
#         metadata=field_metadata(
#             decoder=lambda input: (
#                 search_space.decode_set_space_by_type(
#                     data=input, base_type=GuestVMProfileType
#                 )
#                 if str(input).strip()
#                 else search_space.SetSpace(
#                     items=[
#                         GuestVMProfileType.NON_CVM,
#                         GuestVMProfileType.CVM,
#                     ]
#                 )
#             )
#         ),
#     )
#     igvm: str = field(default="")

#     def __hash__(self) -> int:
#         return hash(self._get_key())

#     def _get_key(self) -> str:
#         return f"{self.type}/{self.guest_vm_profile}/{self.igvm}"

#     def _call_requirement_method(
#         self, method: search_space.RequirementMethod, capability: Any
#     ) -> Any:
#         value = GuestVMProfileSettings()
#         value.guest_vm_profile = getattr(
#             search_space, f"{method.value}_setspace_by_priority"
#         )(
#             self.guest_vm_profile,
#             capability.guest_vm_profile,
#             guest_vm_profile_priority,
#         )
#         value.igvm = self.igvm or capability.igvm
#         return value

#     def check(self, capability: Any) -> search_space.ResultReason:
#         assert isinstance(
#             capability, GuestVMProfileSettings
#         ), f"actual: {type(capability)}"
#         result = super().check(capability)
#         result.merge(
#             search_space.check_setspace(
#                 self.guest_vm_profile, capability.guest_vm_profile
#             ),
#             "guest_vm_profile",
#         )
#         return result


# class GuestVMProfile(Feature):
#     @classmethod
#     def on_before_deployment(cls, *args: Any, **kwargs: Any) -> None:
#         environment = cast(Environment, kwargs.get("environment"))
#         for node in environment.nodes._list:
#             guest_vm_profile = [
#                 feature_setting
#                 for feature_setting in node.capability.features.items
#                 if feature_setting.type == FEATURE_NAME_GUEST_VM_PROFILE
#             ]
#             if guest_vm_profile:
#                 settings: GuestVMProfileSettings = guest_vm_profile[0]
#                 print(f"====>>>> settings {settings}")
#                 print(f"====>>>> settings-type {type(settings)}")
#                 print(f"====>>>> guest_vm_profile {settings.guest_vm_profile}")
#                 print(f"====>>>> guest_vm_profile-type {type(settings.guest_vm_profile)}")
#                 assert isinstance(settings, GuestVMProfileSettings)
#                 assert isinstance(settings.guest_vm_profile, GuestVMProfileType)
#                 node_context = get_node_context(node)
#                 node_context.guest_vm_type = settings.guest_vm_profile
#                 node_context.igvm_source_path = settings.igvm

#     @classmethod
#     def name(cls) -> str:
#         return FEATURE_NAME_GUEST_VM_PROFILE

#     @classmethod
#     def settings_type(cls) -> Type[schema.FeatureSettings]:
#         return GuestVMProfileSettings

#     @classmethod
#     def can_disable(cls) -> bool:
#         return True

#     def enabled(self) -> bool:
#         return True


@dataclass_json()
@dataclass()
class SecurityProfileSettings(features.SecurityProfileSettings):
    igvm: str = field(
        default="",
        metadata=field_metadata(
            required=False,
        ),
    )

    def __hash__(self) -> int:
        return hash(self._get_key())

    def _get_key(self) -> str:
        return (
            f"{self.type}/{self.security_profile}/"
            f"{self.igvm}"
        )

    def _call_requirement_method(
        self, method: search_space.RequirementMethod, capability: Any
    ) -> Any:
        super_value: SecurityProfileSettings = super()._call_requirement_method(
            method, capability
        )
        value = SecurityProfileSettings()
        value.security_profile = super_value.security_profile
        value.encrypt_disk = super_value.encrypt_disk

        if self.igvm:
            value.igvm = self.igvm
        else:
            value.igvm = capability.igvm

        return value


class SecurityProfile(features.SecurityProfile):
    # Convert Security Profile Setting to Arm Parameter Value
    _security_profile_mapping = {
        SecurityProfileType.Standard: "NON-CVM",
        SecurityProfileType.CVM: "CVM",
    }

    def _initialize(self, *args: Any, **kwargs: Any) -> None:
        super()._initialize(*args, **kwargs)
        self._initialize_information(self._node)

    @classmethod
    def settings_type(cls) -> Type[schema.FeatureSettings]:
        return SecurityProfileSettings

    @classmethod
    def on_before_deployment(cls, *args: Any, **kwargs: Any) -> None:
        environment = cast(Environment, kwargs.get("environment"))

        for node in environment.nodes._list:
            assert node.capability.features
            security_profile = [
                feature_setting
                for feature_setting in node.capability.features.items
                if feature_setting.type == FEATURE_NAME_SECURITY_PROFILE
            ]
            if security_profile:
                settings = security_profile[0]
                print(f"====>>>> settings {settings}")
                print(f"====>>>> settings-type {type(settings)}")
                assert isinstance(settings, SecurityProfileSettings)
                assert isinstance(settings.security_profile, SecurityProfileType)
                node_context = get_node_context(node)
                node_context.guest_vm_type = cls._security_profile_mapping[
                    settings.security_profile
                ]
                node_context.igvm_source_path = settings.igvm
