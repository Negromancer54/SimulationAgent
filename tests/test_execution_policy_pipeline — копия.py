from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    ExecutionPolicy,
    FailureMode,
    GoalKind,
    ParallelismPolicy,
    RetryPolicy,
    RollbackMode,
    FailurePolicy,
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

from runtime.execution import ExecutionRuntime
from runtime.execution_policy import (
    ExecutionPolicyStatus,
    RuntimeExecutionLimits,
)
from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
)
from runtime.task_run import TaskRunStatus
from runtime.task_run_executor import TaskRunExecutor

from runtime.assertions import AssertionRegistry

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
    policy=None,
) -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="execution-policy-pipeline-test",
        description="Execution policy pipeline test.",
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
    timeout=120,
    attempts=5,
    workers=8,
    failure=FailureMode.ABORT,
    rollback=RollbackMode.REQUIRED,
):
    return ExecutionPolicy(
        timeout=TimeoutPolicy(
            total_seconds=timeout
        ),
        retry=RetryPolicy(
            max_attempts=attempts
        ),
        parallelism=ParallelismPolicy(
            max_workers=workers
        ),
        failure=FailurePolicy(
            mode=failure
        ),
        rollback=RollbackPolicy(
            mode=rollback
        ),
    )


def make_executor(
    *,
    runtime_limits=None,
):
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="Execution policy pipeline test.",
            owner="PROJECT",
        )
    )

    directory = TargetDirectory()

    directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    handlers = HandlerRegistry()

    handlers.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    return TaskRunExecutor(
        goal_registry,
        directory,
        handlers,
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        AssertionRegistry(),
        execution_runtime=ExecutionRuntime(),
        runtime_execution_limits=runtime_limits,
    )


def test_task_policy_reaches_task_run():
    policy = make_policy(
        timeout=120,
        attempts=5,
        workers=8,
    )

    result = make_executor().execute(
        make_task(policy=policy),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED
    assert result.run.effective_execution_policy is not None

    effective = result.run.effective_execution_policy

    assert effective.timeout_seconds == 120
    assert effective.max_attempts == 5
    assert effective.max_workers == 8


def test_runtime_limits_are_applied_before_execution():
    policy = make_policy(
        timeout=120,
        attempts=10,
        workers=16,
    )

    result = make_executor(
        runtime_limits=RuntimeExecutionLimits(
            timeout_seconds=30,
            max_attempts=3,
            max_workers=4,
        )
    ).execute(
        make_task(policy=policy),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed

    effective = result.run.effective_execution_policy

    assert effective is not None
    assert effective.timeout_seconds == 30
    assert effective.max_attempts == 3
    assert effective.max_workers == 4


def test_effective_policy_is_same_object_used_by_execution():
    policy = make_policy(
        timeout=90,
        attempts=4,
        workers=6,
    )

    result = make_executor().execute(
        make_task(policy=policy),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed

    run_policy = result.run.effective_execution_policy
    execution = result.run.execution

    assert run_policy is not None
    assert execution is not None
    assert execution.policy is run_policy


def test_missing_task_policy_still_produces_effective_policy():
    result = make_executor(
        runtime_limits=RuntimeExecutionLimits(
            timeout_seconds=45,
            max_attempts=4,
            max_workers=6,
        )
    ).execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed

    effective = result.run.effective_execution_policy

    assert effective is not None
    assert effective.timeout_seconds == 45
    assert effective.max_attempts == 4
    assert effective.max_workers == 6


def test_policy_resolution_failure_stops_before_execution():
    invalid_policy = make_policy(
        timeout=0,
    )

    result = make_executor().execute(
        make_task(policy=invalid_policy),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.execution is None
    assert (
        TaskRunStatus.EXECUTING
        not in result.run.history
    )


def test_failure_and_rollback_are_preserved_in_pipeline():
    policy = make_policy(
        failure=FailureMode.ROLLBACK,
        rollback=RollbackMode.OPTIONAL,
    )

    result = make_executor().execute(
        make_task(policy=policy),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed

    effective = result.run.effective_execution_policy

    assert effective is not None

    assert (
        effective.failure_mode
        is FailureMode.ROLLBACK
    )

    assert (
        effective.rollback_mode
        is RollbackMode.OPTIONAL
    )


TESTS = [
    test_task_policy_reaches_task_run,
    test_runtime_limits_are_applied_before_execution,
    test_effective_policy_is_same_object_used_by_execution,
    test_missing_task_policy_still_produces_effective_policy,
    test_policy_resolution_failure_stops_before_execution,
    test_failure_and_rollback_are_preserved_in_pipeline,
]


def main():
    print("=" * 70)
    print("EXECUTION POLICY PIPELINE TESTS")
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
            "EXECUTION POLICY PIPELINE: PASS"
        )
    else:
        print(
            "EXECUTION POLICY PIPELINE: FAIL"
        )

    print("=" * 70)

    return (
        0
        if passed == len(TESTS)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())