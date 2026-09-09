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

from runtime.task_run import (
    TaskIntegrity,
    TaskPhase,
    TaskRun,
    TaskRunStatus,
    TaskStatus,
)


def make_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="task-run-state-test",
        description="TaskRun state test.",
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


def test_initial_state():
    run = TaskRun(make_task())

    assert run.status is TaskPhase.CREATED
    assert run.phase is TaskPhase.CREATED
    assert run.task_status is TaskStatus.PENDING
    assert run.integrity is TaskIntegrity.UNKNOWN


def test_task_run_status_remains_backward_compatible():
    assert TaskRunStatus is TaskPhase

    run = TaskRun(make_task())

    assert run.status is TaskRunStatus.CREATED


def test_entering_first_runtime_phase_marks_task_running():
    run = TaskRun(make_task())

    run.transition(
        TaskPhase.VALIDATING
    )

    assert run.status is TaskPhase.VALIDATING
    assert run.task_status is TaskStatus.RUNNING


def test_task_status_is_independent_from_phase():
    run = TaskRun(make_task())

    run.transition(
        TaskPhase.VALIDATING
    )

    run.set_task_status(
        TaskStatus.CANCELLED
    )

    assert run.phase is TaskPhase.VALIDATING
    assert run.task_status is TaskStatus.CANCELLED


def test_cancel_does_not_rewrite_phase():
    run = TaskRun(make_task())

    run.transition(
        TaskPhase.VALIDATING
    )

    run.cancel()

    assert run.phase is TaskPhase.VALIDATING
    assert run.task_status is TaskStatus.CANCELLED


def test_cancel_is_terminal():
    run = TaskRun(make_task())

    run.transition(
        TaskPhase.VALIDATING
    )

    run.cancel()

    assert run.terminal is True


def test_integrity_is_independent_from_task_status():
    run = TaskRun(make_task())

    run.set_task_status(
        TaskStatus.FAILED
    )

    run.set_integrity(
        TaskIntegrity.VALID
    )

    assert run.task_status is TaskStatus.FAILED
    assert run.integrity is TaskIntegrity.VALID


def test_invalid_integrity_does_not_change_task_status():
    run = TaskRun(make_task())

    run.set_task_status(
        TaskStatus.SUCCEEDED
    )

    run.set_integrity(
        TaskIntegrity.INVALID
    )

    assert run.task_status is TaskStatus.SUCCEEDED
    assert run.integrity is TaskIntegrity.INVALID


def test_running_status_is_preserved_across_phases():
    run = TaskRun(make_task())

    run.transition(TaskPhase.VALIDATING)
    run.transition(TaskPhase.RESOLVING)
    run.transition(TaskPhase.PLANNING)

    assert run.task_status is TaskStatus.RUNNING
    assert run.phase is TaskPhase.PLANNING


def test_failed_phase_sets_failed_task_status():
    run = TaskRun(make_task())

    run.transition(
        TaskPhase.VALIDATING
    )

    run.transition(
        TaskPhase.FAILED
    )

    assert run.task_status is TaskStatus.FAILED
    assert run.terminal is True


def test_cancelled_status_is_not_overwritten_by_failed_phase():
    run = TaskRun(make_task())

    run.transition(
        TaskPhase.VALIDATING
    )

    run.cancel()

    run.transition(
        TaskPhase.FAILED
    )

    assert run.task_status is TaskStatus.CANCELLED
    assert run.terminal is True


def test_task_id_remains_unchanged():
    run = TaskRun(make_task())

    assert run.task_id == "task-run-state-test"


TESTS = [
    test_initial_state,
    test_task_run_status_remains_backward_compatible,
    test_entering_first_runtime_phase_marks_task_running,
    test_task_status_is_independent_from_phase,
    test_cancel_does_not_rewrite_phase,
    test_cancel_is_terminal,
    test_integrity_is_independent_from_task_status,
    test_invalid_integrity_does_not_change_task_status,
    test_running_status_is_preserved_across_phases,
    test_failed_phase_sets_failed_task_status,
    test_cancelled_status_is_not_overwritten_by_failed_phase,
    test_task_id_remains_unchanged,
]


def main():
    print("=" * 70)
    print("TASK RUN STATE MODEL TESTS")
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
            "TASK RUN STATE MODEL: PASS"
        )
    else:
        print(
            "TASK RUN STATE MODEL: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())