from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    FailureMode,
    ExecutionPolicy,
    FailurePolicy,
    GoalKind,
    ParallelismPolicy,
    RetryPolicy,
    RollbackMode,
    RollbackPolicy,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    TargetKind,
    TimeoutPolicy,
)

from runtime.assertions import AssertionRegistry
from runtime.clock import ManualClock
from runtime.execution import (
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_policy import (
    RuntimeExecutionLimits,
)
from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
)
from runtime.task_run import TaskRunStatus
from runtime.task_run_executor import TaskRunExecutor

from registries.goal_registry import (
    GoalRegistry,
    GoalSpec,
)
from registries.handler_registry import (
    HandlerApplicability,
    HandlerRegistry,
    HandlerSpec,
)
from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


def make_task(
    *,
    policy: ExecutionPolicy | None = None,
) -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="execution-timeout-pipeline-test",
        description="Execution timeout pipeline test.",
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=TaskTarget(
                kind=TargetKind.PROJECT,
                identifier="simulation_zero",
                scope=TaskScope(
                    project="SimulationZero-Cpp"
                ),
            ),
            goal=TaskGoal(
                kind=GoalKind.OUTCOME,
                identifier=GOAL_ID,
                version=GOAL_VERSION,
                parameters={},
            ),
        ),
        execution_policy=policy,
    )


def make_policy(
    *,
    timeout: int | None,
    attempts: int = 1,
) -> ExecutionPolicy:
    return ExecutionPolicy(
        timeout=TimeoutPolicy(
            total_seconds=timeout
            if timeout is not None
            else 1
        ),
        retry=RetryPolicy(
            max_attempts=attempts
        ),
        parallelism=ParallelismPolicy(
            max_workers=1
        ),
        failure=FailurePolicy(
            mode=FailureMode.ABORT
        ),
        rollback=RollbackPolicy(
            mode=RollbackMode.REQUIRED
        ),
    )


def make_target_directory() -> TargetDirectory:
    directory = TargetDirectory()

    directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    return directory


def make_handler_registry() -> HandlerRegistry:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    return registry


def make_executor(
    *,
    clock: ManualClock,
    runtime_limits: RuntimeExecutionLimits | None = None,
) -> TaskRunExecutor:
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="Execution timeout pipeline test.",
            owner="PROJECT",
        )
    )

    return TaskRunExecutor(
        goal_registry,
        make_target_directory(),
        make_handler_registry(),
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        AssertionRegistry(),
        execution_runtime=ExecutionRuntime(
            clock=clock
        ),
        runtime_execution_limits=runtime_limits,
    )


def test_timeout_propagates_through_full_pipeline():
    clock = ManualClock()

    def handler(step):
        clock.advance(10)

    result = make_executor(
        clock=clock
    ).execute(
        make_task(
            policy=make_policy(
                timeout=10
            )
        ),
        handlers={
            HANDLER_ID: handler
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    assert result.run.effective_execution_policy is not None
    assert (
        result.run.effective_execution_policy.timeout_seconds
        == 10
    )

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.CANCELLED
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status.name
        == "EXECUTION_FAILED"
    )


def test_runtime_timeout_limit_overrides_task_timeout():
    clock = ManualClock()

    def handler(step):
        clock.advance(20)

    result = make_executor(
        clock=clock,
        runtime_limits=RuntimeExecutionLimits(
            timeout_seconds=10
        ),
    ).execute(
        make_task(
            policy=make_policy(
                timeout=30
            )
        ),
        handlers={
            HANDLER_ID: handler
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    effective = result.run.effective_execution_policy

    assert effective is not None
    assert effective.timeout_seconds == 10

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.CANCELLED
    )


def test_execution_within_pipeline_deadline_succeeds():
    clock = ManualClock()

    def handler(step):
        clock.advance(5)

    result = make_executor(
        clock=clock
    ).execute(
        make_task(
            policy=make_policy(
                timeout=10
            )
        ),
        handlers={
            HANDLER_ID: handler
        },
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.SUCCEEDED
    )

    assert result.run.outcome is not None
    assert result.run.outcome.succeeded


def test_timeout_prevents_retry_after_deadline():
    clock = ManualClock()
    calls = 0

    def handler(step):
        nonlocal calls

        calls += 1
        clock.advance(10)

        raise RuntimeError(
            "temporary failure"
        )

    result = make_executor(
        clock=clock
    ).execute(
        make_task(
            policy=make_policy(
                timeout=10,
                attempts=5,
            )
        ),
        handlers={
            HANDLER_ID: handler
        },
    )

    assert not result.completed
    assert calls == 1

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.CANCELLED
    )

    assert (
        result.run.execution.step_results[0].attempts
        == 1
    )


def test_timeout_preserves_execution_result_policy_identity():
    clock = ManualClock()

    policy = make_policy(
        timeout=20
    )

    result = make_executor(
        clock=clock
    ).execute(
        make_task(
            policy=policy
        ),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed

    effective = result.run.effective_execution_policy
    execution = result.run.execution

    assert effective is not None
    assert execution is not None
    assert execution.policy is effective


def test_timeout_does_not_mutate_task():
    clock = ManualClock()

    policy = make_policy(
        timeout=10
    )

    task = make_task(
        policy=policy
    )

    before = task

    result = make_executor(
        clock=clock
    ).execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.run.task is before
    assert task.execution_policy is policy


TESTS = [
    test_timeout_propagates_through_full_pipeline,
    test_runtime_timeout_limit_overrides_task_timeout,
    test_execution_within_pipeline_deadline_succeeds,
    test_timeout_prevents_retry_after_deadline,
    test_timeout_preserves_execution_result_policy_identity,
    test_timeout_does_not_mutate_task,
]


def main():
    print("=" * 70)
    print("EXECUTION TIMEOUT PIPELINE TESTS")
    print("=" * 70)

    passed = 0

    for test in TESTS:
        try:
            test()
            print(
                f"[PASS] {test.__name__}"
            )
            passed += 1
        except Exception as exc:
            print(
                f"[FAIL] {test.__name__}"
            )
            print(
                f"       {type(exc).__name__}: {exc}"
            )

    print()
    print(
        f"Tests: {passed}/{len(TESTS)}"
    )

    if passed == len(TESTS):
        print(
            "EXECUTION TIMEOUT PIPELINE: PASS"
        )
    else:
        print(
            "EXECUTION TIMEOUT PIPELINE: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())