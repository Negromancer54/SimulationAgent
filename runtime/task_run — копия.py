from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from agent_task_v3 import TaskV3
from runtime.evidence import EvidenceStore
from runtime.execution import ExecutionResult
from runtime.execution_plan import ExecutionPlan
from runtime.expected import ExpectedEvaluation
from runtime.task_outcome import TaskOutcome
from runtime.task_resolution import TaskResolutionResult
from runtime.validation import ValidationResult
from runtime.execution_policy import EffectiveExecutionPolicy

class TaskRunStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    RESOLVING = "RESOLVING"
    PLANNING = "PLANNING"
    CHECKING_PRECONDITIONS = "CHECKING_PRECONDITIONS"
    EXECUTING = "EXECUTING"
    POST_EXECUTION = "POST_EXECUTION"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskRunTransitionError(RuntimeError):
    pass


@dataclass
class TaskRun:
    """
    Mutable lifecycle container for one concrete execution attempt.

    The TaskV3 input remains immutable.
    Runtime products are accumulated as the run advances.
    """

    task: TaskV3
    status: TaskRunStatus = TaskRunStatus.CREATED

    resolution: TaskResolutionResult | None = None
    execution_plan: ExecutionPlan | None = None
    effective_execution_policy: EffectiveExecutionPolicy | None = None
    preconditions: object | None = None
    execution: ExecutionResult | None = None

    evidence: EvidenceStore | None = None
    expected_evaluations: tuple[ExpectedEvaluation, ...] = ()
    validation_results: tuple[ValidationResult, ...] = ()
    outcome: TaskOutcome | None = None

    history: list[TaskRunStatus] = field(
        default_factory=lambda: [TaskRunStatus.CREATED]
    )

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskV3):
            raise TypeError(
                "TaskRun requires a TaskV3 instance."
            )

        self.evidence = EvidenceStore(
            self.task.task_id
        )

    def transition(
        self,
        new_status: TaskRunStatus,
    ) -> None:
        if not isinstance(new_status, TaskRunStatus):
            raise TypeError(
                "TaskRun status must be a TaskRunStatus."
            )

        allowed = {
            TaskRunStatus.CREATED: {
                TaskRunStatus.VALIDATING,
                TaskRunStatus.FAILED,
            },
            TaskRunStatus.VALIDATING: {
                TaskRunStatus.RESOLVING,
                TaskRunStatus.FAILED,
            },
            TaskRunStatus.RESOLVING: {
                TaskRunStatus.PLANNING,
                TaskRunStatus.FAILED,
            },
            TaskRunStatus.PLANNING: {
                TaskRunStatus.CHECKING_PRECONDITIONS,
                TaskRunStatus.FAILED,
            },
            TaskRunStatus.CHECKING_PRECONDITIONS: {
                TaskRunStatus.EXECUTING,
                TaskRunStatus.FAILED,
            },
            TaskRunStatus.EXECUTING: {
                TaskRunStatus.POST_EXECUTION,
                TaskRunStatus.FAILED,
            },
            TaskRunStatus.POST_EXECUTION: {
                TaskRunStatus.EVALUATING,
                TaskRunStatus.FAILED,
            },
            TaskRunStatus.EVALUATING: {
                TaskRunStatus.COMPLETED,
                TaskRunStatus.FAILED,
            },
            TaskRunStatus.COMPLETED: set(),
            TaskRunStatus.FAILED: set(),
        }

        if (
            new_status
            not in allowed[self.status]
        ):
            raise TaskRunTransitionError(
                f"Invalid TaskRun transition: "
                f"{self.status.value} -> {new_status.value}"
            )

        self.status = new_status
        self.history.append(new_status)

    @property
    def terminal(self) -> bool:
        return self.status in {
            TaskRunStatus.COMPLETED,
            TaskRunStatus.FAILED,
        }

    @property
    def successful(self) -> bool:
        return (
            self.status is TaskRunStatus.COMPLETED
            and self.outcome is not None
            and self.outcome.succeeded
        )

    @property
    def task_id(self) -> str:
        return self.task.task_id