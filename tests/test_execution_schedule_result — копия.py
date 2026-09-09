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

from runtime.execution import (
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
    PlanStep,
)
from runtime.execution_policy import (
    EffectiveExecutionPolicy,
)
from runtime.preconditions import (
    PreconditionsResult,
)


def make_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="execution-schedule-result-test",
        description="Execution schedule result test.",
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


def make_step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        handler_id=f"handler.{step_id}",
        target_kind="PROJECT",
        target_identifier="project",
        goal_identifier="test.goal",
        goal_version=1,
        depends_on=depends_on,
    )


def make_plan(
    steps: tuple[PlanStep, ...],
) -> ExecutionPlan:
    return ExecutionPlan(
        status=PlanStatus.READY,
        task=make_task(),
        steps=steps,
    )


def make_policy(
    max_workers: int,
) -> EffectiveExecutionPolicy:
    return EffectiveExecutionPolicy(
        timeout_seconds=None,
        max_attempts=1,
        max_workers=max_workers,
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
    )


def test_successful_execution_preserves_schedule():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    result = ExecutionRuntime().execute(
        make_plan(steps),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: None,
            "handler.step.2": lambda step: None,
            "handler.step.3": lambda step: None,
        },
        policy=make_policy(2),
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.schedule is not None

    assert len(result.schedule.batches) == 2

    assert tuple(
        step.step_id
        for step in result.schedule.batches[0].steps
    ) == (
        "step.1",
        "step.2",
    )

    assert tuple(
        step.step_id
        for step in result.schedule.batches[1].steps
    ) == (
        "step.3",
    )


def test_schedule_uses_policy_max_workers():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
        make_step("step.4"),
    )

    result = ExecutionRuntime().execute(
        make_plan(steps),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: None,
            "handler.step.2": lambda step: None,
            "handler.step.3": lambda step: None,
            "handler.step.4": lambda step: None,
        },
        policy=make_policy(3),
    )

    assert result.schedule is not None

    assert len(result.schedule.batches) == 2

    assert len(
        result.schedule.batches[0].steps
    ) == 3

    assert len(
        result.schedule.batches[1].steps
    ) == 1


def test_schedule_preserves_dependencies():
    steps = (
        make_step("step.1"),
        make_step(
            "step.2",
            depends_on=("step.1",),
        ),
        make_step("step.3"),
    )

    result = ExecutionRuntime().execute(
        make_plan(steps),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: None,
            "handler.step.2": lambda step: None,
            "handler.step.3": lambda step: None,
        },
        policy=make_policy(2),
    )

    assert result.schedule is not None

    assert result.schedule.batches[0].steps == (
        steps[0],
        steps[2],
    )

    assert result.schedule.batches[1].steps == (
        steps[1],
    )


def test_failed_execution_preserves_schedule():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    result = ExecutionRuntime().execute(
        make_plan(steps),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: None,
            "handler.step.2":
                lambda step: (
                    (_ for _ in ()).throw(
                        RuntimeError("failure")
                    )
                ),
            "handler.step.3": lambda step: None,
        },
        policy=make_policy(2),
    )

    assert result.status is ExecutionStatus.FAILED
    assert result.schedule is not None

    assert len(result.schedule.batches) == 2


def test_timeout_preserves_schedule():
    from runtime.clock import ManualClock

    clock = ManualClock()

    steps = (
        make_step("step.1"),
        make_step("step.2"),
    )

    def handler(step):
        clock.advance(10)

    result = ExecutionRuntime(
        clock=clock,
    ).execute(
        make_plan(steps),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": handler,
            "handler.step.2": handler,
        },
        policy=EffectiveExecutionPolicy(
            timeout_seconds=10,
            max_attempts=1,
            max_workers=2,
            failure_mode=FailureMode.ABORT,
            rollback_mode=RollbackMode.REQUIRED,
        ),
    )

    assert result.status is ExecutionStatus.CANCELLED
    assert result.schedule is not None


def test_no_schedule_exists_when_plan_is_invalid():
    result = ExecutionRuntime().execute(
        ExecutionPlan(
            status=PlanStatus.INVALID_RESOLUTION,
            task=make_task(),
            steps=(),
            message="invalid",
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={},
        policy=make_policy(2),
    )

    assert (
        result.status
        is ExecutionStatus.INFRASTRUCTURE_ERROR
    )

    assert result.schedule is None


TESTS = [
    test_successful_execution_preserves_schedule,
    test_schedule_uses_policy_max_workers,
    test_schedule_preserves_dependencies,
    test_failed_execution_preserves_schedule,
    test_timeout_preserves_schedule,
    test_no_schedule_exists_when_plan_is_invalid,
]


def main():
    print("=" * 70)
    print("EXECUTION SCHEDULE RESULT TESTS")
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
            "EXECUTION SCHEDULE RESULT: PASS"
        )
    else:
        print(
            "EXECUTION SCHEDULE RESULT: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())