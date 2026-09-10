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


class TaskStatus(str, Enum):
    """
    High-level result/state of the TaskRun.

    This is intentionally independent from TaskPhase and
    TaskIntegrity.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class FailureCode(str, Enum):
    TASK_INVALID = "TASK.INVALID"
    TASK_MISSING_FIELD = "TASK.MISSING_FIELD"

    RESOLUTION_UNKNOWN_GOAL = "RESOLUTION.UNKNOWN_GOAL"
    RESOLUTION_UNKNOWN_TARGET = "RESOLUTION.UNKNOWN_TARGET"
    RESOLUTION_HANDLER_UNAVAILABLE = "RESOLUTION.HANDLER_UNAVAILABLE"
    RESOLUTION_HANDLER_AMBIGUOUS = "RESOLUTION.HANDLER_AMBIGUOUS"

    PRECONDITION_FAILED = "PRECONDITION.FAILED"
    PRECONDITION_UNAVAILABLE = "PRECONDITION.UNAVAILABLE"
    PRECONDITION_ERROR = "PRECONDITION.ERROR"
    PRECONDITION_CONFLICT = "PRECONDITION.CONFLICT"

    PLANNING_FAILED = "PLANNING.FAILED"

    EXECUTION_FAILED = "EXECUTION.FAILED"
    EXECUTION_TIMEOUT = "EXECUTION.TIMEOUT"
    EXECUTION_CANCELLED = "EXECUTION.CANCELLED"
    EXECUTION_PROCESS_TERMINATION_FAILED = (
        "EXECUTION.PROCESS_TERMINATION_FAILED"
    )

    EXPECTED_NOT_SATISFIED = "EXPECTED.NOT_SATISFIED"
    EXPECTED_UNAVAILABLE = "EXPECTED.UNAVAILABLE"
    EXPECTED_ERROR = "EXPECTED.ERROR"

    VALIDATION_INVALID = "VALIDATION.INVALID"
    VALIDATION_INSUFFICIENT = "VALIDATION.INSUFFICIENT"
    VALIDATION_ERROR = "VALIDATION.ERROR"

    ROLLBACK_FAILED = "ROLLBACK.FAILED"

    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE.ERROR"


class Recoverability(str, Enum):
    NON_RECOVERABLE = "NON_RECOVERABLE"
    RETRYABLE = "RETRYABLE"
    USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
class TaskPhase(str, Enum):
    """
    Concrete lifecycle phase of the TaskRun.
    """

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
    
class V3TaskPhase(str, Enum):
    PRECHECK = "PRECHECK"
    RESOLUTION = "RESOLUTION"
    PLANNING = "PLANNING"
    CHECKPOINT = "CHECKPOINT"
    EXECUTION = "EXECUTION"
    POST_EXECUTION = "POST_EXECUTION"
    EXPECTED_EVALUATION = "EXPECTED_EVALUATION"
    VALIDATION = "VALIDATION"
    ROLLBACK = "ROLLBACK"
    COMPLETE = "COMPLETE"

class TaskIntegrity(str, Enum):
    """
    Internal consistency state of the TaskRun.

    Integrity is independent from task success or failure.
    """

    UNKNOWN = "UNKNOWN"
    VALID = "VALID"
    INVALID = "INVALID"
class V3TaskIntegrity(str, Enum):
    PRESERVED = "PRESERVED"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"

# Backward-compatible name.
TaskRunStatus = TaskPhase


class TaskRunTransitionError(RuntimeError):
    pass


@dataclass
class TaskRun:
    """
    Mutable lifecycle container for one concrete execution attempt.

    TaskStatus answers:
        What is the high-level state/result of this run?

    TaskPhase answers:
        Where is the run in its lifecycle?

    TaskIntegrity answers:
        Is the runtime state internally consistent?

    The TaskV3 input remains immutable.
    Runtime products are accumulated as the run advances.
    """

    task: TaskV3

    status: TaskPhase = TaskPhase.CREATED
    v3_phase: V3TaskPhase = V3TaskPhase.PRECHECK
    task_status: TaskStatus = TaskStatus.PENDING
    integrity: TaskIntegrity = TaskIntegrity.UNKNOWN

    failure_code: FailureCode | None = None
    recoverability: Recoverability | None = None
    v3_integrity: V3TaskIntegrity = V3TaskIntegrity.UNKNOWN

    resolution: TaskResolutionResult | None = None
    execution_plan: ExecutionPlan | None = None
    effective_execution_policy: EffectiveExecutionPolicy | None = None
    preconditions: object | None = None
    execution: ExecutionResult | None = None

    evidence: EvidenceStore | None = None
    expected_evaluations: tuple[ExpectedEvaluation, ...] = ()
    validation_results: tuple[ValidationResult, ...] = ()
    outcome: TaskOutcome | None = None

    history: list[TaskPhase] = field(
        default_factory=lambda: [TaskPhase.CREATED]
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.task,
            TaskV3,
        ):
            raise TypeError(
                "TaskRun requires a TaskV3 instance."
            )

        if not isinstance(
            self.status,
            TaskPhase,
        ):
            raise TypeError(
                "TaskRun status must be a TaskPhase."
            )

        if not isinstance(
            self.task_status,
            TaskStatus,
        ):
            raise TypeError(
                "TaskRun task_status must be a TaskStatus."
            )
        if not isinstance(
            self.v3_phase,
            V3TaskPhase,
        ):
            raise TypeError(
                "TaskRun v3_phase must be a V3TaskPhase."
            )

        if not isinstance(
            self.integrity,
            TaskIntegrity,
        ):
            raise TypeError(
                "TaskRun integrity must be a TaskIntegrity."
            )

        if self.failure_code is not None and not isinstance(
            self.failure_code,
            FailureCode,
        ):
            raise TypeError(
                "TaskRun failure_code must be a FailureCode or None."
            )

        if self.recoverability is not None and not isinstance(
            self.recoverability,
            Recoverability,
        ):
            raise TypeError(
                "TaskRun recoverability must be a Recoverability or None."
            )

        if not isinstance(
            self.v3_integrity,
            V3TaskIntegrity,
        ):
            raise TypeError(
                "TaskRun V3 integrity must be a V3TaskIntegrity."
            )
            raise TypeError(
                "TaskRun integrity must be a TaskIntegrity."
            )

        self.evidence = EvidenceStore(
            self.task.task_id
        )

    @property
    def phase(self) -> TaskPhase:
        return self.status
    def set_v3_phase(
        self,
        new_phase: V3TaskPhase,
    ) -> None:
        if not isinstance(
            new_phase,
            V3TaskPhase,
        ):
            raise TypeError(
                "TaskRun v3_phase must be a V3TaskPhase."
            )

        self.v3_phase = new_phase
    def set_task_status(
        self,
        new_status: TaskStatus,
    ) -> None:
        if not isinstance(
            new_status,
            TaskStatus,
        ):
            raise TypeError(
                "TaskRun task_status must be a TaskStatus."
            )

        self.task_status = new_status

    def set_integrity(
        self,
        new_integrity: TaskIntegrity,
    ) -> None:
        if not isinstance(
            new_integrity,
            TaskIntegrity,
        ):
            raise TypeError(
                "TaskRun integrity must be a TaskIntegrity."
            )

        self.integrity = new_integrity

    def cancel(self) -> None:
        """
        Mark the high-level task state as CANCELLED.

        Cancellation does not rewrite lifecycle history or phase.
        The phase describes where cancellation occurred.
        """

        if self.terminal:
            return

        self.task_status = TaskStatus.CANCELLED

    def transition(
        self,
        new_status: TaskPhase,
    ) -> None:
        if not isinstance(
            new_status,
            TaskPhase,
        ):
            raise TypeError(
                "TaskRun status must be a TaskPhase."
            )

        allowed = {
            TaskPhase.CREATED: {
                TaskPhase.VALIDATING,
                TaskPhase.FAILED,
            },
            TaskPhase.VALIDATING: {
                TaskPhase.RESOLVING,
                TaskPhase.FAILED,
            },
            TaskPhase.RESOLVING: {
                TaskPhase.PLANNING,
                TaskPhase.FAILED,
            },
            TaskPhase.PLANNING: {
                TaskPhase.CHECKING_PRECONDITIONS,
                TaskPhase.FAILED,
            },
            TaskPhase.CHECKING_PRECONDITIONS: {
                TaskPhase.EXECUTING,
                TaskPhase.FAILED,
            },
            TaskPhase.EXECUTING: {
                TaskPhase.POST_EXECUTION,
                TaskPhase.FAILED,
            },
            TaskPhase.POST_EXECUTION: {
                TaskPhase.EVALUATING,
                TaskPhase.FAILED,
            },
            TaskPhase.EVALUATING: {
                TaskPhase.COMPLETED,
                TaskPhase.FAILED,
            },
            TaskPhase.COMPLETED: set(),
            TaskPhase.FAILED: set(),
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

        if (
            new_status is not TaskPhase.CREATED
            and new_status not in {
                TaskPhase.COMPLETED,
                TaskPhase.FAILED,
            }
            and self.task_status is TaskStatus.PENDING
        ):
            self.task_status = TaskStatus.RUNNING

        if new_status is TaskPhase.FAILED:
            if self.task_status is not TaskStatus.CANCELLED:
                self.task_status = TaskStatus.FAILED

        if new_status is TaskPhase.COMPLETED:
            if self.task_status is not TaskStatus.CANCELLED:
                if (
                    self.outcome is not None
                    and self.outcome.succeeded
                ):
                    self.task_status = TaskStatus.SUCCEEDED
                else:
                    self.task_status = TaskStatus.FAILED
    @property
    def v3_lifecycle_phase(self) -> V3TaskPhase:
        return self.v3_phase
    @property
    def terminal(self) -> bool:
        return (
            self.status
            in {
                TaskPhase.COMPLETED,
                TaskPhase.FAILED,
            }
            or self.task_status
            in {
                TaskStatus.SUCCEEDED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }
        )

    @property
    def successful(self) -> bool:
        return (
            self.task_status is TaskStatus.SUCCEEDED
            and self.outcome is not None
            and self.outcome.succeeded
        )

    @property
    def task_id(self) -> str:
        return self.task.task_id
    def set_failure(
        self,
        failure_code: FailureCode,
        recoverability: Recoverability | None = None,
    ) -> None:
        if not isinstance(failure_code, FailureCode):
            raise TypeError(
                "TaskRun failure_code must be a FailureCode."
            )

        if recoverability is not None and not isinstance(
            recoverability,
            Recoverability,
        ):
            raise TypeError(
                "TaskRun recoverability must be a Recoverability or None."
            )

        self.failure_code = failure_code
        self.recoverability = recoverability


    def set_v3_integrity(
        self,
        new_integrity: V3TaskIntegrity,
    ) -> None:
        if not isinstance(new_integrity, V3TaskIntegrity):
            raise TypeError(
                "TaskRun V3 integrity must be a V3TaskIntegrity."
            )

        self.v3_integrity = new_integrity