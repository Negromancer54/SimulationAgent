from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from runtime.execution_backend import (
    BackendBatchResult,
    BackendStepResult,
    ExecutionBackend,
)
from runtime.execution_plan import (
    PlanStep,
)
from runtime.execution_types import (
    ExecutionStatus,
)
from runtime.parallel_batch_executor import (
    ParallelBatchExecutor,
)


def make_step(
    step_id: str,
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        handler_id="handler.test",
        target_kind="PROJECT",
        target_identifier="project",
        goal_identifier="test.goal",
        goal_version=1,
    )


class ScriptedBackend(ExecutionBackend):
    def __init__(
        self,
        scripts: list[dict[str, ExecutionStatus]],
    ):
        self.scripts = scripts
        self.calls = 0
        self.submitted_batches = []

    def execute_batch(
        self,
        steps,
        handlers,
    ) -> BackendBatchResult:
        self.submitted_batches.append(
            tuple(
                step.step_id
                for step in steps
            )
        )

        script_index = min(
            self.calls,
            len(self.scripts) - 1,
        )

        script = self.scripts[script_index]
        self.calls += 1

        results = []

        for step in steps:
            status = script.get(
                step.step_id,
                ExecutionStatus.SUCCEEDED,
            )

            results.append(
                BackendStepResult(
                    step_id=step.step_id,
                    status=status,
                    message=status.value,
                )
            )

        return BackendBatchResult(
            results=tuple(results),
            cancelled=False,
        )


def test_empty_batch_succeeds():
    backend = ScriptedBackend([])
    executor = ParallelBatchExecutor(backend)

    result = executor.execute(
        (),
        {},
        max_attempts=3,
    )

    assert result.results == ()
    assert backend.calls == 0


def test_all_steps_succeed_on_first_attempt():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    backend = ScriptedBackend(
        [
            {
                "step.1": ExecutionStatus.SUCCEEDED,
                "step.2": ExecutionStatus.SUCCEEDED,
                "step.3": ExecutionStatus.SUCCEEDED,
            }
        ]
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        steps,
        {},
        max_attempts=5,
    )

    assert tuple(
        item.status
        for item in result.results
    ) == (
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.SUCCEEDED,
    )

    assert tuple(
        item.attempts
        for item in result.results
    ) == (
        1,
        1,
        1,
    )

    assert backend.calls == 1


def test_only_failed_step_is_retried():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
    )

    backend = ScriptedBackend(
        [
            {
                "step.1": ExecutionStatus.SUCCEEDED,
                "step.2": ExecutionStatus.FAILED,
            },
            {
                "step.2": ExecutionStatus.SUCCEEDED,
            },
        ]
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        steps,
        {},
        max_attempts=3,
    )

    assert tuple(
        item.status
        for item in result.results
    ) == (
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.SUCCEEDED,
    )

    assert tuple(
        item.attempts
        for item in result.results
    ) == (
        1,
        2,
    )

    assert backend.submitted_batches == [
        (
            "step.1",
            "step.2",
        ),
        (
            "step.2",
        ),
    ]


def test_persistent_failure_stops_after_max_attempts():
    steps = (
        make_step("step.1"),
    )

    backend = ScriptedBackend(
        [
            {
                "step.1": ExecutionStatus.FAILED,
            }
        ]
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        steps,
        {},
        max_attempts=3,
    )

    assert result.results[0].status is (
        ExecutionStatus.FAILED
    )

    assert result.results[0].attempts == 3

    assert backend.calls == 3

    assert backend.submitted_batches == [
        ("step.1",),
        ("step.1",),
        ("step.1",),
    ]


def test_infrastructure_error_is_not_retried():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
    )

    backend = ScriptedBackend(
        [
            {
                "step.1": (
                    ExecutionStatus
                    .INFRASTRUCTURE_ERROR
                ),
                "step.2": ExecutionStatus.SUCCEEDED,
            }
        ]
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        steps,
        {},
        max_attempts=5,
    )

    assert result.results[0].status is (
        ExecutionStatus
        .INFRASTRUCTURE_ERROR
    )

    assert result.results[0].attempts == 1

    assert result.results[1].status is (
        ExecutionStatus.SUCCEEDED
    )

    assert result.results[1].attempts == 1

    assert backend.calls == 1


def test_cancellation_is_not_retried():
    steps = (
        make_step("step.1"),
    )

    backend = ScriptedBackend(
        [
            {
                "step.1": ExecutionStatus.CANCELLED,
            }
        ]
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        steps,
        {},
        max_attempts=5,
    )

    assert result.results[0].status is (
        ExecutionStatus.CANCELLED
    )

    assert result.results[0].attempts == 1

    assert backend.calls == 1


def test_final_results_preserve_input_order():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    backend = ScriptedBackend(
        [
            {
                "step.1": ExecutionStatus.SUCCEEDED,
                "step.2": ExecutionStatus.FAILED,
                "step.3": ExecutionStatus.SUCCEEDED,
            },
            {
                "step.2": ExecutionStatus.SUCCEEDED,
            },
        ]
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        steps,
        {},
        max_attempts=3,
    )

    assert tuple(
        item.step_id
        for item in result.results
    ) == (
        "step.1",
        "step.2",
        "step.3",
    )


def test_successful_steps_are_never_submitted_again():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    backend = ScriptedBackend(
        [
            {
                "step.1": ExecutionStatus.SUCCEEDED,
                "step.2": ExecutionStatus.FAILED,
                "step.3": ExecutionStatus.SUCCEEDED,
            },
            {
                "step.2": ExecutionStatus.SUCCEEDED,
            },
        ]
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        steps,
        {},
        max_attempts=2,
    )

    assert result.results[0].attempts == 1
    assert result.results[1].attempts == 2
    assert result.results[2].attempts == 1

    assert backend.submitted_batches[1] == (
        "step.2",
    )


def test_invalid_max_attempts_is_rejected():
    backend = ScriptedBackend([])
    executor = ParallelBatchExecutor(backend)

    try:
        executor.execute(
            (),
            {},
            max_attempts=0,
        )
    except ValueError:
        return

    raise AssertionError(
        "max_attempts must be positive."
    )


def test_invalid_backend_is_rejected():
    try:
        ParallelBatchExecutor(
            backend=object()
        )
    except TypeError:
        return

    raise AssertionError(
        "Invalid backend must be rejected."
    )


TESTS = [
    test_empty_batch_succeeds,
    test_all_steps_succeed_on_first_attempt,
    test_only_failed_step_is_retried,
    test_persistent_failure_stops_after_max_attempts,
    test_infrastructure_error_is_not_retried,
    test_cancellation_is_not_retried,
    test_final_results_preserve_input_order,
    test_successful_steps_are_never_submitted_again,
    test_invalid_max_attempts_is_rejected,
    test_invalid_backend_is_rejected,
]


def main():
    print("=" * 70)
    print("PARALLEL BATCH EXECUTOR TESTS")
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
            "PARALLEL BATCH EXECUTOR: PASS"
        )
    else:
        print(
            "PARALLEL BATCH EXECUTOR: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())