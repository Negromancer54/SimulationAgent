from __future__ import annotations

from dataclasses import dataclass

from runtime.execution_backend import (
    BackendBatchResult,
    ExecutionBackend,
    HandlerCallable,
)
from runtime.execution_plan import PlanStep
from runtime.execution_types import ExecutionStatus
from typing import Callable

@dataclass(frozen=True)
class ParallelStepResult:
    step_id: str
    status: ExecutionStatus
    message: str = ""
    attempts: int = 1


@dataclass(frozen=True)
class ParallelBatchResult:
    results: tuple[ParallelStepResult, ...]


class ParallelBatchExecutor:
    """
    Executes one scheduler batch with per-step retry semantics.

    Responsibilities:
        - submit the current retryable set to the backend;
        - track attempts independently per step;
        - retry FAILED steps only;
        - never retry SUCCEEDED steps;
        - never retry CANCELLED steps;
        - never retry INFRASTRUCTURE_ERROR steps;
        - preserve deterministic input-step order in the final result.

    Non-responsibilities:
        - scheduling;
        - timeout;
        - resource admission;
        - preconditions;
        - rollback;
        - physical execution itself.
    """

    def __init__(
        self,
        backend: ExecutionBackend,
    ) -> None:
        if not isinstance(
            backend,
            ExecutionBackend,
        ):
            raise TypeError(
                "ParallelBatchExecutor requires "
                "an ExecutionBackend."
            )

        self._backend = backend

    def execute(
        self,
        steps: tuple[PlanStep, ...],
        handlers: dict[str, HandlerCallable],
        max_attempts: int,
        before_attempt: Callable[[], bool] | None = None,
    ) -> ParallelBatchResult:
        if not isinstance(
            steps,
            tuple,
        ):
            raise TypeError(
                "ParallelBatchExecutor requires "
                "a tuple of PlanStep objects."
            )

        if not isinstance(
            handlers,
            dict,
        ):
            raise TypeError(
                "ParallelBatchExecutor requires "
                "a handler dictionary."
            )

        if (
            not isinstance(
                max_attempts,
                int,
            )
            or isinstance(
                max_attempts,
                bool,
            )
            or max_attempts <= 0
        ):
            raise ValueError(
                "max_attempts must be a positive integer."
            )

        if not steps:
            return ParallelBatchResult(
                results=(),
            )

        attempts: dict[str, int] = {
            step.step_id: 0
            for step in steps
        }

        terminal_results: dict[
            str,
            ParallelStepResult,
        ] = {}

        pending: tuple[PlanStep, ...] = steps

        while pending:
            if before_attempt is not None:
                if not before_attempt():
                    for step in pending:
                        terminal_results[step.step_id] = (
                            ParallelStepResult(
                                step_id=step.step_id,
                                status=ExecutionStatus.CANCELLED,
                                message="Execution timeout reached.",
                                attempts=attempts[step.step_id],
                            )
                        )

                    break
            for step in pending:
                attempts[step.step_id] += 1

            try:
                backend_result = self._backend.execute_batch(
                    pending,
                    handlers,
                )
            except KeyboardInterrupt:
                for step in pending:
                    terminal_results[step.step_id] = (
                        ParallelStepResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.CANCELLED,
                            message="Execution was cancelled.",
                            attempts=attempts[step.step_id],
                        )
                    )

                break

            except Exception as exc:
                for step in pending:
                    terminal_results[step.step_id] = (
                        ParallelStepResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message=(
                                "Execution backend failed: "
                                f"{type(exc).__name__}: {exc}"
                            ),
                            attempts=attempts[step.step_id],
                        )
                    )

                break

            if not isinstance(
                backend_result,
                BackendBatchResult,
            ):
                raise TypeError(
                    "ExecutionBackend returned an invalid "
                    "batch result."
                )

            backend_results = backend_result.results

            expected_ids = tuple(
                step.step_id
                for step in pending
            )

            actual_ids = tuple(
                result.step_id
                for result in backend_results
            )

            if actual_ids != expected_ids:
                raise ValueError(
                    "ExecutionBackend returned results "
                    "that do not match the submitted batch."
                )

            next_pending: list[PlanStep] = []

            for step, backend_step in zip(
                pending,
                backend_results,
            ):
                step_attempts = attempts[
                    step.step_id
                ]

                if (
                    backend_step.status
                    is ExecutionStatus.SUCCEEDED
                ):
                    terminal_results[
                        step.step_id
                    ] = ParallelStepResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.SUCCEEDED,
                        message=backend_step.message,
                        attempts=step_attempts,
                    )
                    continue

                if (
                    backend_step.status
                    is ExecutionStatus.CANCELLED
                ):
                    terminal_results[
                        step.step_id
                    ] = ParallelStepResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.CANCELLED,
                        message=backend_step.message,
                        attempts=step_attempts,
                    )
                    continue

                if (
                    backend_step.status
                    is ExecutionStatus.INFRASTRUCTURE_ERROR
                ):
                    terminal_results[
                        step.step_id
                    ] = ParallelStepResult(
                        step_id=step.step_id,
                        status=(
                            ExecutionStatus
                            .INFRASTRUCTURE_ERROR
                        ),
                        message=backend_step.message,
                        attempts=step_attempts,
                    )
                    continue

                if (
                    backend_step.status
                    is ExecutionStatus.FAILED
                ):
                    if step_attempts < max_attempts:
                        next_pending.append(step)
                        continue

                    terminal_results[
                        step.step_id
                    ] = ParallelStepResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.FAILED,
                        message=backend_step.message,
                        attempts=step_attempts,
                    )
                    continue

                raise ValueError(
                    "ExecutionBackend returned an "
                    "unsupported execution status."
                )

            pending = tuple(next_pending)

        return ParallelBatchResult(
            results=tuple(
                terminal_results[step.step_id]
                for step in steps
            ),
        )