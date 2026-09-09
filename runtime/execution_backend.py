from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from runtime.execution_types import ExecutionStatus
from runtime.execution_plan import PlanStep


@dataclass(frozen=True)
class BackendStepResult:
    step_id: str
    status: ExecutionStatus
    message: str = ""


@dataclass(frozen=True)
class BackendBatchResult:
    results: tuple[BackendStepResult, ...]
    cancelled: bool = False


HandlerCallable = Callable[[PlanStep], None]


class ExecutionBackend:
    """
    Abstract physical execution backend.

    The backend executes one already-scheduled batch.

    Responsibilities:
        - invoke handlers;
        - return per-step execution results.

    Non-responsibilities:
        - task validation;
        - planning;
        - scheduling;
        - retry policy;
        - timeout policy;
        - rollback;
        - TaskOutcome.
    """

    def execute_batch(
        self,
        steps: tuple[PlanStep, ...],
        handlers: dict[str, HandlerCallable],
    ) -> BackendBatchResult:
        raise NotImplementedError


class SequentialBackend(ExecutionBackend):
    """
    Deterministic reference backend.

    Executes every step in batch order, sequentially.

    This is intentionally the first physical backend and serves as
    the behavioral reference for future concurrent implementations.
    """

    def execute_batch(
        self,
        steps: tuple[PlanStep, ...],
        handlers: dict[str, HandlerCallable],
    ) -> BackendBatchResult:
        results: list[BackendStepResult] = []

        for step in steps:
            handler = handlers.get(
                step.handler_id
            )

            if handler is None:
                results.append(
                    BackendStepResult(
                        step_id=step.step_id,
                        status=(
                            ExecutionStatus
                            .INFRASTRUCTURE_ERROR
                        ),
                        message=(
                            f"No runtime handler is available "
                            f"for '{step.handler_id}'."
                        ),
                    )
                )

                break

            try:
                handler(step)

            except KeyboardInterrupt:
                results.append(
                    BackendStepResult(
                        step_id=step.step_id,
                        status=(
                            ExecutionStatus.CANCELLED
                        ),
                        message="Execution was cancelled.",
                    )
                )

                return BackendBatchResult(
                    results=tuple(results),
                    cancelled=True,
                )

            except Exception as exc:
                results.append(
                    BackendStepResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.FAILED,
                        message=(
                            f"Handler raised "
                            f"{type(exc).__name__}: {exc}"
                        ),
                    )
                )

                break

            results.append(
                BackendStepResult(
                    step_id=step.step_id,
                    status=ExecutionStatus.SUCCEEDED,
                    message="",
                )
            )

        return BackendBatchResult(
            results=tuple(results),
            cancelled=False,
        )