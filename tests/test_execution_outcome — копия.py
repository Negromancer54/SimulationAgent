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

from runtime.assertions import AssertionRegistry
from runtime.execution import (
    ExecutionStatus,
)
from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
)
from runtime.task_outcome import (
    TaskOutcomeStatus,
)
from runtime.task_run import (
    TaskRunStatus,
)
from runtime.task_run_executor import (
    TaskRunExecutor,
)

from registries.goal_registry import (
    GoalRegistry,
    GoalSpec,
)
from registries.handler_registry import (
    HandlerApplicability,
    HandlerRegistry,
    HandlerSpec,
)
from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


def make_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="execution-outcome-test",
        description="Execution to TaskOutcome contract test.",
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=TaskTarget(
                kind=TargetKind.PROJECT,
                identifier="simulation_zero",
                scope=TaskScope(
                    project="SimulationZero-Cpp"
                ),
            ),
            goal=TaskGoal(
                kind=GoalKind.OUTCOME,
                identifier=GOAL_ID,
                version=GOAL_VERSION,
                parameters={},
            ),
        ),
    )


def make_executor() -> TaskRunExecutor:
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="Execution to TaskOutcome contract test.",
            owner="PROJECT",
        )
    )

    directory = TargetDirectory()

    directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    handlers = HandlerRegistry()

    handlers.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    return TaskRunExecutor(
        goal_registry,
        directory,
        handlers,
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        AssertionRegistry(),
    )


def test_execution_failure_produces_task_outcome():
    def failing_handler(step):
        raise RuntimeError(
            "execution failed"
        )

    result = make_executor().execute(
        make_task(),
        handlers={
            HANDLER_ID: failing_handler
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.FAILED
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.EXECUTION_FAILED
    )

    assert (
        result.run.outcome.execution
        is result.run.execution
    )


def test_infrastructure_execution_failure_produces_task_outcome():
    result = make_executor().execute(
        make_task(),
        handlers={},
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.INFRASTRUCTURE_ERROR
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.EXECUTION_FAILED
    )

    assert (
        result.run.outcome.execution
        is result.run.execution
    )


def test_execution_failure_outcome_has_no_uncomputed_post_execution_results():
    def failing_handler(step):
        raise RuntimeError(
            "execution failed"
        )

    result = make_executor().execute(
        make_task(),
        handlers={
            HANDLER_ID: failing_handler
        },
    )

    assert result.run.outcome is not None

    assert (
        result.run.outcome.expected_evaluations
        == ()
    )

    assert (
        result.run.outcome.validation_results
        == ()
    )


def test_successful_execution_still_produces_success_outcome():
    result = make_executor().execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED

    assert result.run.execution is not None
    assert (
        result.run.execution.status
        is ExecutionStatus.SUCCEEDED
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.SUCCEEDED
    )


TESTS = [
    test_execution_failure_produces_task_outcome,
    test_infrastructure_execution_failure_produces_task_outcome,
    test_execution_failure_outcome_has_no_uncomputed_post_execution_results,
    test_successful_execution_still_produces_success_outcome,
]


def main():
    print("=" * 70)
    print("EXECUTION OUTCOME TESTS")
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
            "EXECUTION OUTCOME: PASS"
        )
    else:
        print(
            "EXECUTION OUTCOME: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())