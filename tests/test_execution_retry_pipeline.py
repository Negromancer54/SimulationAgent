from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    ExecutionPolicy,
    FailureMode,
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
from runtime.execution import ExecutionStatus
from runtime.execution_policy import RuntimeExecutionLimits
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
        task_id="execution-retry-pipeline-test",
        description="Execution retry pipeline test.",
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
    max_attempts: int,
    timeout: int = 120,
    workers: int = 1,
) -> ExecutionPolicy:
    return ExecutionPolicy(
        timeout=TimeoutPolicy(
            total_seconds=timeout
        ),
        retry=RetryPolicy(
            max_attempts=max_attempts
        ),
        parallelism=ParallelismPolicy(
            max_workers=workers
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
    runtime_limits: RuntimeExecutionLimits | None = None,
) -> TaskRunExecutor:
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="Execution retry pipeline test.",
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
        runtime_execution_limits=runtime_limits,
    )


def test_executor_retries_failed_handler_until_success():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1

        if calls < 3:
            raise RuntimeError(
                "temporary failure"
            )

    policy = make_policy(
        max_attempts=3
    )

    result = make_executor().execute(
        make_task(policy=policy),
        handlers={
            HANDLER_ID: handler
        },
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED
    assert result.run.effective_execution_policy is not None
    assert (
        result.run.effective_execution_policy.max_attempts
        == 3
    )

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.SUCCEEDED
    )

    assert calls == 3
    assert len(
        result.run.execution.step_results
    ) == 1
    assert (
        result.run.execution.step_results[0].attempts
        == 3
    )

    assert result.run.outcome is not None
    assert result.run.outcome.succeeded


def test_runtime_retry_limit_restricts_task_policy():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1

        if calls < 3:
            raise RuntimeError(
                "temporary failure"
            )

    policy = make_policy(
        max_attempts=5
    )

    result = make_executor(
        runtime_limits=RuntimeExecutionLimits(
            max_attempts=2
        )
    ).execute(
        make_task(policy=policy),
        handlers={
            HANDLER_ID: handler
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    assert result.run.effective_execution_policy is not None
    assert (
        result.run.effective_execution_policy.max_attempts
        == 2
    )

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.FAILED
    )

    assert calls == 2

    assert (
        result.run.execution.step_results[0].attempts
        == 2
    )


def test_executor_exhausts_all_retry_attempts():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1
        raise RuntimeError(
            "persistent failure"
        )

    policy = make_policy(
        max_attempts=4
    )

    result = make_executor().execute(
        make_task(policy=policy),
        handlers={
            HANDLER_ID: handler
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.FAILED
    )

    assert calls == 4

    assert (
        result.run.execution.failed_step
        == "step.1"
    )

    assert (
        result.run.execution.step_results[0].attempts
        == 4
    )

    # Execution failed, therefore the semantic TaskOutcome
    # must preserve the execution failure.
    assert result.run.outcome is not None
    assert (
        result.run.outcome.status.name
        == "EXECUTION_FAILED"
    )

    assert (
        result.run.outcome.execution
        is result.run.execution
    )

def test_effective_policy_and_execution_policy_are_identical_objects():
    policy = make_policy(
        max_attempts=3
    )

    result = make_executor().execute(
        make_task(policy=policy),
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


def test_retry_pipeline_preserves_normal_one_attempt_behavior():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1

    policy = make_policy(
        max_attempts=1
    )

    result = make_executor().execute(
        make_task(policy=policy),
        handlers={
            HANDLER_ID: handler
        },
    )

    assert result.completed
    assert calls == 1

    assert result.run.execution is not None
    assert (
        result.run.execution.step_results[0].attempts
        == 1
    )


def test_retry_does_not_change_task_identity():
    task = make_task(
        policy=make_policy(
            max_attempts=3
        )
    )

    result = make_executor().execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.run.task is task

    assert result.run.execution is not None
    assert (
        result.run.execution.plan.task
        is task
    )


TESTS = [
    test_executor_retries_failed_handler_until_success,
    test_runtime_retry_limit_restricts_task_policy,
    test_executor_exhausts_all_retry_attempts,
    test_effective_policy_and_execution_policy_are_identical_objects,
    test_retry_pipeline_preserves_normal_one_attempt_behavior,
    test_retry_does_not_change_task_identity,
]


def main():
    print("=" * 70)
    print("EXECUTION RETRY PIPELINE TESTS")
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
            "EXECUTION RETRY PIPELINE: PASS"
        )
    else:
        print(
            "EXECUTION RETRY PIPELINE: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())