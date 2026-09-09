from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from runtime.assertions import AssertionRegistry

from agent_task_v3 import (
    GoalKind,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TargetKind,
    TaskV3,
    ExpectedCondition,
    ExpectedKind,
)
from runtime.assertions import (
    AssertionRegistry,
    AssertionSpec,
)
from runtime.expected import ExpectedEvaluationStatus
from runtime.task_outcome import TaskOutcomeStatus
from registries.goal_registry import (
    GoalRegistry,
    GoalSpec,
)
from registries.handler_registry import (
    HandlerApplicability,
    HandlerRegistry,
    HandlerSpec,
)
from registries.handler_resolver import (
    HandlerRuntimeContext,
)
from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)
from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceStatus,
)
from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
    PreconditionStatus,
)
from runtime.task_run import (
    TaskRunStatus,
)
from runtime.task_run_executor import (
    TaskRunExecutor,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


def make_task() -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp"
        ),
    )

    goal = TaskGoal(
        identifier=GOAL_ID,
        kind=GoalKind.OUTCOME,
        version=GOAL_VERSION,
        parameters={},
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id="task-run-executor-test",
        description="Execute a complete TaskRun.",
        intent=intent,
    )


def make_executor(
    target_directory: TargetDirectory | None = None,
    handler_registry: HandlerRegistry | None = None,
) -> TaskRunExecutor:
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract=(
                "Add the generic component API."
            ),
            owner="PROJECT",
        )
    )

    directory = (
        target_directory
        or make_target_directory()
    )

    handlers = (
        handler_registry
        or make_handler_registry()
    )

    precondition_registry = PreconditionRegistry()
    precondition_evaluator = PreconditionEvaluator(
        precondition_registry
    )
    assertion_registry = AssertionRegistry()

    return TaskRunExecutor(
        goal_registry,
        directory,
        handlers,
        precondition_evaluator,
        assertion_registry,
    )


def make_target_directory() -> TargetDirectory:
    directory = TargetDirectory()

    directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    return directory


def make_handler_registry() -> HandlerRegistry:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    return registry


def test_complete_run_reaches_completed() -> None:
    executor = make_executor()

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: handler},
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED
    assert result.run.execution is not None
    assert result.run.execution.succeeded
    assert result.run.outcome is not None
    assert result.run.outcome.succeeded
    assert calls == ["step.1"]


def test_complete_run_has_execution_evidence() -> None:
    executor = make_executor()

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: lambda step: None},
    )

    assert result.completed
    assert result.run.evidence is not None
    assert result.run.evidence.count() == 1

    evidence = result.run.evidence.get(
        "evidence.execution.1"
    )

    assert evidence is not None
    assert evidence.kind is EvidenceKind.EXECUTION
    assert evidence.status is EvidenceStatus.VALID
    assert evidence.task_id == result.run.task_id


def test_resolution_failure_stops_run() -> None:
    executor = make_executor(
        target_directory=TargetDirectory()
    )

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: lambda step: None},
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.resolution is not None
    assert result.run.execution_plan is None
    assert result.run.execution is None


def test_planning_is_not_reached_after_resolution_failure() -> None:
    executor = make_executor(
        target_directory=TargetDirectory()
    )

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: lambda step: None},
    )

    assert result.run.history == [
        TaskRunStatus.CREATED,
        TaskRunStatus.VALIDATING,
        TaskRunStatus.RESOLVING,
        TaskRunStatus.FAILED,
    ]


def test_failed_precondition_blocks_execution() -> None:
    executor = make_executor()

    from agent_task_v3 import Precondition

    precondition = Precondition(
        id="pc.runtime.ready",
        kind="STATE",
        identifier="runtime.ready",
        version=1,
        parameters={},
    )

    precondition_registry = PreconditionRegistry()

    precondition_registry.register(
        "runtime.ready",
        1,
        lambda precondition, context:
            PreconditionStatus.FAILED,
    )

    executor._precondition_evaluator = PreconditionEvaluator(
        precondition_registry
    )

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: handler},
        runtime_safety_preconditions=(
            precondition,
        ),
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED
    assert (
        result.run.status
        is TaskRunStatus.FAILED
    )
    assert result.run.execution is None
    assert calls == []


def test_execution_failure_stops_before_post_execution() -> None:
    executor = make_executor()

    def failing_handler(step):
        raise RuntimeError("execution failed")

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: failing_handler},
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.execution is not None
    assert not result.run.execution.succeeded
    assert TaskRunStatus.POST_EXECUTION not in (
        result.run.history
    )


def test_post_execution_evidence_producer_is_used() -> None:
    executor = make_executor()

    def producer(run):
        yield Evidence(
            evidence_id="evidence.test.1",
            task_id=run.task_id,
            kind=EvidenceKind.TEST,
            status=EvidenceStatus.VALID,
            value={
                "status": "PASSED",
            },
            provenance=EvidenceProvenance(
                source_kind="test.runtime",
                source_id="integration",
            ),
            timestamp="runtime",
        )

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: lambda step: None},
        evidence_producers=(producer,),
    )

    assert result.completed
    assert result.run.evidence is not None
    assert result.run.evidence.count() == 2
    assert result.run.evidence.get(
        "evidence.test.1"
    ) is not None


def test_bad_evidence_producer_fails_run() -> None:
    executor = make_executor()

    def producer(run):
        raise RuntimeError("producer failure")

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: lambda step: None},
        evidence_producers=(producer,),
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED


def test_expected_and_validation_results_are_attached() -> None:
    """
    This test uses no explicit expected/validation requirements.
    Their result collections must nevertheless be available on the run.
    """
    executor = make_executor()

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: lambda step: None},
    )

    assert result.completed
    assert result.run.expected_evaluations == ()
    assert result.run.validation_results == ()


def test_outcome_is_attached_to_run() -> None:
    executor = make_executor()

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: lambda step: None},
    )

    assert result.run.outcome is not None
    assert result.run.outcome.execution is (
        result.run.execution
    )


def test_task_identity_is_preserved_across_pipeline() -> None:
    executor = make_executor()
    task = make_task()

    result = executor.execute(
        task,
        handlers={HANDLER_ID: lambda step: None},
    )

    assert result.run.task is task

    if result.run.resolution is not None:
        assert result.run.resolution.task is task

    if result.run.execution_plan is not None:
        assert result.run.execution_plan.task is task

    if result.run.execution is not None:
        assert result.run.execution.plan.task is task


def test_full_history_is_recorded() -> None:
    executor = make_executor()

    result = executor.execute(
        make_task(),
        handlers={HANDLER_ID: lambda step: None},
    )

    assert result.completed

    assert result.run.history == [
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


def test_executor_does_not_mutate_task() -> None:
    executor = make_executor()

    task = make_task()

    before = (
        task.schema_version,
        task.task_id,
        task.description,
        task.intent,
        task.preconditions,
        task.expected,
        task.validation,
    )

    executor.execute(
        task,
        handlers={HANDLER_ID: lambda step: None},
    )

    after = (
        task.schema_version,
        task.task_id,
        task.description,
        task.intent,
        task.preconditions,
        task.expected,
        task.validation,
    )

    assert before == after

def make_task_with_expected(
    expected: ExpectedCondition,
) -> TaskV3:
    task = make_task()

    return TaskV3(
        schema_version=task.schema_version,
        task_id=task.task_id,
        description=task.description,
        intent=task.intent,
        preconditions=task.preconditions,
        expected=(expected,),
        validation=task.validation,
        execution_policy=task.execution_policy,
    )
def test_assertion_expected_uses_unified_evaluation() -> None:
    assertion_registry = AssertionRegistry()

    assertion_registry.register(
        AssertionSpec(
            identifier="execution.succeeded",
            version=1,
            evaluator=lambda evidence: True,
        )
    )

    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
        )
    )

    executor = TaskRunExecutor(
        goal_registry,
        make_target_directory(),
        make_handler_registry(),
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        assertion_registry,
    )

    task = make_task_with_expected(
        ExpectedCondition(
            id="expected.assertion",
            kind=ExpectedKind.ASSERTION,
            identifier="execution.succeeded",
            version=1,
            parameters={},
        )
    )

    result = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed
    assert len(result.run.expected_evaluations) == 1
    assert (
        result.run.expected_evaluations[0].status
        is ExpectedEvaluationStatus.SATISFIED
    )
    assert result.run.outcome is not None
    assert result.run.outcome.succeeded


def test_changeset_expected_uses_unified_evaluation() -> None:
    executor = make_executor()

    task = make_task_with_expected(
        ExpectedCondition(
            id="expected.changes",
            kind=ExpectedKind.CHANGESET,
            identifier="project.changes",
            version=1,
            parameters={
                "mode": "EXACT",
                "required": [
                    {
                        "kind": "ADDED",
                        "path": "src/new.cpp",
                    }
                ],
                "allowed": [],
                "forbidden": [],
            },
        )
    )

    def producer(run):
        yield Evidence(
            evidence_id="evidence.changeset.1",
            task_id=run.task_id,
            kind=EvidenceKind.CHANGESET,
            status=EvidenceStatus.VALID,
            value={
                "changes": [
                    {
                        "kind": "ADDED",
                        "path": "src/new.cpp",
                    }
                ]
            },
            provenance=EvidenceProvenance(
                source_kind="changeset.runtime",
                source_id="changeset",
            ),
            timestamp="runtime",
        )

    result = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None
        },
        evidence_producers=(producer,),
    )

    assert result.completed
    assert len(result.run.expected_evaluations) == 1
    assert (
        result.run.expected_evaluations[0].status
        is ExpectedEvaluationStatus.SATISFIED
    )
    assert result.run.outcome is not None
    assert result.run.outcome.succeeded


def test_failed_changeset_reaches_task_outcome() -> None:
    executor = make_executor()

    task = make_task_with_expected(
        ExpectedCondition(
            id="expected.changes",
            kind=ExpectedKind.CHANGESET,
            identifier="project.changes",
            version=1,
            parameters={
                "mode": "EXACT",
                "required": [
                    {
                        "kind": "ADDED",
                        "path": "src/required.cpp",
                    }
                ],
                "allowed": [],
                "forbidden": [],
            },
        )
    )

    def producer(run):
        yield Evidence(
            evidence_id="evidence.changeset.1",
            task_id=run.task_id,
            kind=EvidenceKind.CHANGESET,
            status=EvidenceStatus.VALID,
            value={
                "changes": [
                    {
                        "kind": "ADDED",
                        "path": "src/other.cpp",
                    }
                ]
            },
            provenance=EvidenceProvenance(
                source_kind="changeset.runtime",
                source_id="changeset",
            ),
            timestamp="runtime",
        )

    result = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None
        },
        evidence_producers=(producer,),
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    assert len(result.run.expected_evaluations) == 1
    assert (
        result.run.expected_evaluations[0].status
        is ExpectedEvaluationStatus.NOT_SATISFIED
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.EXPECTED_NOT_SATISFIED
    )
def main() -> int:
    tests = [
        test_complete_run_reaches_completed,
        test_complete_run_has_execution_evidence,
        test_resolution_failure_stops_run,
        test_planning_is_not_reached_after_resolution_failure,
        test_failed_precondition_blocks_execution,
        test_execution_failure_stops_before_post_execution,
        test_post_execution_evidence_producer_is_used,
        test_bad_evidence_producer_fails_run,
        test_expected_and_validation_results_are_attached,
        test_outcome_is_attached_to_run,
        test_task_identity_is_preserved_across_pipeline,
        test_full_history_is_recorded,
        test_executor_does_not_mutate_task,
        test_assertion_expected_uses_unified_evaluation,
        test_changeset_expected_uses_unified_evaluation,
        test_failed_changeset_reaches_task_outcome,
    ]

    print("=" * 70)
    print("TASK RUN EXECUTOR TESTS")
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
        print("TASK RUN EXECUTOR: PASS")
    else:
        print("TASK RUN EXECUTOR: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())