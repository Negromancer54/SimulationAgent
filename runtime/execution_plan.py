from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from dataclasses import dataclass, field
from typing import Any
from agent_task_v3 import TaskV3
from registries.handler_registry import HandlerSpec
from registries.target_directory import TargetRecord
from registries.goal_registry import GoalSpec
from runtime.task_resolution import TaskResolutionResult


class PlanStatus(str, Enum):
    READY = "READY"
    INVALID_RESOLUTION = "INVALID_RESOLUTION"


@dataclass(frozen=True)
class ResourceRequirements:
    """
    Runtime-derived resource requirements.

    capabilities:
        Required runtime capabilities.

    resources:
        Required resource quantities.

        Mapping:
            resource_id -> required amount

        Resource amounts must be positive integers.
    """

    capabilities: tuple[str, ...] = ()
    resources: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.capabilities,
            tuple,
        ):
            raise TypeError(
                "ResourceRequirements.capabilities "
                "must be a tuple."
            )

        for capability in self.capabilities:
            if not isinstance(
                capability,
                str,
            ):
                raise TypeError(
                    "ResourceRequirements capabilities "
                    "must contain strings."
                )

        values = (
            self.resources
            if self.resources is not None
            else {}
        )

        if not isinstance(
            values,
            dict,
        ):
            raise TypeError(
                "ResourceRequirements.resources "
                "must be a dictionary or None."
            )

        for resource_id, value in values.items():
            if not isinstance(
                resource_id,
                str,
            ):
                raise TypeError(
                    "ResourceRequirements resource "
                    "identifiers must be strings."
                )

            if not resource_id:
                raise ValueError(
                    "ResourceRequirements resource "
                    "identifiers must not be empty."
                )

            if (
                not isinstance(
                    value,
                    int,
                )
                or isinstance(
                    value,
                    bool,
                )
                or value <= 0
            ):
                raise ValueError(
                    "ResourceRequirements resource "
                    "values must be positive integers."
                )

        object.__setattr__(
            self,
            "resources",
            dict(values),
        )


@dataclass(frozen=True)
class PlanStep:
    """
    Minimal executable step description.

    A step identifies what handler will act on what resolved target
    and for which resolved goal.
    """

    step_id: str
    handler_id: str
    target_kind: str
    target_identifier: str
    goal_identifier: str
    goal_version: int
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    resources: ResourceRequirements = ResourceRequirements()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "parameters",
            dict(self.parameters),
        )


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Runtime-derived execution plan.

    The plan is never accepted directly as TaskV3 input.
    """

    status: PlanStatus
    task: TaskV3
    steps: tuple[PlanStep, ...] = ()
    message: str = ""

    @property
    def ready(self) -> bool:
        return self.status is PlanStatus.READY


class ExecutionPlanner:
    """
    Builds a minimal ExecutionPlan from a resolved Task.

    Current responsibilities:
        - require successful Target/Goal/Handler resolution;
        - derive one deterministic PlanStep;
        - carry handler capability requirements into the plan.

    Current non-responsibilities:
        - precondition evaluation;
        - scheduling;
        - resource allocation;
        - dependency optimization;
        - retries;
        - execution;
        - rollback.
    """

    @staticmethod
    def _build_step(
        target: TargetRecord,
        goal: GoalSpec,
        handler: HandlerSpec,
        parameters: dict[str, Any],
    ) -> PlanStep:
        return PlanStep(
            step_id="step.1",
            handler_id=handler.handler_id,
            target_kind=target.kind.value,
            target_identifier=target.identifier,
            goal_identifier=goal.identifier,
            goal_version=goal.version,
            parameters=parameters,
            depends_on=(),
            resources=ResourceRequirements(
                capabilities=handler.required_capabilities,
            ),
        )

    def build(
        self,
        resolution: TaskResolutionResult,
    ) -> ExecutionPlan:
        if not resolution.resolved:
            return ExecutionPlan(
                status=PlanStatus.INVALID_RESOLUTION,
                task=resolution.task,
                message=(
                    "ExecutionPlan requires a successfully resolved task."
                ),
            )

        if resolution.target_record is None:
            return ExecutionPlan(
                status=PlanStatus.INVALID_RESOLUTION,
                task=resolution.task,
                message=(
                    "ExecutionPlan requires a resolved target record."
                ),
            )

        if resolution.goal_spec is None:
            return ExecutionPlan(
                status=PlanStatus.INVALID_RESOLUTION,
                task=resolution.task,
                message=(
                    "ExecutionPlan requires a resolved goal spec."
                ),
            )

        if resolution.handler_spec is None:
            return ExecutionPlan(
                status=PlanStatus.INVALID_RESOLUTION,
                task=resolution.task,
                message=(
                    "ExecutionPlan requires a resolved handler spec."
                ),
            )

        step = self._build_step(
            target=resolution.target_record,
            goal=resolution.goal_spec,
            handler=resolution.handler_spec,
            parameters=resolution.task.intent.goal.parameters,
        )

        return ExecutionPlan(
            status=PlanStatus.READY,
            task=resolution.task,
            steps=(step,),
            message="",
        )