from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from agent_task_v3 import (
    ExecutionPolicy,
    FailureMode,
    RollbackMode,
)


class ExecutionPolicyStatus(str, Enum):
    READY = "READY"
    INVALID = "INVALID"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class ResourcePolicy:
    """
    Declarative resource limits for execution.

    The mapping is:
        resource_id -> positive integer limit

    ResourcePolicy does not allocate resources. It only represents
    limits established by the current execution context.
    """

    values: dict[str, int]

    def __post_init__(self) -> None:
        if not isinstance(self.values, dict):
            raise TypeError(
                "ResourcePolicy.values must be a dictionary."
            )

        for resource_id, value in self.values.items():
            if not isinstance(resource_id, str):
                raise TypeError(
                    "ResourcePolicy resource identifiers "
                    "must be strings."
                )

            if not resource_id:
                raise ValueError(
                    "ResourcePolicy resource identifiers "
                    "must not be empty."
                )

            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value <= 0
            ):
                raise ValueError(
                    "ResourcePolicy resource limits "
                    "must be positive integers."
                )


@dataclass(frozen=True)
class ExecutionPolicyConstraint:
    """
    Optional constraints contributed by a runtime owner.

    None means that this source does not constrain the
    corresponding dimension.
    """

    timeout_seconds: int | None = None
    max_attempts: int | None = None
    max_workers: int | None = None

    resources: ResourcePolicy | None = None

    failure_mode: FailureMode | None = None
    rollback_mode: RollbackMode | None = None

    def __post_init__(self) -> None:
        checks = (
            (
                self.timeout_seconds,
                "timeout_seconds",
            ),
            (
                self.max_attempts,
                "max_attempts",
            ),
            (
                self.max_workers,
                "max_workers",
            ),
        )

        for value, field_name in checks:
            if value is None:
                continue

            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value <= 0
            ):
                raise ValueError(
                    f"{field_name} must be a positive integer "
                    "or None."
                )

        if self.resources is not None:
            if not isinstance(
                self.resources,
                ResourcePolicy,
            ):
                raise TypeError(
                    "resources must be a ResourcePolicy or None."
                )

            ResourcePolicy(
                values=dict(self.resources.values)
            )

        if (
            self.failure_mode is not None
            and not isinstance(
                self.failure_mode,
                FailureMode,
            )
        ):
            raise TypeError(
                "failure_mode must be a FailureMode or None."
            )

        if (
            self.rollback_mode is not None
            and not isinstance(
                self.rollback_mode,
                RollbackMode,
            )
        ):
            raise TypeError(
                "rollback_mode must be a RollbackMode or None."
            )


@dataclass(frozen=True)
class HandlerExecutionPolicy(
    ExecutionPolicyConstraint
):
    """
    Execution-policy constraints declared by a handler.
    """

    pass


@dataclass(frozen=True)
class TransactionExecutionPolicy(
    ExecutionPolicyConstraint
):
    """
    Execution-policy constraints imposed by a transaction.
    """

    pass


@dataclass(frozen=True)
class RuntimeExecutionLimits:
    """
    Hard runtime limits.

    None means that the runtime does not impose a bound
    for that dimension at this layer.
    """

    timeout_seconds: int | None = None
    max_attempts: int | None = None
    max_workers: int | None = None

    resources: ResourcePolicy | None = None

    failure_mode: FailureMode | None = None
    rollback_mode: RollbackMode | None = None


@dataclass(frozen=True)
class EffectiveExecutionPolicy:
    """
    Fully resolved execution policy.

    All supplied numeric/resource constraints have been
    intersected. Semantic modes have been checked for
    compatibility.
    """

    timeout_seconds: int | None
    max_attempts: int
    max_workers: int

    failure_mode: FailureMode
    rollback_mode: RollbackMode

    resources: ResourcePolicy = field(
        default_factory=lambda: ResourcePolicy(
            values={}
        )
    )


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
    Resolves execution policy across four sources:

        - Task policy;
        - Handler policy;
        - Runtime limits;
        - Transaction policy.

    Numeric limits and resource limits are intersected.

    Failure and rollback modes must be compatible. If more
    than one source explicitly specifies different modes,
    resolution returns CONFLICT.

    This class does not execute, schedule, allocate, retry,
    rollback, or negotiate capabilities.
    """

    @staticmethod
    def _intersect_limit(
        current: int | None,
        constraint: int | None,
    ) -> int | None:
        if constraint is None:
            return current

        if current is None:
            return constraint

        return min(
            current,
            constraint,
        )

    @staticmethod
    def _intersect_resources(
        current: ResourcePolicy | None,
        constraint: ResourcePolicy | None,
    ) -> ResourcePolicy:
        if current is None and constraint is None:
            return ResourcePolicy(values={})

        if current is None:
            return ResourcePolicy(
                values=dict(constraint.values)
            )

        if constraint is None:
            return ResourcePolicy(
                values=dict(current.values)
            )

        result: dict[str, int] = {}

        resource_ids = (
            set(current.values)
            | set(constraint.values)
        )

        for resource_id in resource_ids:
            current_value = current.values.get(
                resource_id
            )

            constraint_value = constraint.values.get(
                resource_id
            )

            if current_value is None:
                result[resource_id] = constraint_value
                continue

            if constraint_value is None:
                result[resource_id] = current_value
                continue

            result[resource_id] = min(
                current_value,
                constraint_value,
            )

        return ResourcePolicy(
            values=result
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

    @staticmethod
    def _validate_resources(
        policy: ResourcePolicy | None,
        field_name: str,
    ) -> str | None:
        if policy is None:
            return None

        try:
            ResourcePolicy(
                values=dict(policy.values)
            )
        except (TypeError, ValueError) as exc:
            return f"{field_name}: {exc}"

        return None

    @staticmethod
    def _merge_mode(
        current,
        constraint,
        field_name: str,
    ):
        if constraint is None:
            return current

        if current is None:
            return constraint

        if current is constraint:
            return current

        return (
            None,
            (
                f"Execution policy conflict for "
                f"{field_name}: "
                f"{current.value} vs {constraint.value}."
            ),
        )

    def resolve(
        self,
        task_policy: ExecutionPolicy | None,
        runtime_limits: RuntimeExecutionLimits,
        handler_policy: HandlerExecutionPolicy | None = None,
        transaction_policy: TransactionExecutionPolicy | None = None,
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

        if (
            handler_policy is not None
            and not isinstance(
                handler_policy,
                HandlerExecutionPolicy,
            )
        ):
            raise TypeError(
                "handler_policy must be a "
                "HandlerExecutionPolicy or None."
            )

        if (
            transaction_policy is not None
            and not isinstance(
                transaction_policy,
                TransactionExecutionPolicy,
            )
        ):
            raise TypeError(
                "transaction_policy must be a "
                "TransactionExecutionPolicy or None."
            )

        sources = (
            (
                handler_policy,
                "handler",
            ),
            (
                transaction_policy,
                "transaction",
            ),
        )

        for source, source_name in sources:
            if source is None:
                continue

            error = self._validate_resources(
                source.resources,
                f"{source_name}.resources",
            )

            if error is not None:
                return ExecutionPolicyResolution(
                    status=ExecutionPolicyStatus.INVALID,
                    message=error,
                )

        runtime_resource_error = self._validate_resources(
            runtime_limits.resources,
            "runtime.resources",
        )

        if runtime_resource_error is not None:
            return ExecutionPolicyResolution(
                status=ExecutionPolicyStatus.INVALID,
                message=runtime_resource_error,
            )

        if task_policy is not None:
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

            timeout_seconds = (
                task_policy.timeout.total_seconds
            )

            max_attempts = (
                task_policy.retry.max_attempts
            )

            max_workers = (
                task_policy.parallelism.max_workers
            )

            failure_mode = task_policy.failure.mode
            rollback_mode = task_policy.rollback.mode

            resources = None

        else:
            timeout_seconds = (
                runtime_limits.timeout_seconds
            )

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

            failure_mode = None
            rollback_mode = None

            resources = None

        timeout_seconds = self._intersect_limit(
            timeout_seconds,
            runtime_limits.timeout_seconds,
        )

        max_attempts = self._intersect_limit(
            max_attempts,
            runtime_limits.max_attempts,
        )

        max_workers = self._intersect_limit(
            max_workers,
            runtime_limits.max_workers,
        )

        resources = self._intersect_resources(
            resources,
            runtime_limits.resources,
        )

        failure_result = self._merge_mode(
            failure_mode,
            runtime_limits.failure_mode,
            "failure_mode",
        )

        if (
            isinstance(failure_result, tuple)
            and len(failure_result) == 2
            and isinstance(failure_result[1], str)
        ):
            return ExecutionPolicyResolution(
                status=ExecutionPolicyStatus.CONFLICT,
                message=failure_result[1],
            )

        failure_mode = failure_result

        rollback_result = self._merge_mode(
            rollback_mode,
            runtime_limits.rollback_mode,
            "rollback_mode",
        )

        if (
            isinstance(rollback_result, tuple)
            and len(rollback_result) == 2
            and isinstance(rollback_result[1], str)
        ):
            return ExecutionPolicyResolution(
                status=ExecutionPolicyStatus.CONFLICT,
                message=rollback_result[1],
            )

        rollback_mode = rollback_result

        for source, source_name in sources:
            if source is None:
                continue

            timeout_seconds = self._intersect_limit(
                timeout_seconds,
                source.timeout_seconds,
            )

            max_attempts = self._intersect_limit(
                max_attempts,
                source.max_attempts,
            )

            max_workers = self._intersect_limit(
                max_workers,
                source.max_workers,
            )

            resources = self._intersect_resources(
                resources,
                source.resources,
            )

            failure_result = self._merge_mode(
                failure_mode,
                source.failure_mode,
                "failure_mode",
            )

            if (
                isinstance(failure_result, tuple)
                and len(failure_result) == 2
                and isinstance(failure_result[1], str)
            ):
                return ExecutionPolicyResolution(
                    status=ExecutionPolicyStatus.CONFLICT,
                    message=(
                        f"{source_name}: "
                        f"{failure_result[1]}"
                    ),
                )

            failure_mode = failure_result

            rollback_result = self._merge_mode(
                rollback_mode,
                source.rollback_mode,
                "rollback_mode",
            )

            if (
                isinstance(rollback_result, tuple)
                and len(rollback_result) == 2
                and isinstance(rollback_result[1], str)
            ):
                return ExecutionPolicyResolution(
                    status=ExecutionPolicyStatus.CONFLICT,
                    message=(
                        f"{source_name}: "
                        f"{rollback_result[1]}"
                    ),
                )

            rollback_mode = rollback_result

        if max_attempts is None:
            max_attempts = 1

        if max_workers is None:
            max_workers = 1

        if failure_mode is None:
            failure_mode = FailureMode.ABORT

        if rollback_mode is None:
            rollback_mode = RollbackMode.REQUIRED

        checks = (
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

        return ExecutionPolicyResolution(
            status=ExecutionPolicyStatus.READY,
            policy=EffectiveExecutionPolicy(
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
                max_workers=max_workers,
                failure_mode=failure_mode,
                rollback_mode=rollback_mode,
                resources=resources,
            ),
        )
