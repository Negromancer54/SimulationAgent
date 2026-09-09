from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from agent_task_v3 import GoalKind, TaskGoal


class GoalSpecStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    DISABLED = "DISABLED"


class GoalResolutionStatus(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    DISABLED = "DISABLED"
    VERSION_UNAVAILABLE = "VERSION_UNAVAILABLE"


class GoalRegistrationError(ValueError):
    pass


@dataclass(frozen=True)
class GoalSpec:
    identifier: str
    kind: GoalKind
    version: int
    parameter_schema: Any = None
    semantic_contract: Any = None
    status: GoalSpecStatus = GoalSpecStatus.ACTIVE
    owner: str = "CORE"


@dataclass(frozen=True)
class GoalResolutionResult:
    status: GoalResolutionStatus
    spec: GoalSpec | None = None
    message: str = ""


class GoalRegistry:
    """
    Runtime registry of versioned GoalSpec definitions.

    Responsibilities:
        - register GoalSpec instances;
        - enforce (identifier, version) uniqueness;
        - resolve exact requested versions;
        - expose registered versions;
        - change lifecycle status.

    Non-responsibilities:
        - handler selection;
        - target resolution;
        - parameter validation against an external schema engine;
        - execution;
        - planning.
    """

    def __init__(self) -> None:
        self._specs: dict[tuple[str, int], GoalSpec] = {}

    @staticmethod
    def _validate_spec(spec: GoalSpec) -> None:
        if not isinstance(spec, GoalSpec):
            raise GoalRegistrationError(
                "GoalRegistry accepts only GoalSpec instances."
            )

        if not isinstance(spec.identifier, str) or not spec.identifier.strip():
            raise GoalRegistrationError(
                "GoalSpec.identifier must be a non-empty string."
            )

        if not isinstance(spec.version, int) or isinstance(spec.version, bool):
            raise GoalRegistrationError(
                "GoalSpec.version must be an integer."
            )

        if spec.version <= 0:
            raise GoalRegistrationError(
                "GoalSpec.version must be greater than zero."
            )

        if not isinstance(spec.kind, GoalKind):
            raise GoalRegistrationError(
                "GoalSpec.kind must be a GoalKind."
            )

        if not isinstance(spec.status, GoalSpecStatus):
            raise GoalRegistrationError(
                "GoalSpec.status must be a GoalSpecStatus."
            )

        if not isinstance(spec.owner, str) or not spec.owner.strip():
            raise GoalRegistrationError(
                "GoalSpec.owner must be a non-empty string."
            )

    def register(self, spec: GoalSpec) -> None:
        self._validate_spec(spec)

        key = (spec.identifier, spec.version)

        if key in self._specs:
            raise GoalRegistrationError(
                "GoalSpec is already registered: "
                f"{spec.identifier}@{spec.version}"
            )

        self._specs[key] = spec

    def contains(self, identifier: str, version: int) -> bool:
        return (identifier, version) in self._specs

    def resolve(
        self,
        identifier: str,
        version: int,
    ) -> GoalResolutionResult:
        key = (identifier, version)

        spec = self._specs.get(key)

        if spec is None:
            versions = self.list_versions(identifier)

            if versions:
                return GoalResolutionResult(
                    status=GoalResolutionStatus.VERSION_UNAVAILABLE,
                    message=(
                        f"Goal '{identifier}' exists, but version "
                        f"{version} is unavailable. "
                        f"Registered versions: {versions}"
                    ),
                )

            return GoalResolutionResult(
                status=GoalResolutionStatus.NOT_FOUND,
                message=(
                    f"Goal '{identifier}' is not registered."
                ),
            )

        if spec.status is GoalSpecStatus.DISABLED:
            return GoalResolutionResult(
                status=GoalResolutionStatus.DISABLED,
                spec=spec,
                message=(
                    f"Goal '{identifier}@{version}' is disabled."
                ),
            )

        return GoalResolutionResult(
            status=GoalResolutionStatus.FOUND,
            spec=spec,
            message="",
        )

    def list_versions(self, identifier: str) -> list[int]:
        versions = [
            version
            for (registered_identifier, version)
            in self._specs
            if registered_identifier == identifier
        ]

        versions.sort()
        return versions

    def deprecate(self, identifier: str, version: int) -> None:
        key = (identifier, version)
        spec = self._specs.get(key)

        if spec is None:
            raise KeyError(
                f"Unknown GoalSpec: {identifier}@{version}"
            )

        self._specs[key] = GoalSpec(
            identifier=spec.identifier,
            kind=spec.kind,
            version=spec.version,
            parameter_schema=spec.parameter_schema,
            semantic_contract=spec.semantic_contract,
            status=GoalSpecStatus.DEPRECATED,
            owner=spec.owner,
        )

    def disable(self, identifier: str, version: int) -> None:
        key = (identifier, version)
        spec = self._specs.get(key)

        if spec is None:
            raise KeyError(
                f"Unknown GoalSpec: {identifier}@{version}"
            )

        self._specs[key] = GoalSpec(
            identifier=spec.identifier,
            kind=spec.kind,
            version=spec.version,
            parameter_schema=spec.parameter_schema,
            semantic_contract=spec.semantic_contract,
            status=GoalSpecStatus.DISABLED,
            owner=spec.owner,
        )