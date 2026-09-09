from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    ExpectedCondition,
    ExpectedKind,
)

from runtime.assertions import (
    AssertionEvaluator,
    AssertionObservationRequirement,
    AssertionRegistry,
    AssertionResultStatus,
    AssertionSpec,
)

from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceStore,
)

from runtime.expected import (
    ExpectedEvaluationStatus,
    ExpectedEvaluator,
)


def make_evidence(
    evidence_id: str,
    *,
    task_id: str = "task-evaluation",
    kind: EvidenceKind = EvidenceKind.STATE,
    status: EvidenceStatus = EvidenceStatus.VALID,
    value: object | None = None,
) -> Evidence:
    if value is None:
        value = {
            "property": "runtime.ready",
            "value": True,
        }

    return Evidence(
        evidence_id=evidence_id,
        task_id=task_id,
        kind=kind,
        status=status,
        value=value,
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="evaluation",
        ),
        timestamp="runtime",
    )


def make_state_expected(
    expected_value: object,
) -> ExpectedCondition:
    return ExpectedCondition(
        id="expected.runtime.ready",
        kind=ExpectedKind.STATE,
        identifier="runtime.ready",
        version=1,
        parameters={
            "property": "runtime.ready",
            "operator": "EQUALS",
            "expected_value": expected_value,
        },
    )


def make_test_expected(
    expected_status: str,
) -> ExpectedCondition:
    return ExpectedCondition(
        id="expected.test.status",
        kind=ExpectedKind.TEST,
        identifier="test.status",
        version=1,
        parameters={
            "status": expected_status,
        },
    )


def test_valid_state_evidence_satisfies_expected() -> None:
    store = EvidenceStore("task-evaluation")

    evidence = make_evidence(
        "evidence.state.1",
    )

    store.add(evidence)

    evaluation = ExpectedEvaluator.evaluate_one(
        make_state_expected(True),
        store,
    )

    assert evaluation.status is (
        ExpectedEvaluationStatus.SATISFIED
    )

    assert evaluation.evidence_ids == (
        "evidence.state.1",
    )


def test_invalid_state_evidence_is_not_available_to_expected() -> None:
    store = EvidenceStore("task-evaluation")

    evidence = make_evidence(
        "evidence.state.1",
        status=EvidenceStatus.INVALID,
    )

    store.add(evidence)

    evaluation = ExpectedEvaluator.evaluate_one(
        make_state_expected(True),
        store,
    )

    assert evaluation.status is (
        ExpectedEvaluationStatus.UNAVAILABLE
    )

    assert evaluation.evidence_ids == ()


def test_error_test_evidence_cannot_satisfy_expected() -> None:
    store = EvidenceStore("task-evaluation")

    evidence = make_evidence(
        "evidence.test.1",
        kind=EvidenceKind.TEST,
        status=EvidenceStatus.ERROR,
        value={
            "status": "PASSED",
        },
    )

    store.add(evidence)

    evaluation = ExpectedEvaluator.evaluate_one(
        make_test_expected("PASSED"),
        store,
    )

    assert evaluation.status is (
        ExpectedEvaluationStatus.UNAVAILABLE
    )

    assert evaluation.evidence_ids == ()


def test_assertion_requires_valid_required_observation() -> None:
    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="runtime.ready.assertion",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="runtime.ready",
                ),
            ),
            evaluator=lambda evidence: True,
        )
    )

    evaluator = AssertionEvaluator(registry)

    store = EvidenceStore("task-evaluation")

    evidence = make_evidence(
        "evidence.state.1",
    )

    store.add(evidence)

    result = evaluator.evaluate(
        "runtime.ready.assertion",
        1,
        store,
    )

    assert result.status is AssertionResultStatus.PASS
    assert result.evidence_ids == (
        "evidence.state.1",
    )


def test_assertion_does_not_use_invalid_required_observation() -> None:
    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="runtime.ready.assertion",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="runtime.ready",
                ),
            ),
            evaluator=lambda evidence: True,
        )
    )

    evaluator = AssertionEvaluator(registry)

    store = EvidenceStore("task-evaluation")

    evidence = make_evidence(
        "evidence.state.1",
        status=EvidenceStatus.INVALID,
    )

    store.add(evidence)

    result = evaluator.evaluate(
        "runtime.ready.assertion",
        1,
        store,
    )

    assert result.status is AssertionResultStatus.UNAVAILABLE
    assert result.evidence_ids == ()


def test_assertion_evaluator_does_not_modify_evidence_store() -> None:
    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="runtime.ready.assertion",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="runtime.ready",
                ),
            ),
            evaluator=lambda evidence: True,
        )
    )

    evaluator = AssertionEvaluator(registry)

    store = EvidenceStore("task-evaluation")

    evidence = make_evidence(
        "evidence.state.1",
    )

    store.add(evidence)

    before = store.list()

    result = evaluator.evaluate(
        "runtime.ready.assertion",
        1,
        store,
    )

    after = store.list()

    assert result.status is AssertionResultStatus.PASS
    assert before == after
    assert after[0] is evidence
    assert store.count() == 1
