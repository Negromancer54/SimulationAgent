from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

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
        - enforce retry limits;
        - enforce timeout;
        - invoke the configured ExecutionBackend;
        - translate backend results into ExecutionResult;
        - preserve deterministic execution semantics.

    Current non-responsibilities:
        - Task validation;
        - target/goal/handler resolution;
        - planning;
        - physical concurrent execution policy;
        - resource allocation;
        - rollback.
    """

    def __init__(
        self,
        clock: Clock | None = None,
        scheduler: Scheduler | None = None,
        backend: ExecutionBackend | None = None,
        resource_admission: ResourceAdmission | None = None,
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

    def execute(
        self,
        plan: ExecutionPlan,
        preconditions: PreconditionsResult,
        handlers: dict[str, HandlerCallable],
        policy: EffectiveExecutionPolicy | None = None,
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

        for batch in schedule.batches:
            for step in batch.steps:
                if self._deadline_exceeded(
                    deadline
                ):
                    result = StepExecutionResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.CANCELLED,
                        message=(
                            "Execution timeout reached."
                        ),
                        attempts=0,
                    )

                    step_results.append(
                        result
                    )

                    return self._cancelled_result(
                        plan=plan,
                        completed_steps=completed_steps,
                        step_results=step_results,
                        step_id=step.step_id,
                        message=result.message,
                        policy=policy,
                        schedule=schedule,
                    )

                # -------------------------------------------------
                # Resource admission happens before the first
                # execution attempt.
                # -------------------------------------------------

                admission = self._resource_admission.check(
                    step.resources,
                    resource_policy,
                )

                if admission.status is ResourceAdmissionStatus.DENY:
                    result = StepExecutionResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.BLOCKED,
                        message=(
                            "Execution blocked by resource "
                            f"admission: {admission.message}"
                        ),
                        attempts=0,
                    )

                    step_results.append(
                        result
                    )

                    return self._blocked_result(
                        plan=plan,
                        message=result.message,
                        policy=policy,
                        schedule=schedule,
                        completed_steps=completed_steps,
                        step_results=step_results,
                        failed_step=step.step_id,
                    )

                if admission.status is ResourceAdmissionStatus.INVALID:
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

                    step_results.append(
                        result
                    )

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

                attempt_count = 0

                while attempt_count < max_attempts:
                    if self._deadline_exceeded(
                        deadline
                    ):
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.CANCELLED,
                            message=(
                                "Execution timeout reached."
                            ),
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

                        return self._cancelled_result(
                            plan=plan,
                            completed_steps=completed_steps,
                            step_results=step_results,
                            step_id=step.step_id,
                            message=result.message,
                            policy=policy,
                            schedule=schedule,
                        )

                    attempt_count += 1

                    try:
                        backend_result = (
                            self._backend.execute_batch(
                                (step,),
                                handlers,
                            )
                        )

                    except KeyboardInterrupt:
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.CANCELLED,
                            message=(
                                "Execution was cancelled."
                            ),
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

                        return self._cancelled_result(
                            plan=plan,
                            completed_steps=completed_steps,
                            step_results=step_results,
                            step_id=step.step_id,
                            message=result.message,
                            policy=policy,
                            schedule=schedule,
                        )

                    except Exception as exc:
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message=(
                                "Execution backend failed: "
                                f"{type(exc).__name__}: {exc}"
                            ),
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

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

                    if not hasattr(
                        backend_result,
                        "results",
                    ):
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message=(
                                "Execution backend returned "
                                "an invalid batch result."
                            ),
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

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

                    backend_results = (
                        backend_result.results
                    )

                    if len(backend_results) != 1:
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message=(
                                "Execution backend returned "
                                "an unexpected number of step results."
                            ),
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

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

                    backend_step = (
                        backend_results[0]
                    )

                    if backend_step.step_id != step.step_id:
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message=(
                                "Execution backend returned "
                                "a result for the wrong step."
                            ),
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

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

                    if (
                        not isinstance(
                            backend_step.status,
                            ExecutionStatus,
                        )
                    ):
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message=(
                                "Execution backend returned "
                                "an invalid step status."
                            ),
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

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

                    if self._deadline_exceeded(
                        deadline
                    ):
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.CANCELLED,
                            message=(
                                "Execution timeout reached."
                            ),
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

                        return self._cancelled_result(
                            plan=plan,
                            completed_steps=completed_steps,
                            step_results=step_results,
                            step_id=step.step_id,
                            message=result.message,
                            policy=policy,
                            schedule=schedule,
                        )

                    if (
                        backend_step.status
                        is ExecutionStatus.SUCCEEDED
                    ):
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.SUCCEEDED,
                            message=backend_step.message,
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

                        completed_steps.append(
                            step.step_id
                        )

                        break

                    if (
                        backend_step.status
                        is ExecutionStatus.CANCELLED
                    ):
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.CANCELLED,
                            message=backend_step.message,
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

                        return self._cancelled_result(
                            plan=plan,
                            completed_steps=completed_steps,
                            step_results=step_results,
                            step_id=step.step_id,
                            message=result.message,
                            policy=policy,
                            schedule=schedule,
                        )

                    if (
                        backend_step.status
                        is ExecutionStatus.INFRASTRUCTURE_ERROR
                    ):
                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message=backend_step.message,
                            attempts=0,
                        )

                        step_results.append(
                            result
                        )

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

                    if (
                        backend_step.status
                        is ExecutionStatus.FAILED
                    ):
                        if self._deadline_exceeded(
                            deadline
                        ):
                            result = StepExecutionResult(
                                step_id=step.step_id,
                                status=ExecutionStatus.CANCELLED,
                                message=(
                                    "Execution timeout reached."
                                ),
                                attempts=attempt_count,
                            )

                            step_results.append(
                                result
                            )

                            return self._cancelled_result(
                                plan=plan,
                                completed_steps=completed_steps,
                                step_results=step_results,
                                step_id=step.step_id,
                                message=result.message,
                                policy=policy,
                                schedule=schedule,
                            )

                        if attempt_count < max_attempts:
                            continue

                        result = StepExecutionResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.FAILED,
                            message=backend_step.message,
                            attempts=attempt_count,
                        )

                        step_results.append(
                            result
                        )

                        return self._failed_result(
                            plan=plan,
                            completed_steps=completed_steps,
                            step_results=step_results,
                            step_id=step.step_id,
                            message=result.message,
                            policy=policy,
                            schedule=schedule,
                        )

                    result = StepExecutionResult(
                        step_id=step.step_id,
                        status=(
                            ExecutionStatus
                            .INFRASTRUCTURE_ERROR
                        ),
                        message=(
                            "Execution backend returned "
                            "an unsupported execution status."
                        ),
                        attempts=attempt_count,
                    )

                    step_results.append(
                        result
                    )

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