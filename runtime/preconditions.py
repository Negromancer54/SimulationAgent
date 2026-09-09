from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from agent_task_v3 import Precondition, TaskV3


class PreconditionScope(str, Enum):
    TASK = "TASK"
    GOAL = "GOAL"
    RUNTIME_SAFETY = "RUNTIME_SAFETY"


class PreconditionStatus(str, Enum):
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class PreconditionEvaluation:
    precondition_id: str
    scope: PreconditionScope
    status: PreconditionStatus
    message: str = ""

    @property
    def satisfied(self) -> bool:
        return self.status is PreconditionStatus.SATISFIED


@dataclass(frozen=True)
class PreconditionsResult:
    evaluations: tuple[PreconditionEvaluation, ...]
    message: str = ""

    @property
    def satisfied(self) -> bool:
        return all(
            evaluation.satisfied
            for evaluation in self.evaluations
        )

    @property
    def has_failed(self) -> bool:
        return any(
            evaluation.status is PreconditionStatus.FAILED
            for evaluation in self.evaluations
        )

    @property
    def has_unavailable(self) -> bool:
        return any(
            evaluation.status is PreconditionStatus.UNAVAILABLE
            for evaluation in self.evaluations
        )

    @property
    def has_error(self) -> bool:
        return any(
            evaluation.status is PreconditionStatus.ERROR
            for evaluation in self.evaluations
        )


@dataclass(frozen=True)
class PreconditionContext:
    """
    Runtime context available to precondition evaluators.

    The context itself does not evaluate anything.
    """

    task: TaskV3


PreconditionEvaluatorFunction = Callable[
    [Precondition, PreconditionContext],
    PreconditionStatus,
]


class PreconditionRegistry:
    """
    Runtime registry of atomic precondition evaluators.

    Key:
        (identifier, version)

    The registry stores executable evaluation functions.
    It does not store TaskV3 instances or execution plans.
    """

    def __init__(self) -> None:
        self._evaluators: dict[
            tuple[str, int],
            PreconditionEvaluatorFunction,
        ] = {}

    def register(
        self,
        identifier: str,
        version: int,
        evaluator: PreconditionEvaluatorFunction,
    ) -> None:
        if (
            not isinstance(identifier, str)
            or not identifier.strip()
        ):
            raise ValueError(
                "Precondition identifier must be a "
                "non-empty string."
            )

        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version <= 0
        ):
            raise ValueError(
                "Precondition version must be a "
                "positive integer."
            )

        if not callable(evaluator):
            raise ValueError(
                "Precondition evaluator must be callable."
            )

        key = (identifier, version)

        if key in self._evaluators:
            raise ValueError(
                "Precondition evaluator is already registered: "
                f"{identifier}@{version}"
            )

        self._evaluators[key] = evaluator

    def contains(
        self,
        identifier: str,
        version: int,
    ) -> bool:
        return (identifier, version) in self._evaluators

    def resolve(
        self,
        identifier: str,
        version: int,
    ) -> PreconditionEvaluatorFunction | None:
        return self._evaluators.get(
            (identifier, version)
        )


class PreconditionEvaluator:
    """
    Evaluates Task, Goal and Runtime Safety preconditions.

    Effective preconditions are an implicit logical AND.

    Execution must not begin unless every required
    precondition is SATISFIED.
    """

    def __init__(
        self,
        registry: PreconditionRegistry,
    ) -> None:
        self._registry = registry

    @staticmethod
    def _evaluate_one(
        precondition: Precondition,
        scope: PreconditionScope,
        context: PreconditionContext,
        evaluator: PreconditionEvaluatorFunction | None,
    ) -> PreconditionEvaluation:
        if evaluator is None:
            return PreconditionEvaluation(
                precondition_id=precondition.id,
                scope=scope,
                status=PreconditionStatus.UNAVAILABLE,
                message=(
                    f"Precondition '{precondition.identifier}"
                    f"@{precondition.version}' has no registered evaluator."
                ),
            )

        try:
            status = evaluator(
                precondition,
                context,
            )
        except Exception as exc:
            return PreconditionEvaluation(
                precondition_id=precondition.id,
                scope=scope,
                status=PreconditionStatus.ERROR,
                message=(
                    f"Precondition evaluator raised "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if not isinstance(status, PreconditionStatus):
            return PreconditionEvaluation(
                precondition_id=precondition.id,
                scope=scope,
                status=PreconditionStatus.ERROR,
                message=(
                    "Precondition evaluator returned an "
                    "invalid status."
                ),
            )

        return PreconditionEvaluation(
            precondition_id=precondition.id,
            scope=scope,
            status=status,
            message="",
        )

    def evaluate(
        self,
        task: TaskV3,
        goal_preconditions: tuple[Precondition, ...] = (),
        runtime_safety_preconditions: tuple[Precondition, ...] = (),
    ) -> PreconditionsResult:
        context = PreconditionContext(task=task)

        evaluations: list[PreconditionEvaluation] = []

        groups = (
            (
                PreconditionScope.TASK,
                tuple(task.preconditions),
            ),
            (
                PreconditionScope.GOAL,
                tuple(goal_preconditions),
            ),
            (
                PreconditionScope.RUNTIME_SAFETY,
                tuple(runtime_safety_preconditions),
            ),
        )

        for scope, preconditions in groups:
            for precondition in preconditions:
                evaluator = self._registry.resolve(
                    precondition.identifier,
                    precondition.version,
                )

                evaluations.append(
                    self._evaluate_one(
                        precondition,
                        scope,
                        context,
                        evaluator,
                    )
                )

        if not evaluations:
            return PreconditionsResult(
                evaluations=(),
                message="No preconditions were supplied.",
            )

        return PreconditionsResult(
            evaluations=tuple(evaluations),
            message="",
        )


def require_preconditions_satisfied(
    result: PreconditionsResult,
) -> None:
    """
    Guard for the transition into execution.

    Raises RuntimeError whenever the effective preconditions
    are not fully satisfied.
    """

    if result.satisfied:
        return

    if result.has_failed:
        raise RuntimeError(
            "Execution blocked: one or more preconditions FAILED."
        )

    if result.has_unavailable:
        raise RuntimeError(
            "Execution blocked: one or more preconditions "
            "are UNAVAILABLE."
        )

    if result.has_error:
        raise RuntimeError(
            "Execution blocked: one or more preconditions "
            "returned ERROR."
        )

    raise RuntimeError(
        "Execution blocked: effective preconditions "
        "are not satisfied."
    )