from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_task_v3 import (
    GoalKind,
    TaskOperation,
    TargetKind,
)
from runtime.execution_policy import HandlerExecutionPolicy

class HandlerSpecStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    DISABLED = "DISABLED"


class HandlerRegistrationError(ValueError):
    pass


@dataclass(frozen=True)
class HandlerApplicability:
    """
    Declarative applicability constraints.

    Empty tuple means "unrestricted" for that dimension.
    All restrictions are ANDed.
    """

    operations: tuple[TaskOperation, ...] = ()
    target_kinds: tuple[TargetKind, ...] = ()
    projects: tuple[str, ...] = ()
    environments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operations",
            tuple(sorted(set(self.operations), key=lambda x: x.value)),
        )
        object.__setattr__(
            self,
            "target_kinds",
            tuple(sorted(set(self.target_kinds), key=lambda x: x.value)),
        )
        object.__setattr__(
            self,
            "projects",
            tuple(sorted(set(self.projects))),
        )
        object.__setattr__(
            self,
            "environments",
            tuple(sorted(set(self.environments))),
        )


@dataclass(frozen=True)
class HandlerSpec:
    handler_id: str
    goal_identifier: str
    goal_version: int
    applicability: HandlerApplicability = HandlerApplicability()
    required_capabilities: tuple[str, ...] = ()
    execution_policy: HandlerExecutionPolicy | None = None
    owner: str = "CORE"
    status: HandlerSpecStatus = HandlerSpecStatus.ACTIVE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_capabilities",
            tuple(sorted(set(self.required_capabilities))),
        )


class HandlerRegistry:
    """
    Registry of runtime handlers for versioned GoalSpecs.

    The registry owns definitions only.

    It does not:
        - choose a handler;
        - inspect runtime capabilities;
        - evaluate task applicability;
        - execute handlers.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, HandlerSpec] = {}

    @staticmethod
    def _validate_spec(spec: HandlerSpec) -> None:
        if not isinstance(spec, HandlerSpec):
            raise HandlerRegistrationError(
                "HandlerRegistry accepts only HandlerSpec instances."
            )

        if (
            not isinstance(spec.handler_id, str)
            or not spec.handler_id.strip()
        ):
            raise HandlerRegistrationError(
                "HandlerSpec.handler_id must be a non-empty string."
            )

        if (
            not isinstance(spec.goal_identifier, str)
            or not spec.goal_identifier.strip()
        ):
            raise HandlerRegistrationError(
                "HandlerSpec.goal_identifier must be a non-empty string."
            )

        if (
            not isinstance(spec.goal_version, int)
            or isinstance(spec.goal_version, bool)
            or spec.goal_version <= 0
        ):
            raise HandlerRegistrationError(
                "HandlerSpec.goal_version must be a positive integer."
            )

        if not isinstance(spec.applicability, HandlerApplicability):
            raise HandlerRegistrationError(
                "HandlerSpec.applicability must be a HandlerApplicability."
            )

        if not isinstance(spec.status, HandlerSpecStatus):
            raise HandlerRegistrationError(
                "HandlerSpec.status must be a HandlerSpecStatus."
            )

        if (
            not isinstance(spec.owner, str)
            or not spec.owner.strip()
        ):
            raise HandlerRegistrationError(
                "HandlerSpec.owner must be a non-empty string."
            )

        for capability in spec.required_capabilities:
            if (
                not isinstance(capability, str)
                or not capability.strip()
            ):
                raise HandlerRegistrationError(
                    "HandlerSpec.required_capabilities must contain "
                    "non-empty strings."
                )

    def register(self, spec: HandlerSpec) -> None:
        self._validate_spec(spec)

        if spec.handler_id in self._handlers:
            raise HandlerRegistrationError(
                f"Handler is already registered: {spec.handler_id}"
            )

        self._handlers[spec.handler_id] = spec

    def contains(self, handler_id: str) -> bool:
        return handler_id in self._handlers

    def get(self, handler_id: str) -> HandlerSpec | None:
        return self._handlers.get(handler_id)

    def list_for_goal(
        self,
        goal_identifier: str,
        goal_version: int,
    ) -> list[HandlerSpec]:
        handlers = [
            handler
            for handler in self._handlers.values()
            if (
                handler.goal_identifier == goal_identifier
                and handler.goal_version == goal_version
            )
        ]

        handlers.sort(key=lambda handler: handler.handler_id)
        return handlers

    def disable(
        self,
        handler_id: str,
    ) -> None:
        handler = self._require(handler_id)

        self._handlers[handler_id] = HandlerSpec(
            handler_id=handler.handler_id,
            goal_identifier=handler.goal_identifier,
            goal_version=handler.goal_version,
            applicability=handler.applicability,
            required_capabilities=handler.required_capabilities,
            execution_policy=handler.execution_policy,
            owner=handler.owner,
            status=HandlerSpecStatus.DISABLED,
        )

    def deprecate(
        self,
        handler_id: str,
    ) -> None:
        handler = self._require(handler_id)

        self._handlers[handler_id] = HandlerSpec(
            handler_id=handler.handler_id,
            goal_identifier=handler.goal_identifier,
            goal_version=handler.goal_version,
            applicability=handler.applicability,
            required_capabilities=handler.required_capabilities,
            execution_policy=handler.execution_policy,
            owner=handler.owner,
            status=HandlerSpecStatus.DEPRECATED,
        )

    def _require(self, handler_id: str) -> HandlerSpec:
        handler = self._handlers.get(handler_id)

        if handler is None:
            raise KeyError(
                f"Unknown handler: {handler_id}"
            )

        return handler