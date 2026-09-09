from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from runtime.cancellation import CancellationToken
from runtime.clock import Clock, MonotonicClock
from runtime.execution_backend import (
    ExecutionBackend,
    SequentialBackend,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
    PlanStep,
)
from runtime.execution_policy import (
    EffectiveExecutionPolicy,
    ResourcePolicy,
)
from runtime.execution_types import ExecutionStatus
from runtime.preconditions import (
    PreconditionsResult,
)
from runtime.resource_admission import (
    ResourceAdmission,
    ResourceAdmissionStatus,
)
from runtime.scheduler import (
    ExecutionSchedule,
    Scheduler,
)
from runtime.parallel_batch_executor import (
    ParallelBatchExecutor,
    ParallelBatchResult,
)


@dataclass(frozen=True)
class StepExecutionResult:
    step_id: str
    status: ExecutionStatus
    message: str = ""
    attempts: int = 1


@dataclass(frozen=True)
class ExecutionResult:
    plan: ExecutionPlan
    status: ExecutionStatus
    completed_steps: tuple[str, ...] = ()
    failed_step: str | None = None
    step_results: tuple[StepExecutionResult, ...] = ()
    message: str = ""
    policy: EffectiveExecutionPolicy | None = None
    schedule: ExecutionSchedule | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is ExecutionStatus.SUCCEEDED


HandlerCallable = Callable[[PlanStep], None]


class ExecutionRuntime:
    """
    Deterministic execution runtime with pluggable physical backend.

    Responsibilities:
        - require a READY ExecutionPlan;
        - require satisfied preconditions;
        - derive an ExecutionSchedule;
        - enforce resource admission;
        - enforce timeout;
        - enforce external cancellation;
        - coordinate batch execution;
        - preserve deterministic execution semantics.

    Retry semantics are delegated to ParallelBatchExecutor.

    Current non-responsibilities:
        - Task validation;
        - target/goal/handler resolution;
        - planning;
        - physical concurrent execution;
        - resource allocation;
        - rollback.
    """

    def __init__(
        self,
        clock: Clock | None = None,
        scheduler: Scheduler | None = None,
        backend: ExecutionBackend | None = None,
        resource_admission: ResourceAdmission | None = None,
        batch_executor: ParallelBatchExecutor | None = None,
    ) -> None:
        self._clock = (
            clock
            if clock is not None
            else MonotonicClock()
        )

        self._scheduler = (
            scheduler
            if scheduler is not None
            else Scheduler()
        )

        self._backend = (
            backend
            if backend is not None
            else SequentialBackend()
        )

        self._resource_admission = (
            resource_admission
            if resource_admission is not None
            else ResourceAdmission()
        )

        self._batch_executor = (
            batch_executor
            if batch_executor is not None
            else ParallelBatchExecutor(
                self._backend
            )
        )

    @staticmethod
    def _blocked_result(
        plan: ExecutionPlan,
        message: str,
        policy: EffectiveExecutionPolicy | None = None,
        schedule: ExecutionSchedule | None = None,
        completed_steps: list[str] | None = None,
        step_results: list[StepExecutionResult] | None = None,
        failed_step: str | None = None,
    ) -> ExecutionResult:
        return ExecutionResult(
            plan=plan,
            status=ExecutionStatus.BLOCKED,
            completed_steps=tuple(
                completed_steps
                if completed_steps is not None
                else ()
            ),
            failed_step=failed_step,
            step_results=tuple(
                step_results
                if step_results is not None
                else ()
            ),
            message=message,
            policy=policy,
            schedule=schedule,
        )

    @staticmethod
    def _invalid_plan_result(
        plan: ExecutionPlan,
        message: str,
        policy: EffectiveExecutionPolicy | None = None,
    ) -> ExecutionResult:
        return ExecutionResult(
            plan=plan,
            status=ExecutionStatus.INFRASTRUCTURE_ERROR,
            message=message,
            policy=policy,
            schedule=None,
        )

    @staticmethod
    def _infrastructure_error_result(
        plan: ExecutionPlan,
        completed_steps: list[str],
        step_results: list[StepExecutionResult],
        step_id: str,
        message: str,
        policy: EffectiveExecutionPolicy | None,
        schedule: ExecutionSchedule,
    ) -> ExecutionResult:
        return ExecutionResult(
            plan=plan,
            status=ExecutionStatus.INFRASTRUCTURE_ERROR,
            completed_steps=tuple(
                completed_steps
            ),
            failed_step=step_id,
            step_results=tuple(
                step_results
            ),
            message=message,
            policy=policy,
            schedule=schedule,
        )

    @staticmethod
    def _failed_result(
        plan: ExecutionPlan,
        completed_steps: list[str],
        step_results: list[StepExecutionResult],
        step_id: str,
        message: str,
        policy: EffectiveExecutionPolicy | None,
        schedule: ExecutionSchedule,
    ) -> ExecutionResult:
        return ExecutionResult(
            plan=plan,
            status=ExecutionStatus.FAILED,
            completed_steps=tuple(
                completed_steps
            ),
            failed_step=step_id,
            step_results=tuple(
                step_results
            ),
            message=message,
            policy=policy,
            schedule=schedule,
        )

    @staticmethod
    def _cancelled_result(
        plan: ExecutionPlan,
        completed_steps: list[str],
        step_results: list[StepExecutionResult],
        step_id: str,
        message: str,
        policy: EffectiveExecutionPolicy | None,
        schedule: ExecutionSchedule,
    ) -> ExecutionResult:
        return ExecutionResult(
            plan=plan,
            status=ExecutionStatus.CANCELLED,
            completed_steps=tuple(
                completed_steps
            ),
            failed_step=step_id,
            step_results=tuple(
                step_results
            ),
            message=message,
            policy=policy,
            schedule=schedule,
        )

    def _deadline_exceeded(
        self,
        deadline: float | None,
    ) -> bool:
        if deadline is None:
            return False

        return self._clock.monotonic() >= deadline

    @staticmethod
    def _convert_batch_result(
        result: ParallelBatchResult,
    ) -> list[StepExecutionResult]:
        converted: list[StepExecutionResult] = []

        for item in result.results:
            attempts = item.attempts

            if (
                item.status
                is ExecutionStatus.INFRASTRUCTURE_ERROR
            ):
                attempts = 0

            converted.append(
                StepExecutionResult(
                    step_id=item.step_id,
                    status=item.status,
                    message=item.message,
                    attempts=attempts,
                )
            )

        return converted

    def execute(
        self,
        plan: ExecutionPlan,
        preconditions: PreconditionsResult,
        handlers: dict[str, HandlerCallable],
        policy: EffectiveExecutionPolicy | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ExecutionResult:
        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "ExecutionRuntime requires an ExecutionPlan."
            )

        if not isinstance(
            preconditions,
            PreconditionsResult,
        ):
            raise TypeError(
                "ExecutionRuntime requires a "
                "PreconditionsResult."
            )

        if not isinstance(
            handlers,
            dict,
        ):
            raise TypeError(
                "ExecutionRuntime requires a "
                "handler dictionary."
            )

        if (
            policy is not None
            and not isinstance(
                policy,
                EffectiveExecutionPolicy,
            )
        ):
            raise TypeError(
                "ExecutionRuntime requires an "
                "EffectiveExecutionPolicy or None."
            )

        if (
            cancellation_token is not None
            and not isinstance(
                cancellation_token,
                CancellationToken,
            )
        ):
            raise TypeError(
                "ExecutionRuntime requires a "
                "CancellationToken or None."
            )

        if not isinstance(
            self._backend,
            ExecutionBackend,
        ):
            raise TypeError(
                "ExecutionRuntime requires an "
                "ExecutionBackend."
            )

        if not isinstance(
            self._resource_admission,
            ResourceAdmission,
        ):
            raise TypeError(
                "ExecutionRuntime requires a "
                "ResourceAdmission."
            )

        if not isinstance(
            self._batch_executor,
            ParallelBatchExecutor,
        ):
            raise TypeError(
                "ExecutionRuntime requires a "
                "ParallelBatchExecutor."
            )

        max_attempts = (
            policy.max_attempts
            if policy is not None
            else 1
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
                "EffectiveExecutionPolicy.max_attempts "
                "must be a positive integer."
            )

        max_workers = (
            policy.max_workers
            if policy is not None
            else 1
        )

        if (
            not isinstance(
                max_workers,
                int,
            )
            or isinstance(
                max_workers,
                bool,
            )
            or max_workers <= 0
        ):
            raise ValueError(
                "EffectiveExecutionPolicy.max_workers "
                "must be a positive integer."
            )

        if plan.status is not PlanStatus.READY:
            return self._invalid_plan_result(
                plan,
                "Execution requires a READY "
                "ExecutionPlan.",
                policy,
            )

        if not preconditions.satisfied:
            return self._blocked_result(
                plan,
                "Execution blocked by unsatisfied "
                "preconditions.",
                policy,
            )

        timeout_seconds = (
            policy.timeout_seconds
            if policy is not None
            else None
        )

        if (
            timeout_seconds is not None
            and (
                not isinstance(
                    timeout_seconds,
                    int,
                )
                or isinstance(
                    timeout_seconds,
                    bool,
                )
                or timeout_seconds <= 0
            )
        ):
            raise ValueError(
                "EffectiveExecutionPolicy.timeout_seconds "
                "must be a positive integer or None."
            )

        start_time = self._clock.monotonic()

        deadline = (
            start_time + timeout_seconds
            if timeout_seconds is not None
            else None
        )

        completed_steps: list[str] = []
        step_results: list[StepExecutionResult] = []

        schedule = self._scheduler.build(
            plan.steps,
            max_workers=max_workers,
        )

        resource_policy = (
            policy.resources
            if policy is not None
            else ResourcePolicy(
                values={}
            )
        )

        def cancellation_requested() -> bool:
            if cancellation_token is None:
                return False

            return cancellation_token.requested

        def execution_cancelled() -> bool:
            return (
                cancellation_requested()
                or self._deadline_exceeded(
                    deadline
                )
            )

        for batch in schedule.batches:
            batch_steps = batch.steps

            # -----------------------------------------------------
            # Cancellation / timeout before the batch starts.
            # -----------------------------------------------------

            if execution_cancelled():
                first_step = batch_steps[0]

                message = (
                    "Execution cancellation requested."
                    if cancellation_requested()
                    else "Execution timeout reached."
                )

                result = StepExecutionResult(
                    step_id=first_step.step_id,
                    status=ExecutionStatus.CANCELLED,
                    message=message,
                    attempts=0,
                )

                step_results.append(result)

                return self._cancelled_result(
                    plan=plan,
                    completed_steps=completed_steps,
                    step_results=step_results,
                    step_id=first_step.step_id,
                    message=result.message,
                    policy=policy,
                    schedule=schedule,
                )

            # -----------------------------------------------------
            # Resource admission for the complete batch.
            # -----------------------------------------------------

            for step in batch_steps:
                admission = self._resource_admission.check(
                    step.resources,
                    resource_policy,
                )

                if admission.status is (
                    ResourceAdmissionStatus.DENY
                ):
                    result = StepExecutionResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.BLOCKED,
                        message=(
                            "Execution blocked by resource "
                            f"admission: {admission.message}"
                        ),
                        attempts=0,
                    )

                    step_results.append(result)

                    return self._blocked_result(
                        plan=plan,
                        message=result.message,
                        policy=policy,
                        schedule=schedule,
                        completed_steps=completed_steps,
                        step_results=step_results,
                        failed_step=step.step_id,
                    )

                if admission.status is (
                    ResourceAdmissionStatus.INVALID
                ):
                    result = StepExecutionResult(
                        step_id=step.step_id,
                        status=(
                            ExecutionStatus
                            .INFRASTRUCTURE_ERROR
                        ),
                        message=(
                            "Resource admission returned "
                            "an invalid result."
                        ),
                        attempts=0,
                    )

                    step_results.append(result)

                    return (
                        self._infrastructure_error_result(
                            plan=plan,
                            completed_steps=completed_steps,
                            step_results=step_results,
                            step_id=step.step_id,
                            message=result.message,
                            policy=policy,
                            schedule=schedule,
                        )
                    )

            # -----------------------------------------------------
            # Physical batch execution + per-step retry.
            #
            # Timeout and external cancellation are checked before
            # every attempt by ParallelBatchExecutor.
            # -----------------------------------------------------

            try:
                batch_result = (
                    self._batch_executor.execute(
                        batch_steps,
                        handlers,
                        max_attempts=max_attempts,
                        before_attempt=(
                            lambda: not execution_cancelled()
                        ),
                    )
                )

            except KeyboardInterrupt:
                first_step = batch_steps[0]

                result = StepExecutionResult(
                    step_id=first_step.step_id,
                    status=ExecutionStatus.CANCELLED,
                    message="Execution was cancelled.",
                    attempts=1,
                )

                step_results.append(result)

                return self._cancelled_result(
                    plan=plan,
                    completed_steps=completed_steps,
                    step_results=step_results,
                    step_id=first_step.step_id,
                    message=result.message,
                    policy=policy,
                    schedule=schedule,
                )

            except Exception as exc:
                first_step = batch_steps[0]

                result = StepExecutionResult(
                    step_id=first_step.step_id,
                    status=(
                        ExecutionStatus
                        .INFRASTRUCTURE_ERROR
                    ),
                    message=(
                        "Parallel batch execution failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    attempts=0,
                )

                step_results.append(result)

                return (
                    self._infrastructure_error_result(
                        plan=plan,
                        completed_steps=completed_steps,
                        step_results=step_results,
                        step_id=first_step.step_id,
                        message=result.message,
                        policy=policy,
                        schedule=schedule,
                    )
                )

            converted_results = (
                self._convert_batch_result(
                    batch_result
                )
            )

            step_results.extend(
                converted_results
            )

            # -----------------------------------------------------
            # Record successful work BEFORE cancellation/timeout
            # handling. Work that physically completed successfully
            # remains completed even when the overall run is then
            # cancelled.
            # -----------------------------------------------------

            batch_successes = [
                item.step_id
                for item in converted_results
                if item.status is ExecutionStatus.SUCCEEDED
            ]

            for step_id in batch_successes:
                completed_steps.append(step_id)

            # -----------------------------------------------------
            # Timeout after physical batch completion.
            # -----------------------------------------------------

            if self._deadline_exceeded(
                deadline
            ):
                first_non_success = next(
                    (
                        item
                        for item in converted_results
                        if item.status is not (
                            ExecutionStatus.SUCCEEDED
                        )
                    ),
                    None,
                )

                timeout_step = (
                    first_non_success
                    if first_non_success is not None
                    else converted_results[0]
                )

                return self._cancelled_result(
                    plan=plan,
                    completed_steps=completed_steps,
                    step_results=step_results,
                    step_id=timeout_step.step_id,
                    message="Execution timeout reached.",
                    policy=policy,
                    schedule=schedule,
                )

            # -----------------------------------------------------
            # External cancellation after batch completion.
            #
            # Already completed work remains completed.
            # Cancellation prevents further execution.
            # -----------------------------------------------------

            if cancellation_requested():
                first_non_success = next(
                    (
                        item
                        for item in converted_results
                        if item.status is not (
                            ExecutionStatus.SUCCEEDED
                        )
                    ),
                    None,
                )

                cancellation_step = (
                    first_non_success
                    if first_non_success is not None
                    else converted_results[0]
                )

                return self._cancelled_result(
                    plan=plan,
                    completed_steps=completed_steps,
                    step_results=step_results,
                    step_id=cancellation_step.step_id,
                    message=(
                        "Execution cancellation requested."
                    ),
                    policy=policy,
                    schedule=schedule,
                )

            # -----------------------------------------------------
            # Resolve deterministic batch result.
            # -----------------------------------------------------

            first_failure = next(
                (
                    item
                    for item in converted_results
                    if item.status is ExecutionStatus.FAILED
                ),
                None,
            )

            first_infrastructure_error = next(
                (
                    item
                    for item in converted_results
                    if (
                        item.status
                        is ExecutionStatus.INFRASTRUCTURE_ERROR
                    )
                ),
                None,
            )

            first_cancelled = next(
                (
                    item
                    for item in converted_results
                    if item.status is ExecutionStatus.CANCELLED
                ),
                None,
            )

            if first_infrastructure_error is not None:
                return self._infrastructure_error_result(
                    plan=plan,
                    completed_steps=completed_steps,
                    step_results=step_results,
                    step_id=first_infrastructure_error.step_id,
                    message=first_infrastructure_error.message,
                    policy=policy,
                    schedule=schedule,
                )

            if first_cancelled is not None:
                return self._cancelled_result(
                    plan=plan,
                    completed_steps=completed_steps,
                    step_results=step_results,
                    step_id=first_cancelled.step_id,
                    message=first_cancelled.message,
                    policy=policy,
                    schedule=schedule,
                )

            if first_failure is not None:
                return self._failed_result(
                    plan=plan,
                    completed_steps=completed_steps,
                    step_results=step_results,
                    step_id=first_failure.step_id,
                    message=first_failure.message,
                    policy=policy,
                    schedule=schedule,
                )

        return ExecutionResult(
            plan=plan,
            status=ExecutionStatus.SUCCEEDED,
            completed_steps=tuple(
                completed_steps
            ),
            step_results=tuple(
                step_results
            ),
            message="",
            policy=policy,
            schedule=schedule,
        )