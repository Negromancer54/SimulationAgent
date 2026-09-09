from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    GoalKind,
    TargetKind,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
)
from runtime.execution import (
    ExecutionResult,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
)
from runtime.expected import (
    ExpectedEvaluation,
    ExpectedEvaluationStatus,
)
from runtime.task_outcome import (
    TaskOutcomeEvaluator,
    TaskOutcomeStatus,
)
from runtime.task_run import (
    TaskRun,
    TaskRunStatus,
    TaskRunTransitionError,
)
from runtime.validation import (
    ValidationResult,
    ValidationStatus,
)


def make_task() -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp"
        ),
    )

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=1,
        parameters={},
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id="task-run-test",
        description="TaskRun lifecycle test.",
        intent=intent,
    )


def make_execution_success() -> ExecutionResult:
    plan = ExecutionPlan(
        status=PlanStatus.READY,
        task=make_task(),
    )

    return ExecutionResult(
        plan=plan,
        status=ExecutionStatus.SUCCEEDED,
        completed_steps=(),
    )


def test_task_run_starts_created() -> None:
    run = TaskRun(make_task())

    assert run.status is TaskRunStatus.CREATED
    assert run.history == [
        TaskRunStatus.CREATED
    ]
    assert not run.terminal


def test_task_run_owns_evidence_store() -> None:
    run = TaskRun(make_task())

    assert run.evidence is not None
    assert run.evidence.task_id == run.task_id
    assert run.evidence.count() == 0


def test_valid_lifecycle_can_reach_completed() -> None:
    run = TaskRun(make_task())

    run.transition(TaskRunStatus.VALIDATING)
    run.transition(TaskRunStatus.RESOLVING)
    run.transition(TaskRunStatus.PLANNING)
    run.transition(
        TaskRunStatus.CHECKING_PRECONDITIONS
    )
    run.transition(TaskRunStatus.EXECUTING)
    run.transition(TaskRunStatus.POST_EXECUTION)
    run.transition(TaskRunStatus.EVALUATING)
    run.transition(TaskRunStatus.COMPLETED)

    assert run.status is TaskRunStatus.COMPLETED
    assert run.terminal
    assert not run.successful

    assert run.history == [
        TaskRunStatus.CREATED,
        TaskRunStatus.VALIDATING,
        TaskRunStatus.RESOLVING,
        TaskRunStatus.PLANNING,
        TaskRunStatus.CHECKING_PRECONDITIONS,
        TaskRunStatus.EXECUTING,
        TaskRunStatus.POST_EXECUTION,
        TaskRunStatus.EVALUATING,
        TaskRunStatus.COMPLETED,
    ]


def test_failure_can_happen_from_any_active_phase() -> None:
    for phase in (
        TaskRunStatus.CREATED,
        TaskRunStatus.VALIDATING,
        TaskRunStatus.RESOLVING,
        TaskRunStatus.PLANNING,
        TaskRunStatus.CHECKING_PRECONDITIONS,
        TaskRunStatus.EXECUTING,
        TaskRunStatus.POST_EXECUTION,
        TaskRunStatus.EVALUATING,
    ):
        run = TaskRun(make_task())

        while run.status is not phase:
            next_phase = {
                TaskRunStatus.CREATED: TaskRunStatus.VALIDATING,
                TaskRunStatus.VALIDATING: TaskRunStatus.RESOLVING,
                TaskRunStatus.RESOLVING: TaskRunStatus.PLANNING,
                TaskRunStatus.PLANNING:
                    TaskRunStatus.CHECKING_PRECONDITIONS,
                TaskRunStatus.CHECKING_PRECONDITIONS:
                    TaskRunStatus.EXECUTING,
                TaskRunStatus.EXECUTING:
                    TaskRunStatus.POST_EXECUTION,
                TaskRunStatus.POST_EXECUTION:
                    TaskRunStatus.EVALUATING,
            }[run.status]

            run.transition(next_phase)

        run.transition(TaskRunStatus.FAILED)

        assert run.status is TaskRunStatus.FAILED
        assert run.terminal


def test_completed_run_cannot_transition() -> None:
    run = TaskRun(make_task())

    run.transition(TaskRunStatus.VALIDATING)
    run.transition(TaskRunStatus.RESOLVING)
    run.transition(TaskRunStatus.PLANNING)
    run.transition(
        TaskRunStatus.CHECKING_PRECONDITIONS
    )
    run.transition(TaskRunStatus.EXECUTING)
    run.transition(TaskRunStatus.POST_EXECUTION)
    run.transition(TaskRunStatus.EVALUATING)
    run.transition(TaskRunStatus.COMPLETED)

    try:
        run.transition(TaskRunStatus.FAILED)
    except TaskRunTransitionError:
        return

    raise AssertionError(
        "COMPLETED TaskRun accepted another transition."
    )


def test_failed_run_cannot_transition() -> None:
    run = TaskRun(make_task())

    run.transition(TaskRunStatus.FAILED)

    try:
        run.transition(TaskRunStatus.VALIDATING)
    except TaskRunTransitionError:
        return

    raise AssertionError(
        "FAILED TaskRun accepted another transition."
    )


def test_invalid_transition_is_rejected() -> None:
    run = TaskRun(make_task())

    try:
        run.transition(TaskRunStatus.EXECUTING)
    except TaskRunTransitionError:
        return

    raise AssertionError(
        "Invalid TaskRun transition was accepted."
    )


def test_history_records_every_successful_transition() -> None:
    run = TaskRun(make_task())

    run.transition(TaskRunStatus.VALIDATING)
    run.transition(TaskRunStatus.RESOLVING)

    assert run.history == [
        TaskRunStatus.CREATED,
        TaskRunStatus.VALIDATING,
        TaskRunStatus.RESOLVING,
    ]


def test_history_is_not_changed_by_failed_transition() -> None:
    run = TaskRun(make_task())

    before = list(run.history)

    try:
        run.transition(TaskRunStatus.EXECUTING)
    except TaskRunTransitionError:
        pass

    assert run.history == before
    assert run.status is TaskRunStatus.CREATED


def test_task_identity_is_preserved() -> None:
    task = make_task()
    run = TaskRun(task)

    assert run.task is task
    assert run.task_id == task.task_id


def test_evidence_store_remains_owned_by_run() -> None:
    run = TaskRun(make_task())

    evidence = run.evidence

    assert evidence is not None
    assert evidence.task_id == run.task_id

    assert run.evidence is evidence


def test_runtime_products_can_be_attached() -> None:
    run = TaskRun(make_task())

    plan = ExecutionPlan(
        status=PlanStatus.READY,
        task=run.task,
    )

    execution = ExecutionResult(
        plan=plan,
        status=ExecutionStatus.SUCCEEDED,
    )

    run.execution_plan = plan
    run.execution = execution

    assert run.execution_plan is plan
    assert run.execution is execution


def test_outcome_can_mark_successful_run() -> None:
    run = TaskRun(make_task())

    execution = make_execution_success()

    expected = ExpectedEvaluation(
        expected_id="expected.1",
        kind=GoalKind.STATE,
        status=ExpectedEvaluationStatus.SATISFIED,
    )

    # ExpectedEvaluation.kind above is intentionally replaced by
    # a real ExpectedKind value below.
    from agent_task_v3 import ExpectedKind

    expected = ExpectedEvaluation(
        expected_id="expected.1",
        kind=ExpectedKind.STATE,
        status=ExpectedEvaluationStatus.SATISFIED,
    )

    validation = ValidationResult(
        validation_id="validation.1",
        status=ValidationStatus.VALID,
    )

    outcome = TaskOutcomeEvaluator.evaluate(
        execution,
        (expected,),
        (validation,),
    )

    run.execution = execution
    run.expected_evaluations = (expected,)
    run.validation_results = (validation,)
    run.outcome = outcome

    run.transition(TaskRunStatus.VALIDATING)
    run.transition(TaskRunStatus.RESOLVING)
    run.transition(TaskRunStatus.PLANNING)
    run.transition(
        TaskRunStatus.CHECKING_PRECONDITIONS
    )
    run.transition(TaskRunStatus.EXECUTING)
    run.transition(TaskRunStatus.POST_EXECUTION)
    run.transition(TaskRunStatus.EVALUATING)
    run.transition(TaskRunStatus.COMPLETED)

    assert run.outcome is outcome
    assert run.status is TaskRunStatus.COMPLETED
    assert run.successful


def test_failed_outcome_does_not_mark_run_successful() -> None:
    run = TaskRun(make_task())

    execution = ExecutionResult(
        plan=ExecutionPlan(
            status=PlanStatus.READY,
            task=run.task,
        ),
        status=ExecutionStatus.FAILED,
    )

    outcome = TaskOutcomeEvaluator.evaluate(
        execution
    )

    run.execution = execution
    run.outcome = outcome

    run.transition(TaskRunStatus.FAILED)

    assert run.outcome is outcome
    assert run.status is TaskRunStatus.FAILED
    assert not run.successful


def test_task_run_does_not_modify_task() -> None:
    task = make_task()

    before = (
        task.schema_version,
        task.task_id,
        task.description,
        task.intent,
    )

    TaskRun(task)

    after = (
        task.schema_version,
        task.task_id,
        task.description,
        task.intent,
    )

    assert before == after


def test_terminal_property() -> None:
    run = TaskRun(make_task())

    assert not run.terminal

    run.transition(TaskRunStatus.FAILED)

    assert run.terminal


def main() -> int:
    tests = [
        test_task_run_starts_created,
        test_task_run_owns_evidence_store,
        test_valid_lifecycle_can_reach_completed,
        test_failure_can_happen_from_any_active_phase,
        test_completed_run_cannot_transition,
        test_failed_run_cannot_transition,
        test_invalid_transition_is_rejected,
        test_history_records_every_successful_transition,
        test_history_is_not_changed_by_failed_transition,
        test_task_identity_is_preserved,
        test_evidence_store_remains_owned_by_run,
        test_runtime_products_can_be_attached,
        test_outcome_can_mark_successful_run,
        test_failed_outcome_does_not_mark_run_successful,
        test_task_run_does_not_modify_task,
        test_terminal_property,
    ]

    print("=" * 70)
    print("TASK RUN TESTS")
    print("=" * 70)

    passed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test.__name__}")
            print(
                f"       {type(exc).__name__}: {exc}"
            )

    print()
    print(f"Tests: {passed}/{len(tests)}")

    if passed == len(tests):
        print("TASK RUN: PASS")
    else:
        print("TASK RUN: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())