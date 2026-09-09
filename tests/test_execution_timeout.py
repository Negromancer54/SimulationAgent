from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    FailureMode,
    GoalKind,
    RollbackMode,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    TargetKind,
)

from runtime.clock import ManualClock
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


def make_plan() -> ExecutionPlan:
    task = TaskV3(
        schema_version=3,
        task_id="execution-timeout-test",
        description="Execution timeout test.",
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
    timeout_seconds: int | None,
    *,
    max_attempts: int = 1,
) -> EffectiveExecutionPolicy:
    return EffectiveExecutionPolicy(
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        max_workers=1,
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
    )


def test_execution_succeeds_before_deadline():
    clock = ManualClock()

    def handler(step):
        clock.advance(5)

    result = ExecutionRuntime(
        clock=clock,
    ).execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(10),
    )

    assert result.status is ExecutionStatus.SUCCEEDED


def test_execution_times_out_when_deadline_is_reached():
    clock = ManualClock()

    def handler(step):
        clock.advance(10)

    result = ExecutionRuntime(
        clock=clock,
    ).execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(10),
    )

    assert result.status is ExecutionStatus.CANCELLED
    assert result.failed_step == "step.1"


def test_execution_times_out_after_deadline_is_exceeded():
    clock = ManualClock()

    def handler(step):
        clock.advance(11)

    result = ExecutionRuntime(
        clock=clock,
    ).execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(10),
    )

    assert result.status is ExecutionStatus.CANCELLED
    assert result.failed_step == "step.1"


def test_no_timeout_when_policy_has_no_deadline():
    clock = ManualClock()

    def handler(step):
        clock.advance(1000)

    result = ExecutionRuntime(
        clock=clock,
    ).execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(None),
    )

    assert result.status is ExecutionStatus.SUCCEEDED


def test_timeout_is_checked_between_attempts():
    clock = ManualClock()
    calls = 0

    def handler(step):
        nonlocal calls

        calls += 1

        # First attempt reaches the deadline and then fails.
        clock.advance(10)

        raise RuntimeError(
            "temporary failure"
        )

    result = ExecutionRuntime(
        clock=clock,
    ).execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler
        },
        policy=make_policy(
            10,
            max_attempts=3,
        ),
    )

    assert result.status is ExecutionStatus.CANCELLED
    assert calls == 1
    assert result.failed_step == "step.1"

    assert len(result.step_results) == 1
    assert (
        result.step_results[0].status
        is ExecutionStatus.CANCELLED
    )
    assert (
        result.step_results[0].attempts
        == 1
    )
def test_timeout_policy_is_preserved_in_execution_result():
    clock = ManualClock()

    policy = make_policy(20)

    result = ExecutionRuntime(
        clock=clock,
    ).execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": lambda step: None
        },
        policy=policy,
    )

    assert result.policy is policy


TESTS = [
    test_execution_succeeds_before_deadline,
    test_execution_times_out_when_deadline_is_reached,
    test_execution_times_out_after_deadline_is_exceeded,
    test_no_timeout_when_policy_has_no_deadline,
    test_timeout_is_checked_between_attempts,
    test_timeout_policy_is_preserved_in_execution_result,
]


def main():
    print("=" * 70)
    print("EXECUTION TIMEOUT TESTS")
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
            "EXECUTION TIMEOUT: PASS"
        )
    else:
        print(
            "EXECUTION TIMEOUT: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())