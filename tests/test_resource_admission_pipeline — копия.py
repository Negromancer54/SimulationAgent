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
    ResourceRequirements,
)
from runtime.execution_policy import (
    EffectiveExecutionPolicy,
    ResourcePolicy,
)
from runtime.preconditions import (
    PreconditionsResult,
)
from runtime.task_resolution import TaskResolutionResult


def make_plan(
    resources: dict[str, int],
) -> ExecutionPlan:
    from tests.test_execution_retry import make_plan as base_make_plan

    plan = base_make_plan()

    step = PlanStep(
        step_id="step.1",
        handler_id="handler.test",
        target_kind="PROJECT",
        target_identifier="project",
        goal_identifier="test.goal",
        goal_version=1,
        depends_on=(),
        resources=ResourceRequirements(
            resources=resources,
        ),
    )

    return ExecutionPlan(
        status=PlanStatus.READY,
        task=plan.task,
        steps=(step,),
        message="",
    )


def make_policy(
    resources: dict[str, int],
) -> EffectiveExecutionPolicy:
    return EffectiveExecutionPolicy(
        timeout_seconds=None,
        max_attempts=5,
        max_workers=1,
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
        resources=ResourcePolicy(
            values=resources,
        ),
    )


class RecordingBackend(ExecutionBackend):
    def __init__(self):
        self.calls = 0

    def execute_batch(
        self,
        steps,
        handlers,
    ) -> BackendBatchResult:
        self.calls += 1

        return BackendBatchResult(
            results=(
                BackendStepResult(
                    step_id=steps[0].step_id,
                    status=ExecutionStatus.SUCCEEDED,
                    message="backend executed",
                ),
            ),
            cancelled=False,
        )


def test_resource_denial_blocks_before_handler():
    handler_calls = 0

    def handler(step):
        nonlocal handler_calls
        handler_calls += 1

    backend = RecordingBackend()

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        make_plan(
            {
                "memory_mb": 2048,
            }
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler,
        },
        policy=make_policy(
            {
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ExecutionStatus.BLOCKED
    assert result.failed_step == "step.1"
    assert result.step_results[0].status is ExecutionStatus.BLOCKED
    assert result.step_results[0].attempts == 0
    assert handler_calls == 0
    assert backend.calls == 0


def test_resource_denial_does_not_retry():
    backend = RecordingBackend()

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        make_plan(
            {
                "memory_mb": 2048,
            }
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": lambda step: None,
        },
        policy=make_policy(
            {
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ExecutionStatus.BLOCKED
    assert result.step_results[0].attempts == 0
    assert backend.calls == 0


def test_resource_denial_preserves_schedule():
    backend = RecordingBackend()

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        make_plan(
            {
                "memory_mb": 2048,
            }
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": lambda step: None,
        },
        policy=make_policy(
            {
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ExecutionStatus.BLOCKED
    assert result.schedule is not None
    assert len(result.schedule.batches) == 1
    assert result.schedule.batches[0].steps[0].step_id == "step.1"


def test_resource_denial_preserves_policy():
    policy = make_policy(
        {
            "memory_mb": 1024,
        }
    )

    result = ExecutionRuntime().execute(
        make_plan(
            {
                "memory_mb": 2048,
            }
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": lambda step: None,
        },
        policy=policy,
    )

    assert result.status is ExecutionStatus.BLOCKED
    assert result.policy is policy


def test_resource_admission_allows_execution():
    handler_calls = 0

    def handler(step):
        nonlocal handler_calls
        handler_calls += 1

    backend = RecordingBackend()

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        make_plan(
            {
                "memory_mb": 512,
            }
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": handler,
        },
        policy=make_policy(
            {
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.completed_steps == (
        "step.1",
    )
    assert result.step_results[0].attempts == 1
    assert handler_calls == 0
    assert backend.calls == 1


def test_empty_resource_requirements_preserve_existing_execution():
    backend = RecordingBackend()

    result = ExecutionRuntime(
        backend=backend,
    ).execute(
        make_plan({}),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.test": lambda step: None,
        },
        policy=make_policy({}),
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.completed_steps == (
        "step.1",
    )
    assert backend.calls == 1


TESTS = [
    test_resource_denial_blocks_before_handler,
    test_resource_denial_does_not_retry,
    test_resource_denial_preserves_schedule,
    test_resource_denial_preserves_policy,
    test_resource_admission_allows_execution,
    test_empty_resource_requirements_preserve_existing_execution,
]


def main():
    print("=" * 70)
    print("RESOURCE ADMISSION PIPELINE TESTS")
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
            "RESOURCE ADMISSION PIPELINE: PASS"
        )
    else:
        print(
            "RESOURCE ADMISSION PIPELINE: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())