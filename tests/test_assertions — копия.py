from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


TASK_ID = "task-assertion-test"


def make_store() -> EvidenceStore:
    return EvidenceStore(TASK_ID)


def make_state_evidence(
    evidence_id: str,
    property_name: str,
    value,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id=TASK_ID,
        kind=EvidenceKind.STATE,
        status=EvidenceStatus.VALID,
        value={
            "property": property_name,
            "value": value,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="state-provider",
        ),
        timestamp="2026-09-08T16:00:00+03:00",
    )


def make_test_evidence(
    evidence_id: str,
    status: str,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id=TASK_ID,
        kind=EvidenceKind.TEST,
        status=EvidenceStatus.VALID,
        value={
            "status": status,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="test-runtime",
        ),
        timestamp="2026-09-08T16:00:00+03:00",
    )


def test_assertion_can_be_registered() -> None:
    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.ready",
            version=1,
            evaluator=lambda evidence: True,
        )
    )

    assert registry.contains(
        "project.ready",
        1,
    )

    assert registry.resolve(
        "project.ready",
        1,
    ) is not None


def test_duplicate_assertion_is_rejected() -> None:
    registry = AssertionRegistry()

    spec = AssertionSpec(
        identifier="project.ready",
        version=1,
        evaluator=lambda evidence: True,
    )

    registry.register(spec)

    try:
        registry.register(spec)
    except ValueError:
        return

    raise AssertionError(
        "Duplicate AssertionSpec registration was accepted."
    )


def test_assertion_versions_are_independent() -> None:
    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.ready",
            version=1,
            evaluator=lambda evidence: True,
        )
    )

    registry.register(
        AssertionSpec(
            identifier="project.ready",
            version=2,
            evaluator=lambda evidence: False,
        )
    )

    assert registry.list_versions(
        "project.ready"
    ) == [1, 2]


def test_assertion_passes() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.project",
            "project.exists",
            True,
        )
    )

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.exists",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="project.exists",
                ),
            ),
            evaluator=lambda evidence:
                evidence[0].value["value"] is True,
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "project.exists",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.PASS
    )
    assert result.passed
    assert result.evidence_ids == (
        "evidence.project",
    )


def test_assertion_fails() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.project",
            "project.exists",
            False,
        )
    )

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.exists",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="project.exists",
                ),
            ),
            evaluator=lambda evidence:
                evidence[0].value["value"] is True,
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "project.exists",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.FAIL
    )
    assert not result.passed


def test_missing_required_observation_is_unavailable() -> None:
    store = make_store()

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.exists",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="project.exists",
                ),
            ),
            evaluator=lambda evidence: True,
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "project.exists",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.UNAVAILABLE
    )
    assert not result.passed


def test_unknown_assertion_is_unavailable() -> None:
    store = make_store()
    registry = AssertionRegistry()

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "unknown.assertion",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.UNAVAILABLE
    )


def test_missing_evaluator_is_error() -> None:
    store = make_store()
    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="missing.implementation",
            version=1,
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "missing.implementation",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.ERROR
    )


def test_evaluator_exception_is_error() -> None:
    store = make_store()
    registry = AssertionRegistry()

    def failing_evaluator(evidence):
        raise RuntimeError("boom")

    registry.register(
        AssertionSpec(
            identifier="failing.assertion",
            version=1,
            evaluator=failing_evaluator,
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "failing.assertion",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.ERROR
    )
    assert "RuntimeError" in result.message


def test_non_boolean_evaluator_result_is_error() -> None:
    store = make_store()
    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="bad.assertion",
            version=1,
            evaluator=lambda evidence: "PASS",
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "bad.assertion",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.ERROR
    )


def test_test_evidence_can_be_required() -> None:
    store = make_store()

    store.add(
        make_test_evidence(
            "evidence.test",
            "PASSED",
        )
    )

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="integration.ok",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.TEST,
                ),
            ),
            evaluator=lambda evidence:
                evidence[0].value["status"] == "PASSED",
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "integration.ok",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.PASS
    )


def test_invalid_evidence_is_not_used() -> None:
    store = make_store()

    store.add(
        Evidence(
            evidence_id="evidence.invalid",
            task_id=TASK_ID,
            kind=EvidenceKind.STATE,
            status=EvidenceStatus.INVALID,
            value={
                "property": "project.exists",
                "value": True,
            },
            provenance=EvidenceProvenance(
                source_kind="test",
                source_id="invalid-source",
            ),
            timestamp="2026-09-08T16:00:00+03:00",
        )
    )

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.exists",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="project.exists",
                ),
            ),
            evaluator=lambda evidence: True,
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "project.exists",
        1,
        store,
    )

    assert (
        result.status
        is AssertionResultStatus.UNAVAILABLE
    )


def test_assertion_does_not_modify_evidence_store() -> None:
    store = make_store()

    evidence = make_state_evidence(
        "evidence.project",
        "project.exists",
        True,
    )

    store.add(evidence)

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.exists",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="project.exists",
                ),
            ),
            evaluator=lambda evidence: True,
        )
    )

    before = store.list()

    AssertionEvaluator(
        registry
    ).evaluate(
        "project.exists",
        1,
        store,
    )

    after = store.list()

    assert before == after
    assert store.get("evidence.project") is evidence


def test_assertion_result_preserves_evidence_reference() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.project",
            "project.exists",
            True,
        )
    )

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.exists",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="project.exists",
                ),
            ),
            evaluator=lambda evidence: True,
        )
    )

    result = AssertionEvaluator(
        registry
    ).evaluate(
        "project.exists",
        1,
        store,
    )

    assert result.evidence_ids == (
        "evidence.project",
    )


def test_multiple_assertions_are_evaluated_independently() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.exists",
            "project.exists",
            True,
        )
    )

    store.add(
        make_test_evidence(
            "evidence.test",
            "PASSED",
        )
    )

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.exists",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="project.exists",
                ),
            ),
            evaluator=lambda evidence:
                evidence[0].value["value"] is True,
        )
    )

    registry.register(
        AssertionSpec(
            identifier="integration.ok",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.TEST,
                ),
            ),
            evaluator=lambda evidence:
                evidence[0].value["status"] == "PASSED",
        )
    )

    results = AssertionEvaluator(
        registry
    ).evaluate_many(
        (
            ("project.exists", 1),
            ("integration.ok", 1),
        ),
        store,
    )

    assert len(results) == 2

    assert (
        results[0].status
        is AssertionResultStatus.PASS
    )

    assert (
        results[1].status
        is AssertionResultStatus.PASS
    )


def test_same_assertion_version_is_deterministic() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.project",
            "project.exists",
            True,
        )
    )

    registry = AssertionRegistry()

    registry.register(
        AssertionSpec(
            identifier="project.exists",
            version=1,
            required_observations=(
                AssertionObservationRequirement(
                    kind=EvidenceKind.STATE,
                    property_name="project.exists",
                ),
            ),
            evaluator=lambda evidence:
                evidence[0].value["value"] is True,
        )
    )

    evaluator = AssertionEvaluator(registry)

    result_a = evaluator.evaluate(
        "project.exists",
        1,
        store,
    )

    result_b = evaluator.evaluate(
        "project.exists",
        1,
        store,
    )

    assert result_a == result_b


def test_evaluator_does_not_mutate_spec() -> None:
    store = make_store()

    registry = AssertionRegistry()

    spec = AssertionSpec(
        identifier="static.assertion",
        version=1,
        evaluator=lambda evidence: True,
    )

    registry.register(spec)

    before = registry.resolve(
        "static.assertion",
        1,
    )

    AssertionEvaluator(
        registry
    ).evaluate(
        "static.assertion",
        1,
        store,
    )

    after = registry.resolve(
        "static.assertion",
        1,
    )

    assert before is after
    assert before == spec


def main() -> int:
    tests = [
        test_assertion_can_be_registered,
        test_duplicate_assertion_is_rejected,
        test_assertion_versions_are_independent,
        test_assertion_passes,
        test_assertion_fails,
        test_missing_required_observation_is_unavailable,
        test_unknown_assertion_is_unavailable,
        test_missing_evaluator_is_error,
        test_evaluator_exception_is_error,
        test_non_boolean_evaluator_result_is_error,
        test_test_evidence_can_be_required,
        test_invalid_evidence_is_not_used,
        test_assertion_does_not_modify_evidence_store,
        test_assertion_result_preserves_evidence_reference,
        test_multiple_assertions_are_evaluated_independently,
        test_same_assertion_version_is_deterministic,
        test_evaluator_does_not_mutate_spec,
    ]

    print("=" * 70)
    print("ASSERTION RUNTIME TESTS")
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
        print("ASSERTION RUNTIME: PASS")
    else:
        print("ASSERTION RUNTIME: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())