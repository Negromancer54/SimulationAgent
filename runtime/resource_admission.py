from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from runtime.execution_plan import ResourceRequirements
from runtime.execution_policy import ResourcePolicy


class ResourceAdmissionStatus(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ResourceAdmissionResult:
    status: ResourceAdmissionStatus
    message: str = ""

    @property
    def allowed(self) -> bool:
        return self.status is ResourceAdmissionStatus.ALLOW

    @property
    def denied(self) -> bool:
        return self.status is ResourceAdmissionStatus.DENY

    @property
    def invalid(self) -> bool:
        return self.status is ResourceAdmissionStatus.INVALID


class ResourceAdmission:
    """
    Checks whether one PlanStep's resource requirements can be
    satisfied by the effective runtime resource policy.

    This class does not:
        - allocate resources;
        - release resources;
        - execute handlers;
        - perform retries;
        - perform scheduling;
        - modify the plan or policies.

    It only answers:
        "Can this step be admitted under these limits?"
    """

    def check(
        self,
        requirements: ResourceRequirements,
        policy: ResourcePolicy,
    ) -> ResourceAdmissionResult:
        if not isinstance(
            requirements,
            ResourceRequirements,
        ):
            raise TypeError(
                "ResourceAdmission requires "
                "ResourceRequirements."
            )

        if not isinstance(
            policy,
            ResourcePolicy,
        ):
            raise TypeError(
                "ResourceAdmission requires "
                "ResourcePolicy."
            )

        required = requirements.resources
        available = policy.values

        for resource_id, required_value in required.items():
            available_value = available.get(
                resource_id
            )

            if available_value is None:
                return ResourceAdmissionResult(
                    status=ResourceAdmissionStatus.DENY,
                    message=(
                        "Required resource is unavailable: "
                        f"{resource_id}."
                    ),
                )

            if required_value > available_value:
                return ResourceAdmissionResult(
                    status=ResourceAdmissionStatus.DENY,
                    message=(
                        "Required resource exceeds "
                        f"runtime limit: {resource_id}."
                    ),
                )

        return ResourceAdmissionResult(
            status=ResourceAdmissionStatus.ALLOW,
            message="",
        )