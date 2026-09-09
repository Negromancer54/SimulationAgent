from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass

from runtime.execution_backend import (
    BackendBatchResult,
    BackendStepResult,
    ExecutionBackend,
    HandlerCallable,
)
from runtime.execution_types import ExecutionStatus
from runtime.execution_plan import PlanStep


class ParallelExecutionBackend(ExecutionBackend):
    """
    Physical parallel execution backend.

    Responsibilities:
        - execute all supplied steps concurrently;
        - preserve input step identity;
        - collect one BackendStepResult per step;
        - return results in input-step order.

    Non-responsibilities:
        - retry;
        - timeout;
        - scheduling dependencies;
        - resource allocation;
        - rollback.
    """

    def execute_batch(
        self,
        steps: tuple[PlanStep, ...],
        handlers: dict[str, HandlerCallable],
    ) -> BackendBatchResult:
        if not isinstance(
            steps,
            tuple,
        ):
            raise TypeError(
                "ParallelExecutionBackend requires "
                "a tuple of PlanStep objects."
            )

        if not isinstance(
            handlers,
            dict,
        ):
            raise TypeError(
                "ParallelExecutionBackend requires "
                "a handler dictionary."
            )

        if not steps:
            return BackendBatchResult(
                results=(),
                cancelled=False,
            )

        results_by_step: dict[str, BackendStepResult] = {}

        with ThreadPoolExecutor(
            max_workers=len(steps)
        ) as executor:
            futures = {}

            for step in steps:
                handler = handlers.get(
                    step.handler_id
                )

                if handler is None:
                    results_by_step[step.step_id] = (
                        BackendStepResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message=(
                                "No handler registered for "
                                f"handler id '{step.handler_id}'."
                            ),
                        )
                    )
                    continue

                futures[
                    executor.submit(
                        handler,
                        step,
                    )
                ] = step

            for future in as_completed(futures):
                step = futures[future]

                try:
                    future.result()

                except KeyboardInterrupt:
                    results_by_step[step.step_id] = (
                        BackendStepResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.CANCELLED,
                            message=(
                                "Execution was cancelled."
                            ),
                        )
                    )

                except Exception as exc:
                    results_by_step[step.step_id] = (
                        BackendStepResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.FAILED,
                            message=(
                                "Handler raised "
                                f"{type(exc).__name__}: {exc}"
                            ),
                        )
                    )

                else:
                    results_by_step[step.step_id] = (
                        BackendStepResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.SUCCEEDED,
                            message="",
                        )
                    )

        return BackendBatchResult(
            results=tuple(
                results_by_step[step.step_id]
                for step in steps
            ),
            cancelled=any(
                result.status is ExecutionStatus.CANCELLED
                for result in results_by_step.values()
            ),
        )