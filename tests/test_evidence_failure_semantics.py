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


def make_state_evidence(
    evidence_id: str,
    status: EvidenceStatus,
    *,
    value: object | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id="task-failure-semantics",
        kind=EvidenceKind.STATE,
        status=status,
        value=(
            value
            if value is not None
            else {
                "property": "runtime.ready",
                "value": True,
            }
        ),
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="failure-semantics",
        ),
        timestamp="runtime",
    )


def make_test_evidence(
    evidence_id: str,
    status: EvidenceStatus,
    observed_status: str,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id="task-failure-semantics",
        kind=EvidenceKind.TEST,
        status=status,
        value={
            "status": observed_status,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="failure-semantics",
        ),
        timestamp="runtime",
    )


def make_state_expected() -> ExpectedCondition:
    return ExpectedCondition(
        id="expected.runtime.ready",
        kind=ExpectedKind.STATE,
        identifier="runtime.ready",
        version=1,
        parameters={
            "property": "runtime.ready",
            "operator": "EQUALS",
            "expected_value": True,
        },
    )


def make_test_expected() -> ExpectedCondition:
    return ExpectedCondition(
        id="expected.test.status",
        kind=ExpectedKind.TEST,
        identifier="test.status",
        version=1,
        parameters={
            "status": "PASSED",
        },
    )


def make_assertion_registry(
    evaluator,
) -> AssertionRegistry:
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
            evaluator=evaluator,
        )
    )

    return registry


def test_invalid_state_evidence_becomes_unavailable() -> None:
    store = EvidenceStore("task-failure-semantics")

    store.add(
        make_state_evidence(
            "evidence.invalid",
            EvidenceStatus.INVALID,
        )
    )

    result = ExpectedEvaluator.evaluate_one(
        make_state_expected(),
        store,
    )

    assert result.status is ExpectedEvaluationStatus.UNAVAILABLE
    assert result.evidence_ids == ()


def test_error_state_evidence_becomes_unavailable() -> None:
    store = EvidenceStore("task-failure-semantics")

    store.add(
        make_state_evidence(
            "evidence.error",
            EvidenceStatus.ERROR,
        )
    )

    result = ExpectedEvaluator.evaluate_one(
        make_state_expected(),
        store,
    )

    assert result.status is ExpectedEvaluationStatus.UNAVAILABLE
    assert result.evidence_ids == ()


def test_unavailable_state_evidence_does_not_create_a_false_pass() -> None:
    store = EvidenceStore("task-failure-semantics")

    store.add(
        make_state_evidence(
            "evidence.unavailable",
            EvidenceStatus.UNAVAILABLE,
        )
    )

    result = ExpectedEvaluator.evaluate_one(
        make_state_expected(),
        store,
    )

    assert result.status is ExpectedEvaluationStatus.UNAVAILABLE
    assert not result.satisfied
    assert result.evidence_ids == ()


def test_invalid_test_evidence_with_matching_status_is_not_satisfied() -> None:
    store = EvidenceStore("task-failure-semantics")

    store.add(
        make_test_evidence(
            "evidence.test.invalid",
            EvidenceStatus.INVALID,
            "PASSED",
        )
    )

    result = ExpectedEvaluator.evaluate_one(
        make_test_expected(),
        store,
    )

    assert result.status is ExpectedEvaluationStatus.NOT_SATISFIED
    assert result.evidence_ids == (
        "evidence.test.invalid",
    )
    assert not result.satisfied


def test_assertion_required_error_evidence_is_unavailable() -> None:
    registry = make_assertion_registry(
        lambda evidence: True,
    )

    evaluator = AssertionEvaluator(registry)
    store = EvidenceStore("task-failure-semantics")

    store.add(
        make_state_evidence(
            "evidence.error",
            EvidenceStatus.ERROR,
        )
    )

    result = evaluator.evaluate(
        "runtime.ready.assertion",
        1,
        store,
    )

    assert result.status is AssertionResultStatus.UNAVAILABLE
    assert result.evidence_ids == ()
    assert not result.passed


def test_assertion_evaluator_error_becomes_error_result() -> None:
    registry = make_assertion_registry(
        lambda evidence: (_ for _ in ()).throw(
            RuntimeError("assertion failure")
        ),
    )

    evaluator = AssertionEvaluator(registry)
    store = EvidenceStore("task-failure-semantics")

    store.add(
        make_state_evidence(
            "evidence.valid",
            EvidenceStatus.VALID,
        )
    )

    result = evaluator.evaluate(
        "runtime.ready.assertion",
        1,
        store,
    )

    assert result.status is AssertionResultStatus.ERROR
    assert result.evidence_ids == (
        "evidence.valid",
    )
    assert not result.passed
