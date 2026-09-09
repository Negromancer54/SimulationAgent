from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    GoalKind,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    TargetKind,
)

from runtime.execution import (
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
    PlanStep,
    ResourceRequirements,
)
from runtime.execution_policy import (
    EffectiveExecutionPolicy,
)
from runtime.preconditions import (
    PreconditionsResult,
)

from agent_task_v3 import (
    FailureMode,
    RollbackMode,
)


def make_plan() -> ExecutionPlan:
    task = TaskV3(
        schema_version=3,
        task_id="execution-retry-test",
        description="Execution retry test.",
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=TaskTarget(
                kind=TargetKind.PROJECT,
                identifier="project",
                scope=TaskScope(
                    project="SimulationZero-Cpp"
                ),
            ),
            goal=TaskGoal(
                kind=GoalKind.OUTCOME,
                identifier="test.goal",
                version=1,
                parameters={},
            ),
        ),
    )

    return ExecutionPlan(
        status=PlanStatus.READY,
        task=task,
        steps=(
            PlanStep(
                step_id="step.1",
                handler_id="handler.test",
                target_kind="PROJECT",
                target_identifier="project",
                goal_identifier="test.goal",
                goal_version=1,
                depends_on=(),
                resources=ResourceRequirements(
                    capabilities=()
                ),
            ),
        ),
    )


def make_policy(
    max_attempts: int,
) -> EffectiveExecutionPolicy:
    return EffectiveExecutionPolicy(
        timeout_seconds=None,
        max_attempts=max_attempts,
        max_workers=1,
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
    )


def test_failed_first_attempt_then_success_retries():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1

        if calls == 1:
            raise RuntimeError(
                "temporary failure"
            )

    result = ExecutionRuntime().execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(3),
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.completed_steps == (
        "step.1",
    )
    assert calls == 2

    assert len(result.step_results) == 1
    assert result.step_results[0].status is ExecutionStatus.SUCCEEDED
    assert result.step_results[0].attempts == 2


def test_success_on_first_attempt_does_not_retry():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1

    result = ExecutionRuntime().execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(5),
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert calls == 1
    assert result.step_results[0].attempts == 1


def test_all_attempts_failed():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1
        raise RuntimeError(
            "persistent failure"
        )

    result = ExecutionRuntime().execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(3),
    )

    assert result.status is ExecutionStatus.FAILED
    assert calls == 3

    assert result.failed_step == "step.1"
    assert len(result.completed_steps) == 0

    assert len(result.step_results) == 1
    assert result.step_results[0].status is ExecutionStatus.FAILED
    assert result.step_results[0].attempts == 3


def test_default_policy_without_policy_object_means_one_attempt():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1
        raise RuntimeError(
            "failure"
        )

    result = ExecutionRuntime().execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
    )

    assert result.status is ExecutionStatus.FAILED
    assert calls == 1
    assert result.step_results[0].attempts == 1


def test_infrastructure_error_is_not_retried():
    calls = 0

    result = ExecutionRuntime().execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={},
        policy=make_policy(5),
    )

    assert result.status is ExecutionStatus.INFRASTRUCTURE_ERROR
    assert result.failed_step == "step.1"
    assert len(result.step_results) == 1
    assert result.step_results[0].attempts == 0


def test_cancellation_is_not_retried():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1
        raise KeyboardInterrupt()

    result = ExecutionRuntime().execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(5),
    )

    assert result.status is ExecutionStatus.CANCELLED
    assert calls == 1
    assert result.step_results[0].attempts == 1


TESTS = [
    test_failed_first_attempt_then_success_retries,
    test_success_on_first_attempt_does_not_retry,
    test_all_attempts_failed,
    test_default_policy_without_policy_object_means_one_attempt,
    test_infrastructure_error_is_not_retried,
    test_cancellation_is_not_retried,
]


def main():
    print("=" * 70)
    print("EXECUTION RETRY TESTS")
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
            "EXECUTION RETRY: PASS"
        )
    else:
        print(
            "EXECUTION RETRY: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())