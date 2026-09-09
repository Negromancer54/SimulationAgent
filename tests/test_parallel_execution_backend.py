from __future__ import annotations

from pathlib import Path
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from runtime.execution_backend import (
    BackendBatchResult,
)
from runtime.execution_types import (
    ExecutionStatus,
)
from runtime.execution_plan import (
    PlanStep,
)
from runtime.parallel_execution_backend import (
    ParallelExecutionBackend,
)


def make_step(
    step_id: str,
    handler_id: str = "handler.test",
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        handler_id=handler_id,
        target_kind="PROJECT",
        target_identifier="project",
        goal_identifier="test.goal",
        goal_version=1,
    )


def test_empty_batch_succeeds():
    result = ParallelExecutionBackend().execute_batch(
        (),
        {},
    )

    assert isinstance(
        result,
        BackendBatchResult,
    )
    assert result.results == ()
    assert result.cancelled is False


def test_multiple_steps_succeed():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    calls = []

    def handler(step):
        calls.append(step.step_id)

    result = ParallelExecutionBackend().execute_batch(
        steps,
        {
            "handler.test": handler,
        },
    )

    assert set(calls) == {
        "step.1",
        "step.2",
        "step.3",
    }

    assert tuple(
        item.step_id
        for item in result.results
    ) == (
        "step.1",
        "step.2",
        "step.3",
    )

    assert tuple(
        item.status
        for item in result.results
    ) == (
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.SUCCEEDED,
    )


def test_results_preserve_input_step_order():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    def handler(step):
        if step.step_id == "step.1":
            time.sleep(0.15)

        if step.step_id == "step.2":
            time.sleep(0.01)

        if step.step_id == "step.3":
            time.sleep(0.05)

    result = ParallelExecutionBackend().execute_batch(
        steps,
        {
            "handler.test": handler,
        },
    )

    assert tuple(
        item.step_id
        for item in result.results
    ) == (
        "step.1",
        "step.2",
        "step.3",
    )


def test_steps_are_actually_executed_concurrently():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
    )

    lock = threading.Lock()
    running = 0
    max_running = 0

    def handler(step):
        nonlocal running
        nonlocal max_running

        with lock:
            running += 1
            max_running = max(
                max_running,
                running,
            )

        time.sleep(0.1)

        with lock:
            running -= 1

    result = ParallelExecutionBackend().execute_batch(
        steps,
        {
            "handler.test": handler,
        },
    )

    assert result.cancelled is False
    assert max_running >= 2


def test_missing_handler_is_infrastructure_error():
    steps = (
        make_step(
            "step.1",
            handler_id="missing",
        ),
    )

    result = ParallelExecutionBackend().execute_batch(
        steps,
        {},
    )

    assert len(result.results) == 1
    assert result.results[0].step_id == "step.1"
    assert (
        result.results[0].status
        is ExecutionStatus.INFRASTRUCTURE_ERROR
    )


def test_handler_failure_is_reported_per_step():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
    )

    def handler(step):
        if step.step_id == "step.1":
            raise RuntimeError(
                "failure"
            )

    result = ParallelExecutionBackend().execute_batch(
        steps,
        {
            "handler.test": handler,
        },
    )

    assert tuple(
        item.status
        for item in result.results
    ) == (
        ExecutionStatus.FAILED,
        ExecutionStatus.SUCCEEDED,
    )


def test_failure_does_not_prevent_other_steps_from_running():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
    )

    calls = []

    def handler(step):
        calls.append(step.step_id)

        if step.step_id == "step.1":
            raise RuntimeError(
                "failure"
            )

    result = ParallelExecutionBackend().execute_batch(
        steps,
        {
            "handler.test": handler,
        },
    )

    assert set(calls) == {
        "step.1",
        "step.2",
    }

    assert result.results[0].status is (
        ExecutionStatus.FAILED
    )

    assert result.results[1].status is (
        ExecutionStatus.SUCCEEDED
    )


def test_backend_does_not_modify_steps():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
    )

    original = tuple(steps)

    ParallelExecutionBackend().execute_batch(
        steps,
        {
            "handler.test": lambda step: None,
        },
    )

    assert steps == original


def test_backend_does_not_perform_retry():
    steps = (
        make_step("step.1"),
    )

    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1

        raise RuntimeError(
            "failure"
        )

    result = ParallelExecutionBackend().execute_batch(
        steps,
        {
            "handler.test": handler,
        },
    )

    assert calls == 1
    assert result.results[0].status is (
        ExecutionStatus.FAILED
    )


TESTS = [
    test_empty_batch_succeeds,
    test_multiple_steps_succeed,
    test_results_preserve_input_step_order,
    test_steps_are_actually_executed_concurrently,
    test_missing_handler_is_infrastructure_error,
    test_handler_failure_is_reported_per_step,
    test_failure_does_not_prevent_other_steps_from_running,
    test_backend_does_not_modify_steps,
    test_backend_does_not_perform_retry,
]


def main():
    print("=" * 70)
    print("PARALLEL EXECUTION BACKEND TESTS")
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
            "PARALLEL EXECUTION BACKEND: PASS"
        )
    else:
        print(
            "PARALLEL EXECUTION BACKEND: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())