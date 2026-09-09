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
from runtime.execution_backend import (
    SequentialBackend,
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
        task_id="execution-backend-pipeline-test",
        description="Execution backend pipeline test.",
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
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        handler_id=f"handler.{step_id}",
        target_kind="PROJECT",
        target_identifier="project",
        goal_identifier="test.goal",
        goal_version=1,
        depends_on=(),
    )


def make_plan() -> ExecutionPlan:
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    return ExecutionPlan(
        status=PlanStatus.READY,
        task=make_task(),
        steps=steps,
    )


def make_policy(
    *,
    attempts: int = 1,
    workers: int = 1,
) -> EffectiveExecutionPolicy:
    return EffectiveExecutionPolicy(
        timeout_seconds=None,
        max_attempts=attempts,
        max_workers=workers,
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
    )


def test_runtime_can_use_sequential_backend():
    calls: list[str] = []

    runtime = ExecutionRuntime(
        backend=SequentialBackend(),
    )

    result = runtime.execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1":
                lambda step: calls.append("step.1"),
            "handler.step.2":
                lambda step: calls.append("step.2"),
            "handler.step.3":
                lambda step: calls.append("step.3"),
        },
        policy=make_policy(
            workers=2,
        ),
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert calls == [
        "step.1",
        "step.2",
        "step.3",
    ]


def test_backend_failure_is_translated_into_execution_failure():
    calls: list[str] = []

    runtime = ExecutionRuntime(
        backend=SequentialBackend(),
    )

    def failing_handler(step):
        calls.append(step.step_id)
        raise RuntimeError(
            "backend pipeline failure"
        )

    result = runtime.execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: None,
            "handler.step.2": failing_handler,
            "handler.step.3": lambda step: None,
        },
        policy=make_policy(),
    )

    assert result.status is ExecutionStatus.FAILED

    assert calls == [
        "step.2",
    ]

    assert result.failed_step == "step.2"


def test_backend_is_not_responsible_for_retry():
    calls = 0

    runtime = ExecutionRuntime(
        backend=SequentialBackend(),
    )

    def handler(step):
        nonlocal calls
        calls += 1

        if calls < 3:
            raise RuntimeError(
                "temporary failure"
            )

    result = runtime.execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": handler,
            "handler.step.2": lambda step: None,
            "handler.step.3": lambda step: None,
        },
        policy=make_policy(
            attempts=3,
        ),
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert calls == 3


def test_backend_is_not_responsible_for_timeout():
    from runtime.clock import ManualClock

    clock = ManualClock()

    runtime = ExecutionRuntime(
        clock=clock,
        backend=SequentialBackend(),
    )

    def handler(step):
        clock.advance(10)

    result = runtime.execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": handler,
            "handler.step.2": handler,
            "handler.step.3": handler,
        },
        policy=make_policy(),
    )

    assert result.status is ExecutionStatus.SUCCEEDED

def test_backend_preserves_policy_and_schedule_context():
    runtime = ExecutionRuntime(
        backend=SequentialBackend(),
    )

    policy = make_policy(
        attempts=2,
        workers=3,
    )

    result = runtime.execute(
        make_plan(),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: None,
            "handler.step.2": lambda step: None,
            "handler.step.3": lambda step: None,
        },
        policy=policy,
    )

    assert result.policy is policy
    assert result.schedule is not None


TESTS = [
    test_runtime_can_use_sequential_backend,
    test_backend_failure_is_translated_into_execution_failure,
    test_backend_is_not_responsible_for_retry,
    test_backend_is_not_responsible_for_timeout,
    test_backend_preserves_policy_and_schedule_context,
]


def main():
    print("=" * 70)
    print("EXECUTION BACKEND PIPELINE TESTS")
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
            "EXECUTION BACKEND PIPELINE: PASS"
        )
    else:
        print(
            "EXECUTION BACKEND PIPELINE: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())