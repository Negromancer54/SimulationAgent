from __future__ import annotations

from runtime.task_run import TaskPhase, V3TaskPhase


class TaskRunPhaseMapper:
    """
    Compatibility mapping from the legacy TaskPhase model
    to the normative V3 lifecycle model.

    This mapper is intentionally lossy where the legacy model
    has less resolution than V3.
    """

    @staticmethod
    def map_legacy_phase(
        phase: TaskPhase,
    ) -> V3TaskPhase | None:
        if not isinstance(phase, TaskPhase):
            raise TypeError(
                "TaskRunPhaseMapper requires a TaskPhase."
            )

        mapping = {
            TaskPhase.CREATED: V3TaskPhase.PRECHECK,
            TaskPhase.VALIDATING: V3TaskPhase.PRECHECK,
            TaskPhase.RESOLVING: V3TaskPhase.RESOLUTION,
            TaskPhase.PLANNING: V3TaskPhase.PLANNING,
            TaskPhase.CHECKING_PRECONDITIONS: V3TaskPhase.PRECHECK,
            TaskPhase.EXECUTING: V3TaskPhase.EXECUTION,
            TaskPhase.POST_EXECUTION: V3TaskPhase.POST_EXECUTION,
            TaskPhase.EVALUATING: None,
            TaskPhase.COMPLETED: V3TaskPhase.COMPLETE,
            TaskPhase.FAILED: V3TaskPhase.COMPLETE,
        }

        return mapping[phase]