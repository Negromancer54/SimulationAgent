from __future__ import annotations

from dataclasses import dataclass

from runtime.execution import ExecutionStatus
from runtime.task_run import (
    TaskIntegrity,
    TaskStatus,
)


@dataclass(frozen=True)
class TaskRunStateMapping:
    """
    Result of mapping an ExecutionStatus into TaskRun state.

    The mapping deliberately does not contain a TaskPhase.
    Lifecycle phase remains controlled by TaskRun itself.
    """

    task_status: TaskStatus | None
    integrity: TaskIntegrity | None

    @property
    def changes_task_status(self) -> bool:
        return self.task_status is not None

    @property
    def changes_integrity(self) -> bool:
        return self.integrity is not None


class TaskRunStateMapper:
    """
    Maps ExecutionStatus into high-level TaskRun state.

    Execution status and TaskRun phase remain separate concepts.

    BLOCKED deliberately produces no automatic TaskStatus change.
    Integrity is also not inferred from ExecutionStatus alone.
    """

    @staticmethod
    def map(
        status: ExecutionStatus,
    ) -> TaskRunStateMapping:
        if not isinstance(
            status,
            ExecutionStatus,
        ):
            raise TypeError(
                "TaskRunStateMapper requires an "
                "ExecutionStatus."
            )

        if status is ExecutionStatus.SUCCEEDED:
            return TaskRunStateMapping(
                task_status=TaskStatus.SUCCEEDED,
                integrity=None,
            )

        if status is ExecutionStatus.FAILED:
            return TaskRunStateMapping(
                task_status=TaskStatus.FAILED,
                integrity=None,
            )

        if status is ExecutionStatus.INFRASTRUCTURE_ERROR:
            return TaskRunStateMapping(
                task_status=TaskStatus.FAILED,
                integrity=None,
            )

        if status is ExecutionStatus.CANCELLED:
            return TaskRunStateMapping(
                task_status=TaskStatus.CANCELLED,
                integrity=None,
            )

        if status is ExecutionStatus.BLOCKED:
            return TaskRunStateMapping(
                task_status=None,
                integrity=None,
            )

        raise ValueError(
            "Unsupported ExecutionStatus."
        )