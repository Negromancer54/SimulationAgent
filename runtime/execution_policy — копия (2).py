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


@dataclass(frozen=True)
class ResourcePolicy:
    """
    Declarative resource limits for execution.

    The mapping is:
        resource_id -> positive integer limit

    ResourcePolicy does not allocate resources and does not
    communicate with the scheduler. It only represents limits
    already established for the current execution context.
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
class RuntimeExecutionLimits:
    """
    Hard upper bounds imposed by the runtime.

    None means that the runtime does not impose a bound
    for that dimension at this layer.
    """

    timeout_seconds: int | None = None
    max_attempts: int | None = None
    max_workers: int | None = None

    resources: ResourcePolicy | None = None

@dataclass(frozen=True)
class ExecutionPolicyConstraint:
    """
    Optional execution-policy constraints contributed by
    a runtime owner such as a handler or transaction.

    None means that this source imposes no constraint for
    the corresponding dimension.
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
class HandlerExecutionPolicy(ExecutionPolicyConstraint):
    """
    Execution-policy constraints declared by a runtime handler.

    This policy can only restrict execution relative to the
    effective task/runtime context.
    """

    pass


@dataclass(frozen=True)
class TransactionExecutionPolicy(ExecutionPolicyConstraint):
    """
    Execution-policy constraints imposed by the current
    transaction.

    Transaction policy is runtime-owned and exists only for
    a concrete execution context.
    """

    pass
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
    Resolves Task V3 ExecutionPolicy against hard runtime limits.

    The runtime can restrict a task policy, but never expand it.

    Current layer resolves:
        - timeout;
        - retry attempts;
        - parallel workers;
        - runtime resource limits.

    This layer intentionally does not resolve:
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
    def _intersect_resources(
        requested: ResourcePolicy,
        runtime: ResourcePolicy | None,
    ) -> ResourcePolicy:
        if runtime is None:
            return requested

        result: dict[str, int] = {}

        resource_ids = (
            set(requested.values)
            | set(runtime.values)
        )

        for resource_id in resource_ids:
            requested_value = requested.values.get(
                resource_id
            )

            runtime_value = runtime.values.get(
                resource_id
            )

            if requested_value is None:
                result[resource_id] = runtime_value
                continue

            if runtime_value is None:
                result[resource_id] = requested_value
                continue

            result[resource_id] = min(
                requested_value,
                runtime_value,
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
        policy: ResourcePolicy,
        field_name: str,
    ) -> str | None:
        try:
            ResourcePolicy(
                values=dict(policy.values)
            )
        except (TypeError, ValueError) as exc:
            return f"{field_name}: {exc}"

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

        runtime_resources = (
            runtime_limits.resources
            if runtime_limits.resources is not None
            else ResourcePolicy(values={})
        )

        resource_error = self._validate_resources(
            runtime_resources,
            "runtime.resources",
        )

        if resource_error is not None:
            return ExecutionPolicyResolution(
                status=ExecutionPolicyStatus.INVALID,
                message=resource_error,
            )

        # ---------------------------------------------------------
        # No task policy:
        #
        # derive effective defaults from runtime limits.
        # ---------------------------------------------------------

        if task_policy is None:
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

            checks = (
                (
                    timeout_seconds,
                    "timeout_seconds",
                ),
                (
                    max_attempts,
                    "max_attempts",
                ),
                (
                    max_workers,
                    "max_workers",
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
                    failure_mode=FailureMode.ABORT,
                    rollback_mode=RollbackMode.REQUIRED,
                    resources=runtime_resources,
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
        # Task V3 currently has no independently verified
        # resource-policy field exposed by this module.
        #
        # Therefore the task-side resource requirement is not
        # inferred here. Runtime resources are preserved as the
        # effective runtime-side resource policy.
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

        # retry and parallelism always have concrete
        # Task V3 defaults.

        if max_attempts is None:
            max_attempts = 1

        if max_workers is None:
            max_workers = 1

        # ---------------------------------------------------------
        # Validate effective numeric values.
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
                resources=runtime_resources,
            ),
        )