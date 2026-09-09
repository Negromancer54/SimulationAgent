from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from runtime.cancellation import CancellationToken
from runtime.execution_backend import (
    BackendBatchResult,
    BackendStepResult,
    ExecutionBackend,
)
from runtime.execution_plan import PlanStep
from runtime.execution_types import ExecutionStatus
from runtime.parallel_batch_executor import (
    ParallelBatchExecutor,
)


def make_step(step_id: str) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        handler_id="handler.test",
        target_kind="PROJECT",
        target_identifier="project",
        goal_identifier="test.goal",
        goal_version=1,
    )


class RecordingBackend(ExecutionBackend):
    def __init__(self, status: ExecutionStatus):
        self.status = status
        self.calls = 0
        self.batches: list[tuple[str, ...]] = []

    def execute_batch(self, steps, handlers):
        self.calls += 1

        self.batches.append(
            tuple(
                step.step_id
                for step in steps
            )
        )

        return BackendBatchResult(
            results=tuple(
                BackendStepResult(
                    step_id=step.step_id,
                    status=self.status,
                    message="",
                )
                for step in steps
            ),
            cancelled=(
                self.status is ExecutionStatus.CANCELLED
            ),
        )


def test_cancelled_token_blocks_initial_batch():
    token = CancellationToken()
    token.cancel()

    backend = RecordingBackend(
        ExecutionStatus.SUCCEEDED
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        (
            make_step("step.1"),
            make_step("step.2"),
        ),
        {},
        max_attempts=3,
        before_attempt=lambda: not token.requested,
    )

    assert result.results[0].status is (
        ExecutionStatus.CANCELLED
    )
    assert result.results[1].status is (
        ExecutionStatus.CANCELLED
    )

    assert result.results[0].attempts == 0
    assert result.results[1].attempts == 0

    assert backend.calls == 0
    assert backend.batches == []


def test_cancellation_between_retries_blocks_next_attempt():
    token = CancellationToken()

    backend = RecordingBackend(
        ExecutionStatus.FAILED
    )

    checks = 0

    def before_attempt():
        nonlocal checks

        checks += 1

        if checks == 2:
            token.cancel()

        return not token.requested

    result = ParallelBatchExecutor(
        backend
    ).execute(
        (
            make_step("step.1"),
        ),
        {},
        max_attempts=3,
        before_attempt=before_attempt,
    )

    assert result.results[0].status is (
        ExecutionStatus.CANCELLED
    )

    assert result.results[0].attempts == 1

    assert backend.calls == 1
    assert backend.batches == [
        ("step.1",),
    ]


def test_cancellation_does_not_retry_completed_step():
    token = CancellationToken()

    backend = RecordingBackend(
        ExecutionStatus.SUCCEEDED
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        (
            make_step("step.1"),
        ),
        {},
        max_attempts=5,
        before_attempt=lambda: not token.requested,
    )

    assert result.results[0].status is (
        ExecutionStatus.SUCCEEDED
    )

    assert result.results[0].attempts == 1
    assert backend.calls == 1


def test_cancellation_callback_is_not_required():
    backend = RecordingBackend(
        ExecutionStatus.SUCCEEDED
    )

    result = ParallelBatchExecutor(
        backend
    ).execute(
        (
            make_step("step.1"),
        ),
        {},
        max_attempts=1,
    )

    assert result.results[0].status is (
        ExecutionStatus.SUCCEEDED
    )

    assert backend.calls == 1


TESTS = [
    test_cancelled_token_blocks_initial_batch,
    test_cancellation_between_retries_blocks_next_attempt,
    test_cancellation_does_not_retry_completed_step,
    test_cancellation_callback_is_not_required,
]


def main():
    print("=" * 70)
    print("PARALLEL BATCH CANCELLATION TESTS")
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
            "PARALLEL BATCH CANCELLATION: PASS"
        )
    else:
        print(
            "PARALLEL BATCH CANCELLATION: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())