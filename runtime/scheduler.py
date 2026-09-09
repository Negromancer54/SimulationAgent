from __future__ import annotations

from dataclasses import dataclass

from runtime.execution_plan import PlanStep


@dataclass(frozen=True)
class ScheduledBatch:
    """
    One deterministic group of steps that may execute concurrently.

    The steps inside a batch are ordered by their position in the
    original ExecutionPlan.
    """

    steps: tuple[PlanStep, ...]


@dataclass(frozen=True)
class ExecutionSchedule:
    """
    Deterministic execution schedule.

    Batches must execute sequentially.
    Steps inside one batch are independent and may execute concurrently
    in a future physical backend.
    """

    batches: tuple[ScheduledBatch, ...]


class Scheduler:
    """
    Builds a deterministic schedule from PlanStep dependencies.

    Current implementation is deliberately backend-neutral:
        - no threads;
        - no futures;
        - no OS scheduling;
        - no actual concurrent execution.

    It only determines which steps are eligible to belong to the
    same concurrent batch.
    """

    def build(
        self,
        steps: tuple[PlanStep, ...],
        max_workers: int,
    ) -> ExecutionSchedule:
        if not isinstance(steps, tuple):
            raise TypeError(
                "Scheduler requires PlanStep tuple."
            )

        if (
            not isinstance(max_workers, int)
            or isinstance(max_workers, bool)
            or max_workers <= 0
        ):
            raise ValueError(
                "max_workers must be a positive integer."
            )

        remaining = list(steps)
        completed_ids: set[str] = set()
        batches: list[ScheduledBatch] = []

        while remaining:
            eligible: list[PlanStep] = []

            for step in remaining:
                if all(
                    dependency in completed_ids
                    for dependency in step.depends_on
                ):
                    eligible.append(step)

            if not eligible:
                raise ValueError(
                    "Execution plan contains an unresolved "
                    "or cyclic dependency."
                )

            batch_steps = tuple(
                eligible[:max_workers]
            )

            batches.append(
                ScheduledBatch(
                    steps=batch_steps
                )
            )

            batch_ids = {
                step.step_id
                for step in batch_steps
            }

            completed_ids.update(
                batch_ids
            )

            remaining = [
                step
                for step in remaining
                if step.step_id not in batch_ids
            ]

        return ExecutionSchedule(
            batches=tuple(batches)
        )