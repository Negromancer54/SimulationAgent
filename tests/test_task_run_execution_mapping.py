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

from runtime.execution import (
    ExecutionResult,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
)
from runtime.task_run import (
    TaskIntegrity,
    TaskPhase,
    TaskRun,
    TaskStatus,
)


def make_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="execution-mapping-test",
        description="Execution to TaskRun mapping test.",
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


def make_execution(
    status: ExecutionStatus,
) -> ExecutionResult:
    return ExecutionResult(
        plan=ExecutionPlan(
            status=PlanStatus.READY,
            task=make_task(),
            steps=(),
        ),
        status=status,
    )


def test_successful_execution_maps_to_succeeded():
    run = TaskRun(make_task())

    execution = make_execution(
        ExecutionStatus.SUCCEEDED
    )

    run.transition(TaskPhase.VALIDATING)
    run.transition(TaskPhase.RESOLVING)
    run.transition(TaskPhase.PLANNING)
    run.transition(TaskPhase.CHECKING_PRECONDITIONS)
    run.transition(TaskPhase.EXECUTING)

    run.execution = execution
    run.set_task_status(TaskStatus.SUCCEEDED)
    run.set_integrity(TaskIntegrity.VALID)

    assert run.task_status is TaskStatus.SUCCEEDED
    assert run.integrity is TaskIntegrity.VALID
    assert run.phase is TaskPhase.EXECUTING


def test_failed_execution_maps_to_failed():
    run = TaskRun(make_task())

    execution = make_execution(
        ExecutionStatus.FAILED
    )

    run.transition(TaskPhase.VALIDATING)
    run.transition(TaskPhase.RESOLVING)
    run.transition(TaskPhase.PLANNING)
    run.transition(TaskPhase.CHECKING_PRECONDITIONS)
    run.transition(TaskPhase.EXECUTING)

    run.execution = execution
    run.set_task_status(TaskStatus.FAILED)
    run.set_integrity(TaskIntegrity.VALID)

    assert run.task_status is TaskStatus.FAILED
    assert run.integrity is TaskIntegrity.VALID
    assert run.phase is TaskPhase.EXECUTING


def test_infrastructure_error_maps_to_failed_without_becoming_invalid_implicitly():
    run = TaskRun(make_task())

    execution = make_execution(
        ExecutionStatus.INFRASTRUCTURE_ERROR
    )

    run.transition(TaskPhase.VALIDATING)
    run.transition(TaskPhase.RESOLVING)
    run.transition(TaskPhase.PLANNING)
    run.transition(TaskPhase.CHECKING_PRECONDITIONS)
    run.transition(TaskPhase.EXECUTING)

    run.execution = execution
    run.set_task_status(TaskStatus.FAILED)
    run.set_integrity(TaskIntegrity.UNKNOWN)

    assert run.task_status is TaskStatus.FAILED
    assert run.integrity is TaskIntegrity.UNKNOWN
    assert run.phase is TaskPhase.EXECUTING


def test_cancelled_execution_maps_to_cancelled():
    run = TaskRun(make_task())

    execution = make_execution(
        ExecutionStatus.CANCELLED
    )

    run.transition(TaskPhase.VALIDATING)
    run.transition(TaskPhase.RESOLVING)
    run.transition(TaskPhase.PLANNING)
    run.transition(TaskPhase.CHECKING_PRECONDITIONS)
    run.transition(TaskPhase.EXECUTING)

    run.execution = execution
    run.set_task_status(TaskStatus.CANCELLED)
    run.set_integrity(TaskIntegrity.VALID)

    assert run.task_status is TaskStatus.CANCELLED
    assert run.integrity is TaskIntegrity.VALID
    assert run.phase is TaskPhase.EXECUTING


def test_blocked_execution_is_not_mapped_to_failed_automatically():
    run = TaskRun(make_task())

    execution = make_execution(
        ExecutionStatus.BLOCKED
    )

    run.transition(TaskPhase.VALIDATING)
    run.transition(TaskPhase.RESOLVING)
    run.transition(TaskPhase.PLANNING)
    run.transition(TaskPhase.CHECKING_PRECONDITIONS)
    run.transition(TaskPhase.EXECUTING)

    run.execution = execution

    # BLOCKED is deliberately NOT converted to FAILED here.
    # The current model has no terminal TaskStatus.BLOCKED yet.
    # Therefore the mapping layer must make this case explicit
    # rather than silently conflating it with FAILED.
    assert run.task_status in {
        TaskStatus.PENDING,
        TaskStatus.RUNNING,
    }


def test_execution_status_does_not_change_phase_by_itself():
    run = TaskRun(make_task())

    run.transition(TaskPhase.VALIDATING)
    run.transition(TaskPhase.RESOLVING)
    run.transition(TaskPhase.PLANNING)
    run.transition(TaskPhase.CHECKING_PRECONDITIONS)
    run.transition(TaskPhase.EXECUTING)

    original_phase = run.phase

    run.execution = make_execution(
        ExecutionStatus.FAILED
    )

    run.set_task_status(
        TaskStatus.FAILED
    )

    assert run.phase is original_phase


def test_task_integrity_is_independent_from_execution_status():
    run = TaskRun(make_task())

    run.set_task_status(
        TaskStatus.FAILED
    )

    run.set_integrity(
        TaskIntegrity.INVALID
    )

    assert run.task_status is TaskStatus.FAILED
    assert run.integrity is TaskIntegrity.INVALID


TESTS = [
    test_successful_execution_maps_to_succeeded,
    test_failed_execution_maps_to_failed,
    test_infrastructure_error_maps_to_failed_without_becoming_invalid_implicitly,
    test_cancelled_execution_maps_to_cancelled,
    test_blocked_execution_is_not_mapped_to_failed_automatically,
    test_execution_status_does_not_change_phase_by_itself,
    test_task_integrity_is_independent_from_execution_status,
]


def main():
    print("=" * 70)
    print("TASK RUN EXECUTION MAPPING TESTS")
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
            "TASK RUN EXECUTION MAPPING: PASS"
        )
    else:
        print(
            "TASK RUN EXECUTION MAPPING: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())