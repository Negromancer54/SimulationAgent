from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    FailureMode,
    RollbackMode,
)

from runtime.cancellation import (
    CancellationToken,
)
from runtime.execution import (
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_backend import (
    BackendBatchResult,
    BackendStepResult,
    ExecutionBackend,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
    PlanStep,
)
from runtime.execution_policy import (
    EffectiveExecutionPolicy,
    ResourcePolicy,
)
from runtime.preconditions import (
    PreconditionsResult,
)


def make_task():
    from tests.test_execution_retry import make_plan

    return make_plan().task


def make_plan(
    step_count: int,
) -> ExecutionPlan:
    return ExecutionPlan(
        status=PlanStatus.READY,
        task=make_task(),
        steps=tuple(
            PlanStep(
                step_id=f"step.{index}",
                handler_id="handler.test",
                target_kind="PROJECT",
                target_identifier="project",
                goal_identifier="test.goal",
                goal_version=1,
                depends_on=(),
            )
            for index in range(
                1,
                step_count + 1,
            )
        ),
    )


def make_policy(
    max_workers: int = 1,
    max_attempts: int = 3,
) -> EffectiveExecutionPolicy:
    return EffectiveExecutionPolicy(
        timeout_seconds=None,
        max_attempts=max_attempts,
        max_workers=max_workers,
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
        resources=ResourcePolicy(
            values={}
        ),
    )


class RecordingBackend(ExecutionBackend):
    def __init__(self):
        self.calls = 0
        self.batches = []

    def execute_batch(
        self,
        steps,
        handlers,
    ) -> BackendBatchResult:
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
                    status=ExecutionStatus.SUCCEEDED,
                    message="",
                )
                for step in steps
            ),
            cancelled=False,
        )


def test_cancel_before_execution():
    token = CancellationToken()
    token.cancel()

    backend = RecordingBackend()

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        make_plan(1),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": lambda step: None,
        },
        policy=make_policy(),
        cancellation_token=token,
    )

    assert result.status is ExecutionStatus.CANCELLED
    assert result.completed_steps == ()
    assert result.step_results[0].attempts == 0
    assert backend.calls == 0

def test_cancel_between_batches():
    token = CancellationToken()

    calls = []
    backend_calls = []

    class CancellingBackend(ExecutionBackend):
        def execute_batch(
            self,
            steps,
            handlers,
        ) -> BackendBatchResult:
            backend_calls.append(
                tuple(
                    step.step_id
                    for step in steps
                )
            )

            results = []

            for step in steps:
                handler = handlers.get(
                    step.handler_id
                )

                if handler is None:
                    results.append(
                        BackendStepResult(
                            step_id=step.step_id,
                            status=(
                                ExecutionStatus
                                .INFRASTRUCTURE_ERROR
                            ),
                            message="Missing handler.",
                        )
                    )
                    continue

                try:
                    handler(step)
                except KeyboardInterrupt:
                    results.append(
                        BackendStepResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.CANCELLED,
                            message="Execution was cancelled.",
                        )
                    )
                except Exception as exc:
                    results.append(
                        BackendStepResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.FAILED,
                            message=(
                                f"{type(exc).__name__}: {exc}"
                            ),
                        )
                    )
                else:
                    results.append(
                        BackendStepResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.SUCCEEDED,
                            message="",
                        )
                    )

            return BackendBatchResult(
                results=tuple(results),
                cancelled=False,
            )

    backend = CancellingBackend()

    def handler(step):
        calls.append(step.step_id)

        if step.step_id == "step.1":
            token.cancel()

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        make_plan(2),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler,
        },
        policy=make_policy(
            max_workers=1
        ),
        cancellation_token=token,
    )

    assert result.status is ExecutionStatus.CANCELLED

    assert result.completed_steps == (
        "step.1",
    )

    assert backend_calls == [
        ("step.1",),
    ]

    assert calls == [
        "step.1",
    ]


def test_cancelled_token_does_not_retry_after_failure():
    token = CancellationToken()

    attempts = 0

    class CancellingBackend(ExecutionBackend):
        def __init__(self):
            self.calls = 0

        def execute_batch(
            self,
            steps,
            handlers,
        ):
            self.calls += 1

            if self.calls == 1:
                return BackendBatchResult(
                    results=(
                        BackendStepResult(
                            step_id=steps[0].step_id,
                            status=ExecutionStatus.FAILED,
                            message="temporary failure",
                        ),
                    ),
                    cancelled=False,
                )

            raise AssertionError(
                "A second attempt must not be started."
            )

    backend = CancellingBackend()

    def handler(step):
        nonlocal attempts
        attempts += 1

    token_before = {"checked": False}

    def before_attempt():
        if not token_before["checked"]:
            token_before["checked"] = True
            return True

        token.cancel()
        return False

    from runtime.parallel_batch_executor import (
        ParallelBatchExecutor,
    )

    direct_result = ParallelBatchExecutor(
        backend
    ).execute(
        (
            make_plan(1).steps[0],
        ),
        {
            "handler.test": handler,
        },
        max_attempts=3,
        before_attempt=before_attempt,
    )

    assert direct_result.results[0].status is (
        ExecutionStatus.CANCELLED
    )
    assert direct_result.results[0].attempts == 1
    assert backend.calls == 1


def test_invalid_cancellation_token_is_rejected():
    try:
        ExecutionRuntime().execute(
            make_plan(1),
            PreconditionsResult(
                evaluations=()
            ),
            handlers={
                "handler.test": lambda step: None,
            },
            cancellation_token=object(),
        )
    except TypeError:
        return

    raise AssertionError(
        "Invalid cancellation token must be rejected."
    )


TESTS = [
    test_cancel_before_execution,
    test_cancel_between_batches,
    test_cancelled_token_does_not_retry_after_failure,
    test_invalid_cancellation_token_is_rejected,
]


def main():
    print("=" * 70)
    print("EXECUTION CANCELLATION PIPELINE TESTS")
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
            "EXECUTION CANCELLATION PIPELINE: PASS"
        )
    else:
        print(
            "EXECUTION CANCELLATION PIPELINE: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())