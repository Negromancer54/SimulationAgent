from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_task_v3 import (
    ExecutionPolicy,
    FailureMode,
    RollbackMode,
)


class ExecutionPolicyStatus(str, Enum):
    READY = "READY"
    INVALID = "INVALID"


@dataclass(frozen=True)
class RuntimeExecutionLimits:
    """
    Hard upper bounds imposed by the runtime.

    None means that the runtime does not impose a bound
    for that dimension at this layer.
    """

    timeout_seconds: int | None = None
    max_attempts: int | None = None
    max_workers: int | None = None


@dataclass(frozen=True)
class EffectiveExecutionPolicy:
    """
    Runtime-resolved execution policy.

    Values are already intersected with runtime limits.
    """

    timeout_seconds: int | None
    max_attempts: int
    max_workers: int

    failure_mode: FailureMode
    rollback_mode: RollbackMode


@dataclass(frozen=True)
class ExecutionPolicyResolution:
    status: ExecutionPolicyStatus
    policy: EffectiveExecutionPolicy | None = None
    message: str = ""

    @property
    def ready(self) -> bool:
        return self.status is ExecutionPolicyStatus.READY


class ExecutionPolicyResolver:
    """
    Resolves Task V3 ExecutionPolicy against hard runtime limits.

    The runtime can restrict a task policy, but never expand it.

    Current layer intentionally does not resolve:
        - handler-specific policy;
        - transaction limits;
        - resource scheduler state;
        - capability negotiation;
        - actual timeout enforcement;
        - retry execution;
        - parallel execution.
    """

    @staticmethod
    def _intersect_limit(
        requested: int | None,
        runtime_limit: int | None,
    ) -> int | None:
        if requested is None:
            return runtime_limit

        if runtime_limit is None:
            return requested

        return min(
            requested,
            runtime_limit,
        )

    @staticmethod
    def _validate_positive(
        value: int | None,
        field_name: str,
    ) -> str | None:
        if value is None:
            return None

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
        ):
            return (
                f"{field_name} must be a positive integer."
            )

        return None

    def resolve(
        self,
        task_policy: ExecutionPolicy | None,
        runtime_limits: RuntimeExecutionLimits,
    ) -> ExecutionPolicyResolution:
        if not isinstance(
            runtime_limits,
            RuntimeExecutionLimits,
        ):
            raise TypeError(
                "ExecutionPolicyResolver requires "
                "RuntimeExecutionLimits."
            )

        if task_policy is not None and not isinstance(
            task_policy,
            ExecutionPolicy,
        ):
            raise TypeError(
                "Task execution policy must be an "
                "ExecutionPolicy or None."
            )

        # ---------------------------------------------------------
        # No task policy:
        #
        # derive effective defaults from runtime limits.
        # ---------------------------------------------------------

        if task_policy is None:
            timeout_seconds = runtime_limits.timeout_seconds
            max_attempts = (
                runtime_limits.max_attempts
                if runtime_limits.max_attempts is not None
                else 1
            )
            max_workers = (
                runtime_limits.max_workers
                if runtime_limits.max_workers is not None
                else 1
            )

            return ExecutionPolicyResolution(
                status=ExecutionPolicyStatus.READY,
                policy=EffectiveExecutionPolicy(
                    timeout_seconds=timeout_seconds,
                    max_attempts=max_attempts,
                    max_workers=max_workers,
                    failure_mode=FailureMode.ABORT,
                    rollback_mode=RollbackMode.REQUIRED,
                ),
            )

        # ---------------------------------------------------------
        # Validate task values.
        # ---------------------------------------------------------

        checks = (
            (
                task_policy.timeout.total_seconds,
                "timeout.total_seconds",
            ),
            (
                task_policy.retry.max_attempts,
                "retry.max_attempts",
            ),
            (
                task_policy.parallelism.max_workers,
                "parallelism.max_workers",
            ),
        )

        for value, field_name in checks:
            error = self._validate_positive(
                value,
                field_name,
            )

            if error is not None:
                return ExecutionPolicyResolution(
                    status=ExecutionPolicyStatus.INVALID,
                    message=error,
                )

        # ---------------------------------------------------------
        # Intersect task policy with runtime hard limits.
        # ---------------------------------------------------------

        timeout_seconds = self._intersect_limit(
            task_policy.timeout.total_seconds,
            runtime_limits.timeout_seconds,
        )

        max_attempts = self._intersect_limit(
            task_policy.retry.max_attempts,
            runtime_limits.max_attempts,
        )

        max_workers = self._intersect_limit(
            task_policy.parallelism.max_workers,
            runtime_limits.max_workers,
        )

        # retry and parallelism always have concrete Task V3 defaults.
        if max_attempts is None:
            max_attempts = 1

        if max_workers is None:
            max_workers = 1

        # ---------------------------------------------------------
        # The intersection itself must never produce an invalid
        # positive-valued result.
        # ---------------------------------------------------------

        for value, field_name in (
            (
                timeout_seconds,
                "effective.timeout_seconds",
            ),
            (
                max_attempts,
                "effective.max_attempts",
            ),
            (
                max_workers,
                "effective.max_workers",
            ),
        ):
            error = self._validate_positive(
                value,
                field_name,
            )

            if error is not None:
                return ExecutionPolicyResolution(
                    status=ExecutionPolicyStatus.INVALID,
                    message=error,
                )

        return ExecutionPolicyResolution(
            status=ExecutionPolicyStatus.READY,
            policy=EffectiveExecutionPolicy(
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
                max_workers=max_workers,
                failure_mode=task_policy.failure.mode,
                rollback_mode=task_policy.rollback.mode,
            ),
        )