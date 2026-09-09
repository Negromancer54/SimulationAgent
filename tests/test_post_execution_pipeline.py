from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    EvidenceRequirement,
    ExpectedCondition,
    ExpectedKind,
    GoalKind,
    TargetKind,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    ValidationSpec,
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
from registries.handler_resolver import (
    HandlerRuntimeContext,
)
from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)

from runtime.assertions import (
    AssertionRegistry,
    AssertionSpec,
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


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


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


def make_goal_registry() -> GoalRegistry:
    registry = GoalRegistry()

    registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="Add the generic component API.",
            owner="PROJECT",
        )
    )

    return registry


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


def make_executor(
    assertion_registry: AssertionRegistry | None = None,
) -> TaskRunExecutor:
    return TaskRunExecutor(
        make_goal_registry(),
        make_target_directory(),
        make_handler_registry(),
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        assertion_registry
        or AssertionRegistry(),
    )


def make_task(
    expected: tuple[ExpectedCondition, ...] = (),
    validation: tuple[ValidationSpec, ...] = (),
) -> TaskV3:
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
        task_id="post-execution-pipeline-test",
        description="Test the post-execution V3 pipeline.",
        intent=intent,
        expected=expected,
        validation=validation,
    )


def make_validation(
    validation_id: str = "validation.execution",
    source_kind: str = "execution.runtime",
) -> ValidationSpec:
    return ValidationSpec(
        id=validation_id,
        identifier="execution.evidence",
        version=1,
        applies_to=None,
        evidence_requirements=(
            EvidenceRequirement(
                source_kind=source_kind,
                freshness="CURRENT",
            ),
        ),
    )


def state_expected(
    expected_id: str = "expected.state",
    expected_value: bool = True,
) -> ExpectedCondition:
    return ExpectedCondition(
        id=expected_id,
        kind=ExpectedKind.STATE,
        identifier="project.exists",
        version=1,
        parameters={
            "property": "project.exists",
            "operator": "EQUALS",
            "expected_value": expected_value,
        },
    )


def test_expected_state_and_validation_both_succeed() -> None:
    executor = make_executor()

    task = make_task(
        expected=(
            state_expected(),
        ),
        validation=(
            make_validation(),
        ),
    )

    def producer(run):
        yield Evidence(
            evidence_id="evidence.state.1",
            task_id=run.task_id,
            kind=EvidenceKind.STATE,
            status=EvidenceStatus.VALID,
            value={
                "property": "project.exists",
                "value": True,
            },
            provenance=EvidenceProvenance(
                source_kind="state.provider",
                source_id="project",
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
    assert result.run.status is TaskRunStatus.COMPLETED

    assert len(result.run.expected_evaluations) == 1
    assert result.run.expected_evaluations[0].satisfied

    assert len(result.run.validation_results) == 1
    assert result.run.validation_results[0].valid

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.SUCCEEDED
    )


def test_test_expected_and_validation_both_succeed() -> None:
    executor = make_executor()

    expected = ExpectedCondition(
        id="expected.test",
        kind=ExpectedKind.TEST,
        identifier="integration.test",
        version=1,
        parameters={
            "status": "PASSED",
        },
    )

    task = make_task(
        expected=(expected,),
        validation=(
            make_validation(),
        ),
    )

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
        task,
        handlers={
            HANDLER_ID: lambda step: None
        },
        evidence_producers=(producer,),
    )

    assert result.completed
    assert result.run.expected_evaluations[0].satisfied
    assert result.run.validation_results[0].valid
    assert result.run.outcome is not None
    assert result.run.outcome.succeeded


def test_assertion_expected_and_validation_both_succeed() -> None:
    assertion_registry = AssertionRegistry()

    assertion_registry.register(
        AssertionSpec(
            identifier="project.state.valid",
            version=1,
            required_observations=(),
            evaluator=lambda evidence: True,
        )
    )

    executor = make_executor(
        assertion_registry=assertion_registry,
    )

    expected = ExpectedCondition(
        id="expected.assertion",
        kind=ExpectedKind.ASSERTION,
        identifier="project.state.valid",
        version=1,
        parameters={},
    )

    task = make_task(
        expected=(expected,),
        validation=(
            make_validation(),
        ),
    )

    result = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert result.completed
    assert (
        result.run.expected_evaluations[0].satisfied
    )
    assert result.run.validation_results[0].valid
    assert result.run.outcome is not None
    assert result.run.outcome.succeeded


def test_changeset_expected_and_validation_both_succeed() -> None:
    executor = make_executor()

    expected = ExpectedCondition(
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

    task = make_task(
        expected=(expected,),
        validation=(
            make_validation(),
        ),
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
    assert (
        result.run.expected_evaluations[0].satisfied
    )
    assert result.run.validation_results[0].valid
    assert result.run.outcome is not None
    assert result.run.outcome.succeeded


def test_unsatisfied_expected_is_preserved_as_semantic_failure() -> None:
    executor = make_executor()

    task = make_task(
        expected=(
            state_expected(
                expected_value=True,
            ),
        ),
        validation=(
            make_validation(),
        ),
    )

    def producer(run):
        yield Evidence(
            evidence_id="evidence.state.1",
            task_id=run.task_id,
            kind=EvidenceKind.STATE,
            status=EvidenceStatus.VALID,
            value={
                "property": "project.exists",
                "value": False,
            },
            provenance=EvidenceProvenance(
                source_kind="state.provider",
                source_id="project",
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

    assert (
        result.run.expected_evaluations[0].status.value
        == "NOT_SATISFIED"
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.EXPECTED_NOT_SATISFIED
    )


def test_insufficient_validation_is_preserved() -> None:
    executor = make_executor()

    task = make_task(
        expected=(
            state_expected(),
        ),
        validation=(
            make_validation(
                source_kind="missing.validation.source"
            ),
        ),
    )

    def producer(run):
        yield Evidence(
            evidence_id="evidence.state.1",
            task_id=run.task_id,
            kind=EvidenceKind.STATE,
            status=EvidenceStatus.VALID,
            value={
                "property": "project.exists",
                "value": True,
            },
            provenance=EvidenceProvenance(
                source_kind="state.provider",
                source_id="project",
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

    assert result.run.expected_evaluations[0].satisfied
    assert (
        result.run.validation_results[0].status.value
        == "INSUFFICIENT"
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.VALIDATION_INSUFFICIENT
    )


def test_expected_and_validation_are_independent_consumers() -> None:
    executor = make_executor()

    task = make_task(
        expected=(
            state_expected(),
        ),
        validation=(
            make_validation(
                validation_id="validation.execution"
            ),
        ),
    )

    def producer(run):
        yield Evidence(
            evidence_id="evidence.state.1",
            task_id=run.task_id,
            kind=EvidenceKind.STATE,
            status=EvidenceStatus.VALID,
            value={
                "property": "project.exists",
                "value": True,
            },
            provenance=EvidenceProvenance(
                source_kind="state.provider",
                source_id="project",
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

    expected_result = (
        result.run.expected_evaluations[0]
    )
    validation_result = (
        result.run.validation_results[0]
    )

    assert expected_result.satisfied
    assert validation_result.valid

    assert (
        "evidence.state.1"
        in expected_result.evidence_ids
    )

    # Validation uses the independently produced execution evidence.
    assert (
        "evidence.execution.1"
        in validation_result.evidence_ids
    )

    # Neither evaluator depends on the other evaluator's output.
    assert expected_result is not validation_result


def test_final_outcome_requires_both_branches() -> None:
    executor = make_executor()

    task = make_task(
        expected=(
            state_expected(),
        ),
        validation=(
            make_validation(),
        ),
    )

    result = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None
        },
        evidence_producers=(
            lambda run: (
                Evidence(
                    evidence_id="evidence.state.1",
                    task_id=run.task_id,
                    kind=EvidenceKind.STATE,
                    status=EvidenceStatus.VALID,
                    value={
                        "property": "project.exists",
                        "value": True,
                    },
                    provenance=EvidenceProvenance(
                        source_kind="state.provider",
                        source_id="project",
                    ),
                    timestamp="runtime",
                ),
            ),
        ),
    )

    assert result.completed
    assert result.run.outcome is not None
    assert result.run.outcome.succeeded

    assert result.run.execution is not None
    assert result.run.execution.succeeded

    assert all(
        evaluation.satisfied
        for evaluation in result.run.expected_evaluations
    )

    assert all(
        validation.valid
        for validation in result.run.validation_results
    )


def main() -> int:
    tests = [
        test_expected_state_and_validation_both_succeed,
        test_test_expected_and_validation_both_succeed,
        test_assertion_expected_and_validation_both_succeed,
        test_changeset_expected_and_validation_both_succeed,
        test_unsatisfied_expected_is_preserved_as_semantic_failure,
        test_insufficient_validation_is_preserved,
        test_expected_and_validation_are_independent_consumers,
        test_final_outcome_requires_both_branches,
    ]

    print("=" * 70)
    print("POST-EXECUTION PIPELINE TESTS")
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
        print("POST-EXECUTION PIPELINE: PASS")
    else:
        print("POST-EXECUTION PIPELINE: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())