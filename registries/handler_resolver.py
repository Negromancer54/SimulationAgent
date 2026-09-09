from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_task_v3 import TaskV3, TaskOperation, TargetKind
from registries.handler_registry import (
    HandlerApplicability,
    HandlerRegistry,
    HandlerSpec,
    HandlerSpecStatus,
)


class SpecificityRelation(str, Enum):
    LESS_SPECIFIC = "LESS_SPECIFIC"
    EQUIVALENT = "EQUIVALENT"
    MORE_SPECIFIC = "MORE_SPECIFIC"
    INCOMPARABLE = "INCOMPARABLE"


class HandlerResolverStatus(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"


@dataclass(frozen=True)
class HandlerRuntimeContext:
    capabilities: frozenset[str] = frozenset()
    environment: str | None = None


@dataclass(frozen=True)
class HandlerResolution:
    status: HandlerResolverStatus
    task: TaskV3
    handler: HandlerSpec | None = None
    candidates: tuple[HandlerSpec, ...] = ()
    message: str = ""

    @property
    def resolved(self) -> bool:
        return self.status is HandlerResolverStatus.FOUND


class HandlerResolver:
    """
    Selects a handler using:

        1. goal identity;
        2. applicability compatibility;
        3. capability compatibility;
        4. partial-order specificity;
        5. stable handler_id tie-break for equivalent profiles.

    Numeric priority is deliberately not used.
    """

    def __init__(
        self,
        registry: HandlerRegistry,
    ) -> None:
        self._registry = registry

    @staticmethod
    def _validate_context(
        context: HandlerRuntimeContext,
    ) -> str | None:
        if not isinstance(context, HandlerRuntimeContext):
            return (
                "HandlerResolver accepts only "
                "HandlerRuntimeContext instances."
            )

        for capability in context.capabilities:
            if (
                not isinstance(capability, str)
                or not capability.strip()
            ):
                return (
                    "Runtime capabilities must contain "
                    "non-empty strings."
                )

        if (
            context.environment is not None
            and (
                not isinstance(context.environment, str)
                or not context.environment.strip()
            )
        ):
            return (
                "Runtime environment must be None "
                "or a non-empty string."
            )

        return None

    @staticmethod
    def _validate_task(task: TaskV3) -> str | None:
        if not isinstance(task, TaskV3):
            return (
                "HandlerResolver accepts only TaskV3 instances."
            )

        if task.intent is None:
            return "TaskV3.intent must be present."

        if task.intent.target is None:
            return "TaskV3.intent.target must be present."

        if task.intent.goal is None:
            return "TaskV3.intent.goal must be present."

        return None

    @staticmethod
    def _matches_applicability(
        applicability: HandlerApplicability,
        operation: TaskOperation,
        target_kind: TargetKind,
        project: str | None,
        environment: str | None,
    ) -> bool:
        if (
            applicability.operations
            and operation not in applicability.operations
        ):
            return False

        if (
            applicability.target_kinds
            and target_kind not in applicability.target_kinds
        ):
            return False

        if (
            applicability.projects
            and project not in applicability.projects
        ):
            return False

        if (
            applicability.environments
            and environment not in applicability.environments
        ):
            return False

        return True

    @staticmethod
    def _has_capabilities(
        handler: HandlerSpec,
        available: frozenset[str],
    ) -> bool:
        return set(handler.required_capabilities).issubset(
            available
        )

    @staticmethod
    def _compare_dimension(
        left: tuple,
        right: tuple,
    ) -> SpecificityRelation:
        """
        Compare one applicability dimension.

        Empty means unrestricted.

        A non-empty strict subset of B means A is more specific.
        B empty and A non-empty also means A is more specific.
        """

        left_set = set(left)
        right_set = set(right)

        if not left_set and not right_set:
            return SpecificityRelation.EQUIVALENT

        if not left_set and right_set:
            return SpecificityRelation.LESS_SPECIFIC

        if left_set and not right_set:
            return SpecificityRelation.MORE_SPECIFIC

        if left_set == right_set:
            return SpecificityRelation.EQUIVALENT

        if left_set < right_set:
            return SpecificityRelation.MORE_SPECIFIC

        if right_set < left_set:
            return SpecificityRelation.LESS_SPECIFIC

        return SpecificityRelation.INCOMPARABLE

    @classmethod
    def compare_specificity(
        cls,
        left: HandlerSpec,
        right: HandlerSpec,
    ) -> SpecificityRelation:
        dimensions = (
            cls._compare_dimension(
                left.applicability.operations,
                right.applicability.operations,
            ),
            cls._compare_dimension(
                left.applicability.target_kinds,
                right.applicability.target_kinds,
            ),
            cls._compare_dimension(
                left.applicability.projects,
                right.applicability.projects,
            ),
            cls._compare_dimension(
                left.applicability.environments,
                right.applicability.environments,
            ),
        )

        has_more = any(
            relation is SpecificityRelation.MORE_SPECIFIC
            for relation in dimensions
        )

        has_less = any(
            relation is SpecificityRelation.LESS_SPECIFIC
            for relation in dimensions
        )

        has_incomparable = any(
            relation is SpecificityRelation.INCOMPARABLE
            for relation in dimensions
        )

        if has_incomparable:
            return SpecificityRelation.INCOMPARABLE

        if has_more and has_less:
            return SpecificityRelation.INCOMPARABLE

        if has_more:
            return SpecificityRelation.MORE_SPECIFIC

        if has_less:
            return SpecificityRelation.LESS_SPECIFIC

        return SpecificityRelation.EQUIVALENT

    @classmethod
    def _maximally_specific(
        cls,
        candidates: list[HandlerSpec],
    ) -> list[HandlerSpec]:
        maximal: list[HandlerSpec] = []

        for candidate in candidates:
            dominated = False

            for other in candidates:
                if candidate is other:
                    continue

                relation = cls.compare_specificity(
                    other,
                    candidate,
                )

                if relation is SpecificityRelation.MORE_SPECIFIC:
                    dominated = True
                    break

            if not dominated:
                maximal.append(candidate)

        return maximal

    def resolve(
        self,
        task: TaskV3,
        context: HandlerRuntimeContext | None = None,
    ) -> HandlerResolution:
        validation_error = self._validate_task(task)

        if validation_error is not None:
            return HandlerResolution(
                status=HandlerResolverStatus.INVALID,
                task=task,
                message=validation_error,
            )

        if context is None:
            context = HandlerRuntimeContext()

        context_error = self._validate_context(context)

        if context_error is not None:
            return HandlerResolution(
                status=HandlerResolverStatus.INVALID,
                task=task,
                message=context_error,
            )

        goal = task.intent.goal
        target = task.intent.target

        project = target.scope.project

        all_handlers = self._registry.list_for_goal(
            goal.identifier,
            goal.version,
        )

        if not all_handlers:
            return HandlerResolution(
                status=HandlerResolverStatus.NOT_FOUND,
                task=task,
                message=(
                    f"No handlers are registered for "
                    f"goal '{goal.identifier}@{goal.version}'."
                ),
            )

        active_handlers = [
            handler
            for handler in all_handlers
            if handler.status is not HandlerSpecStatus.DISABLED
        ]

        if not active_handlers:
            return HandlerResolution(
                status=HandlerResolverStatus.UNAVAILABLE,
                task=task,
                message=(
                    f"All handlers for "
                    f"'{goal.identifier}@{goal.version}' "
                    "are disabled."
                ),
            )

        compatible = [
            handler
            for handler in active_handlers
            if self._matches_applicability(
                handler.applicability,
                task.intent.operation,
                target.kind,
                project,
                context.environment,
            )
        ]

        if not compatible:
            return HandlerResolution(
                status=HandlerResolverStatus.UNAVAILABLE,
                task=task,
                candidates=tuple(active_handlers),
                message=(
                    f"No handler for "
                    f"'{goal.identifier}@{goal.version}' "
                    "matches task applicability."
                ),
            )

        capable = [
            handler
            for handler in compatible
            if self._has_capabilities(
                handler,
                context.capabilities,
            )
        ]

        if not capable:
            return HandlerResolution(
                status=HandlerResolverStatus.UNAVAILABLE,
                task=task,
                candidates=tuple(compatible),
                message=(
                    f"No compatible handler for "
                    f"'{goal.identifier}@{goal.version}' "
                    "has the required capabilities."
                ),
            )

        maximal = self._maximally_specific(capable)

        if len(maximal) == 1:
            return HandlerResolution(
                status=HandlerResolverStatus.FOUND,
                task=task,
                handler=maximal[0],
                candidates=tuple(maximal),
                message="",
            )

        # All remaining maximal candidates can be selected by stable ID
        # only when their applicability profiles are equivalent.
        for index, candidate in enumerate(maximal):
            for other in maximal[index + 1:]:
                relation = self.compare_specificity(
                    candidate,
                    other,
                )

                if relation is SpecificityRelation.INCOMPARABLE:
                    return HandlerResolution(
                        status=HandlerResolverStatus.AMBIGUOUS,
                        task=task,
                        candidates=tuple(maximal),
                        message=(
                            "Multiple incomparable handlers remain "
                            "after applicability and capability filtering."
                        ),
                    )

        maximal.sort(
            key=lambda handler: handler.handler_id
        )

        return HandlerResolution(
            status=HandlerResolverStatus.FOUND,
            task=task,
            handler=maximal[0],
            candidates=tuple(maximal),
            message="",
        )