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

from runtime.execution import ExecutionStatus
from runtime.execution_backend import (
    BackendBatchResult,
    SequentialBackend,
)
from runtime.execution_plan import PlanStep


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


def test_successful_batch_preserves_step_order():
    calls: list[str] = []

    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    result = SequentialBackend().execute_batch(
        steps,
        handlers={
            "handler.step.1":
                lambda step: calls.append("step.1"),
            "handler.step.2":
                lambda step: calls.append("step.2"),
            "handler.step.3":
                lambda step: calls.append("step.3"),
        },
    )

    assert isinstance(
        result,
        BackendBatchResult,
    )

    assert calls == [
        "step.1",
        "step.2",
        "step.3",
    ]

    assert tuple(
        item.step_id
        for item in result.results
    ) == (
        "step.1",
        "step.2",
        "step.3",
    )

    assert all(
        item.status is ExecutionStatus.SUCCEEDED
        for item in result.results
    )


def test_missing_handler_is_infrastructure_error():
    step = make_step("step.1")

    result = SequentialBackend().execute_batch(
        (step,),
        handlers={},
    )

    assert len(result.results) == 1
    assert (
        result.results[0].status
        is ExecutionStatus.INFRASTRUCTURE_ERROR
    )


def test_handler_failure_stops_remaining_steps():
    calls: list[str] = []

    def failing_handler(step):
        calls.append("step.2")

        raise RuntimeError(
            "failure"
        )

    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    result = SequentialBackend().execute_batch(
        steps,
        handlers={
            "handler.step.1":
                lambda step: calls.append("step.1"),
            "handler.step.2":
                failing_handler,
            "handler.step.3":
                lambda step: calls.append("step.3"),
        },
    )

    assert calls == [
        "step.1",
        "step.2",
    ]

    assert tuple(
        item.status
        for item in result.results
    ) == (
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
    )

    assert result.results[-1].step_id == "step.2"


def test_keyboard_interrupt_cancels_batch():
    calls = 0

    def cancelling_handler(step):
        nonlocal calls
        calls += 1
        raise KeyboardInterrupt()

    result = SequentialBackend().execute_batch(
        (make_step("step.1"),),
        handlers={
            "handler.step.1":
                cancelling_handler
        },
    )

    assert calls == 1
    assert result.cancelled is True
    assert len(result.results) == 1
    assert (
        result.results[0].status
        is ExecutionStatus.CANCELLED
    )


def test_empty_batch_succeeds():
    result = SequentialBackend().execute_batch(
        (),
        handlers={},
    )

    assert result.results == ()
    assert result.cancelled is False


def test_backend_does_not_modify_steps():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
    )

    before = steps

    SequentialBackend().execute_batch(
        steps,
        handlers={
            "handler.step.1": lambda step: None,
            "handler.step.2": lambda step: None,
        },
    )

    assert steps == before


TESTS = [
    test_successful_batch_preserves_step_order,
    test_missing_handler_is_infrastructure_error,
    test_handler_failure_stops_remaining_steps,
    test_keyboard_interrupt_cancels_batch,
    test_empty_batch_succeeds,
    test_backend_does_not_modify_steps,
]


def main():
    print("=" * 70)
    print("EXECUTION BACKEND TESTS")
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
            "EXECUTION BACKEND: PASS"
        )
    else:
        print(
            "EXECUTION BACKEND: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())