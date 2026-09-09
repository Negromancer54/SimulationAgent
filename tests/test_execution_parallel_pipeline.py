from __future__ import annotations

from pathlib import Path
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    FailureMode,
    RollbackMode,
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
    ResourcePolicy,
)
from runtime.execution_backend import (
    BackendBatchResult,
)
from runtime.parallel_execution_backend import (
    ParallelExecutionBackend,
)
from runtime.preconditions import (
    PreconditionsResult,
)


def make_plan(
    step_count: int,
) -> ExecutionPlan:
    steps = []

    for index in range(1, step_count + 1):
        steps.append(
            PlanStep(
                step_id=f"step.{index}",
                handler_id="handler.test",
                target_kind="PROJECT",
                target_identifier="project",
                goal_identifier="test.goal",
                goal_version=1,
                depends_on=(),
                resources=ResourceRequirements(),
            )
        )

    return ExecutionPlan(
        status=PlanStatus.READY,
        task=__import__(
            "tests.test_execution_retry",
            fromlist=["make_plan"],
        ).make_plan().task,
        steps=tuple(steps),
        message="",
    )


def make_policy(
    max_workers: int,
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


class RecordingParallelBackend(
    ParallelExecutionBackend
):
    def __init__(self):
        pass
        self.submitted_batches: list[
            tuple[str, ...]
        ] = []

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

        return super().execute_batch(
            steps,
            handlers,
        )


def test_max_workers_one_preserves_single_step_batches():
    backend = RecordingParallelBackend()

    calls = []

    def handler(step):
        calls.append(step.step_id)

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
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.completed_steps == (
        "step.1",
        "step.2",
    )

    assert backend.submitted_batches == [
        ("step.1",),
        ("step.2",),
    ]

    assert calls == [
        "step.1",
        "step.2",
    ]


def test_max_workers_greater_than_one_creates_real_parallel_batch():
    backend = RecordingParallelBackend()

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
            max_workers=2
        ),
    )

    assert result.status is ExecutionStatus.SUCCEEDED

    assert backend.submitted_batches == [
        (
            "step.1",
            "step.2",
        ),
    ]

    assert max_running >= 2


def test_only_failed_step_is_resubmitted_for_retry():
    backend = RecordingParallelBackend()

    calls = {
        "step.1": 0,
        "step.2": 0,
    }

    def handler(step):
        calls[step.step_id] += 1

        if (
            step.step_id == "step.2"
            and calls[step.step_id] == 1
        ):
            raise RuntimeError(
                "temporary failure"
            )

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
            max_workers=2,
            max_attempts=3,
        ),
    )

    assert result.status is ExecutionStatus.SUCCEEDED

    assert calls == {
        "step.1": 1,
        "step.2": 2,
    }

    assert backend.submitted_batches == [
        (
            "step.1",
            "step.2",
        ),
        (
            "step.2",
        ),
    ]

    assert tuple(
        item.attempts
        for item in result.step_results
    ) == (
        1,
        2,
    )


def test_successful_neighbor_is_never_reexecuted():
    backend = RecordingParallelBackend()

    calls = {
        "step.1": 0,
        "step.2": 0,
    }

    def handler(step):
        calls[step.step_id] += 1

        if (
            step.step_id == "step.1"
        ):
            return

        if calls[step.step_id] == 1:
            raise RuntimeError(
                "temporary failure"
            )

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
            max_workers=2,
            max_attempts=2,
        ),
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert calls["step.1"] == 1
    assert calls["step.2"] == 2

    assert backend.submitted_batches[0] == (
        "step.1",
        "step.2",
    )

    assert backend.submitted_batches[1] == (
        "step.2",
    )


def test_parallel_execution_preserves_result_order():
    backend = RecordingParallelBackend()

    def handler(step):
        if step.step_id == "step.1":
            time.sleep(0.15)

        elif step.step_id == "step.2":
            time.sleep(0.01)

        elif step.step_id == "step.3":
            time.sleep(0.05)

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        make_plan(3),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler,
        },
        policy=make_policy(
            max_workers=3
        ),
    )

    assert result.status is ExecutionStatus.SUCCEEDED

    assert tuple(
        item.step_id
        for item in result.step_results
    ) == (
        "step.1",
        "step.2",
        "step.3",
    )


def test_resource_denial_prevents_parallel_batch():
    backend = RecordingParallelBackend()

    plan = make_plan(2)

    steps = tuple(
        PlanStep(
            step_id=step.step_id,
            handler_id=step.handler_id,
            target_kind=step.target_kind,
            target_identifier=step.target_identifier,
            goal_identifier=step.goal_identifier,
            goal_version=step.goal_version,
            depends_on=step.depends_on,
            resources=ResourceRequirements(
                resources={
                    "memory_mb": 2048,
                }
            ),
        )
        for step in plan.steps
    )

    denied_plan = ExecutionPlan(
        status=PlanStatus.READY,
        task=plan.task,
        steps=steps,
        message="",
    )

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        denied_plan,
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": lambda step: None,
        },
        policy=make_policy(
            max_workers=2
        ),
    )

    assert result.status is ExecutionStatus.BLOCKED
    assert backend.submitted_batches == []


TESTS = [
    test_max_workers_one_preserves_single_step_batches,
    test_max_workers_greater_than_one_creates_real_parallel_batch,
    test_only_failed_step_is_resubmitted_for_retry,
    test_successful_neighbor_is_never_reexecuted,
    test_parallel_execution_preserves_result_order,
    test_resource_denial_prevents_parallel_batch,
]


def main():
    print("=" * 70)
    print("EXECUTION PARALLEL PIPELINE TESTS")
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
            "EXECUTION PARALLEL PIPELINE: PASS"
        )
    else:
        print(
            "EXECUTION PARALLEL PIPELINE: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())