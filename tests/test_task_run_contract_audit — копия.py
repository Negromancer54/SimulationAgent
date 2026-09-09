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
    Precondition,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    TargetKind,
    ValidationSpec,
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
    PreconditionStatus,
)
from runtime.task_run import (
    TaskRun,
    TaskRunStatus,
)
from runtime.task_run_executor import (
    TaskRunExecutor,
)
from runtime.task_outcome import (
    TaskOutcomeStatus,
)
from runtime.expected import (
    ExpectedEvaluationStatus,
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


# ============================================================================
# Helpers
# ============================================================================

def make_task(
    *,
    task_id: str = "task-run-contract-audit",
    expected=None,
    validation=None,
    preconditions=None,
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
        task_id=task_id,
        description="TaskRun runtime contract audit.",
        intent=intent,
        preconditions=list(preconditions or []),
        expected=list(expected or []),
        validation=list(validation or []),
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


def make_executor(
    *,
    precondition_registry: PreconditionRegistry | None = None,
    assertion_registry: AssertionRegistry | None = None,
    target_directory: TargetDirectory | None = None,
) -> TaskRunExecutor:
    if precondition_registry is None:
        precondition_registry = PreconditionRegistry()

    if assertion_registry is None:
        assertion_registry = AssertionRegistry()

    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="TaskRun contract audit.",
            owner="PROJECT",
        )
    )

    return TaskRunExecutor(
        goal_registry,
        target_directory or make_target_directory(),
        make_handler_registry(),
        PreconditionEvaluator(
            precondition_registry
        ),
        assertion_registry,
    )


def successful_handler(calls: list[str]):
    def handler(step):
        calls.append(step.step_id)

    return handler


# ============================================================================
# AUDIT-01
# ============================================================================

def test_valid_lifecycle_has_expected_phase_order():
    calls: list[str] = []

    result = make_executor().execute(
        make_task(),
        handlers={
            HANDLER_ID: successful_handler(calls)
        },
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
    assert calls == ["step.1"]


# ============================================================================
# AUDIT-02
# ============================================================================

def test_invalid_transition_does_not_modify_run():
    run = TaskRun(
        task=make_task()
    )

    run.transition(
        TaskRunStatus.VALIDATING
    )

    previous_status = run.status
    previous_history = list(run.history)

    try:
        run.transition(
            TaskRunStatus.EXECUTING
        )
    except Exception:
        pass
    else:
        raise AssertionError(
            "Invalid TaskRun transition was accepted."
        )

    assert run.status is previous_status
    assert run.history == previous_history


# ============================================================================
# AUDIT-03
# ============================================================================

def test_failed_precondition_prevents_execution():
    precondition_registry = PreconditionRegistry()

    precondition_registry.register(
        "runtime.ready",
        1,
        lambda precondition, context:
            PreconditionStatus.FAILED,
    )

    executor = make_executor(
        precondition_registry=precondition_registry
    )

    precondition = Precondition(
        id="pc.runtime.ready",
        kind=ExpectedKind.STATE,
        identifier="runtime.ready",
        version=1,
        parameters={},
    )

    calls: list[str] = []

    result = executor.execute(
        make_task(
            preconditions=[precondition]
        ),
        handlers={
            HANDLER_ID: successful_handler(calls)
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.preconditions is not None
    assert not result.run.preconditions.satisfied
    assert result.run.execution is None
    assert result.run.outcome is None
    assert calls == []


# ============================================================================
# AUDIT-04
# ============================================================================

def test_handler_failure_is_not_reported_as_resolution_failure():
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

    # Resolution must succeed: the handler was found and selected.
    assert result.run.resolution is not None
    assert (
        result.run.resolution.status.name
        == "RESOLVED"
    )

    assert (
        result.run.resolution.handler_resolution
        is not None
    )

    assert (
        result.run.resolution.handler_resolution.status.name
        == "FOUND"
    )

    # The failure must occur at the execution layer.
    assert result.run.execution is not None
    assert (
        result.run.execution.status.name
        == "FAILED"
    )

    # The TaskRun must become terminal FAILED.
    assert (
        result.run.status
        is TaskRunStatus.FAILED
    )

    # Execution must have been reached; POST_EXECUTION must not be reached.
    assert (
        TaskRunStatus.EXECUTING
        in result.run.history
    )

    assert (
        TaskRunStatus.POST_EXECUTION
        not in result.run.history
    )

# ============================================================================
# AUDIT-05
# ============================================================================

def test_execution_evidence_is_recorded_only_after_successful_execution():
    successful_result = make_executor().execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert successful_result.run.evidence is not None
    assert successful_result.run.evidence.count() == 1

    execution_evidence = (
        successful_result.run.evidence.get(
            "evidence.execution.1"
        )
    )

    assert execution_evidence is not None
    assert execution_evidence.kind is EvidenceKind.EXECUTION
    assert execution_evidence.status is EvidenceStatus.VALID

    def failing_handler(step):
        raise RuntimeError(
            "execution failed"
        )

    failed_result = make_executor().execute(
        make_task(),
        handlers={
            HANDLER_ID: failing_handler
        },
    )

    assert failed_result.run.evidence is not None
    assert (
        failed_result.run.evidence.count()
        == 0
    )


# ============================================================================
# AUDIT-06
# ============================================================================

def test_evidence_cannot_cross_task_run_boundaries():
    result = make_executor().execute(
        make_task(
            task_id="audit.task.a"
        ),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    run_a = result.run

    run_b = TaskRun(
        task=make_task(
            task_id="audit.task.b"
        )
    )

    assert run_a.evidence is not None
    assert run_b.evidence is not None

    evidence = run_a.evidence.get(
        "evidence.execution.1"
    )

    assert evidence is not None

    try:
        run_b.evidence.add(
            evidence
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Evidence from another TaskRun was accepted."
        )


# ============================================================================
# AUDIT-07
# ============================================================================

def test_expected_evaluation_does_not_modify_evidence():
    assertion_registry = AssertionRegistry()

    assertion_registry.register(
        AssertionSpec(
            identifier="execution.succeeded",
            version=1,
            evaluator=lambda evidence: True,
        )
    )

    executor = make_executor(
        assertion_registry=assertion_registry
    )

    expected = ExpectedCondition(
        id="expected.assertion",
        kind=ExpectedKind.ASSERTION,
        identifier="execution.succeeded",
        version=1,
        parameters={},
    )

    result = executor.execute(
        make_task(
            expected=[expected]
        ),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    evidence = result.run.evidence

    assert evidence is not None

    before = evidence.list()

    assert len(
        result.run.expected_evaluations
    ) == 1

    after = evidence.list()

    assert before == after


# ============================================================================
# AUDIT-08
# ============================================================================

def test_validation_does_not_modify_evidence():
    validation = ValidationSpec(
        id="validation.execution",
        identifier="runtime.validation",
        version=1,
        applies_to=[
            "execution.runtime"
        ],
        evidence_requirements=[
            EvidenceRequirement(
                source_kind="execution.runtime",
                freshness="CURRENT",
            ),
        ],
    )

    result = make_executor().execute(
        make_task(
            validation=[validation]
        ),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    evidence = result.run.evidence

    assert evidence is not None

    before = evidence.list()

    assert len(
        result.run.validation_results
    ) == 1

    after = evidence.list()

    assert before == after


# ============================================================================
# AUDIT-09
# ============================================================================
# Semantic Expected failure is tested with a real CHANGESET evidence,
# because TEST Expected requires TEST evidence.
# ============================================================================

def test_expected_failure_reaches_task_outcome():
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
                    "path": "src/required.cpp",
                }
            ],
            "allowed": [],
            "forbidden": [],
        },
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

    result = make_executor().execute(
        make_task(
            expected=[expected]
        ),
        handlers={
            HANDLER_ID: lambda step: None
        },
        evidence_producers=(producer,),
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    assert len(
        result.run.expected_evaluations
    ) == 1

    assert (
        result.run.expected_evaluations[0].status
        is ExpectedEvaluationStatus.NOT_SATISFIED
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.EXPECTED_NOT_SATISFIED
    )


# ============================================================================
# AUDIT-10
# ============================================================================

def test_validation_insufficiency_reaches_task_outcome():
    validation = ValidationSpec(
        id="validation.missing",
        identifier="runtime.validation.missing",
        version=1,
        applies_to=[
            "missing.source"
        ],
        evidence_requirements=[
            EvidenceRequirement(
                source_kind="missing.source",
                freshness="CURRENT",
            ),
        ],
    )

    result = make_executor().execute(
        make_task(
            validation=[validation]
        ),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED

    assert len(
        result.run.validation_results
    ) == 1

    assert (
        result.run.validation_results[0].status.name
        == "INSUFFICIENT"
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.VALIDATION_INSUFFICIENT
    )


# ============================================================================
# AUDIT-11
# ============================================================================

def test_expected_and_validation_are_independent():
    assertion_registry = AssertionRegistry()

    assertion_registry.register(
        AssertionSpec(
            identifier="execution.succeeded",
            version=1,
            evaluator=lambda evidence: True,
        )
    )

    expected = ExpectedCondition(
        id="expected.assertion",
        kind=ExpectedKind.ASSERTION,
        identifier="execution.succeeded",
        version=1,
        parameters={},
    )

    validation = ValidationSpec(
        id="validation.missing",
        identifier="runtime.validation.missing",
        version=1,
        applies_to=[
            "missing.source"
        ],
        evidence_requirements=[
            EvidenceRequirement(
                source_kind="missing.source",
                freshness="CURRENT",
            ),
        ],
    )

    result = make_executor(
        assertion_registry=assertion_registry
    ).execute(
        make_task(
            expected=[expected],
            validation=[validation],
        ),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert len(
        result.run.expected_evaluations
    ) == 1

    assert (
        result.run.expected_evaluations[0].status
        is ExpectedEvaluationStatus.SATISFIED
    )

    assert len(
        result.run.validation_results
    ) == 1

    assert (
        result.run.validation_results[0].status.name
        == "INSUFFICIENT"
    )

    assert result.run.outcome is not None
    assert (
        result.run.outcome.status
        is TaskOutcomeStatus.VALIDATION_INSUFFICIENT
    )


# ============================================================================
# AUDIT-12
# ============================================================================

def test_terminal_state_matches_outcome_and_executor_result():
    success_result = make_executor().execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None
        },
    )

    assert success_result.completed
    assert success_result.run.status is TaskRunStatus.COMPLETED
    assert success_result.run.outcome is not None
    assert (
        success_result.run.outcome.status
        is TaskOutcomeStatus.SUCCEEDED
    )
    assert success_result.run.successful

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
                    "path": "src/required.cpp",
                }
            ],
            "allowed": [],
            "forbidden": [],
        },
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

    failure_result = make_executor().execute(
        make_task(
            expected=[expected]
        ),
        handlers={
            HANDLER_ID: lambda step: None
        },
        evidence_producers=(producer,),
    )

    assert not failure_result.completed
    assert failure_result.run.status is TaskRunStatus.FAILED
    assert failure_result.run.outcome is not None
    assert (
        failure_result.run.outcome.status
        is TaskOutcomeStatus.EXPECTED_NOT_SATISFIED
    )
    assert not failure_result.run.successful


# ============================================================================
# Runner
# ============================================================================

TESTS = [
    test_valid_lifecycle_has_expected_phase_order,
    test_invalid_transition_does_not_modify_run,
    test_failed_precondition_prevents_execution,
    test_handler_failure_is_not_reported_as_resolution_failure,
    test_execution_evidence_is_recorded_only_after_successful_execution,
    test_evidence_cannot_cross_task_run_boundaries,
    test_expected_evaluation_does_not_modify_evidence,
    test_validation_does_not_modify_evidence,
    test_expected_failure_reaches_task_outcome,
    test_validation_insufficiency_reaches_task_outcome,
    test_expected_and_validation_are_independent,
    test_terminal_state_matches_outcome_and_executor_result,
]


def main() -> int:
    print("=" * 70)
    print("TASK RUN CONTRACT AUDIT")
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
            "TASK RUN CONTRACT AUDIT: PASS"
        )
    else:
        print(
            "TASK RUN CONTRACT AUDIT: FAIL"
        )

    print("=" * 70)

    return (
        0
        if passed == len(TESTS)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())