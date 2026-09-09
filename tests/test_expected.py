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


TASK_ID = "task-expected-test"


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
        timestamp="2026-09-08T15:00:00+03:00",
    )


def make_test_evidence(
    evidence_id: str,
    status: str,
    evidence_status: EvidenceStatus = EvidenceStatus.VALID,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id=TASK_ID,
        kind=EvidenceKind.TEST,
        status=evidence_status,
        value={
            "status": status,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="test-runtime",
        ),
        timestamp="2026-09-08T15:00:00+03:00",
    )


def make_state_expected(
    expected_id: str = "expected.state",
    operator: str = "EQUALS",
    expected_value=True,
) -> ExpectedCondition:
    return ExpectedCondition(
        id=expected_id,
        kind=ExpectedKind.STATE,
        identifier="project.exists",
        version=1,
        parameters={
            "property": "project.exists",
            "operator": operator,
            "expected_value": expected_value,
        },
    )


def make_test_expected(
    expected_id: str = "expected.test",
    status: str = "PASSED",
) -> ExpectedCondition:
    return ExpectedCondition(
        id=expected_id,
        kind=ExpectedKind.TEST,
        identifier="tests.integration",
        version=1,
        parameters={
            "status": status,
        },
    )


def test_state_equals_is_satisfied() -> None:
    store = make_store()

    evidence = make_state_evidence(
        "evidence.state.1",
        "project.exists",
        True,
    )

    store.add(evidence)

    expected = make_state_expected()

    result = ExpectedEvaluator.evaluate_one(
        expected,
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.SATISFIED
    )
    assert result.satisfied
    assert result.evidence_ids == (
        "evidence.state.1",
    )


def test_state_equals_can_fail() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.state.1",
            "project.exists",
            False,
        )
    )

    result = ExpectedEvaluator.evaluate_one(
        make_state_expected(expected_value=True),
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.NOT_SATISFIED
    )
    assert not result.satisfied


def test_state_greater_is_supported() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.count",
            "component.count",
            10,
        )
    )

    expected = ExpectedCondition(
        id="expected.count",
        kind=ExpectedKind.STATE,
        identifier="component.count",
        version=1,
        parameters={
            "property": "component.count",
            "operator": "GREATER",
            "expected_value": 5,
        },
    )

    result = ExpectedEvaluator.evaluate_one(
        expected,
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.SATISFIED
    )


def test_state_less_or_equal_is_supported() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.count",
            "component.count",
            5,
        )
    )

    expected = ExpectedCondition(
        id="expected.count",
        kind=ExpectedKind.STATE,
        identifier="component.count",
        version=1,
        parameters={
            "property": "component.count",
            "operator": "LESS_OR_EQUAL",
            "expected_value": 5,
        },
    )

    result = ExpectedEvaluator.evaluate_one(
        expected,
        store,
    )

    assert result.satisfied


def test_state_in_is_supported() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.mode",
            "mode",
            "SAFE",
        )
    )

    expected = ExpectedCondition(
        id="expected.mode",
        kind=ExpectedKind.STATE,
        identifier="mode",
        version=1,
        parameters={
            "property": "mode",
            "operator": "IN",
            "expected_value": (
                "SAFE",
                "ACTIVE",
            ),
        },
    )

    result = ExpectedEvaluator.evaluate_one(
        expected,
        store,
    )

    assert result.satisfied


def test_state_contains_is_supported() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.features",
            "features",
            ["A", "B", "C"],
        )
    )

    expected = ExpectedCondition(
        id="expected.feature",
        kind=ExpectedKind.STATE,
        identifier="features",
        version=1,
        parameters={
            "property": "features",
            "operator": "CONTAINS",
            "expected_value": "B",
        },
    )

    result = ExpectedEvaluator.evaluate_one(
        expected,
        store,
    )

    assert result.satisfied


def test_missing_state_evidence_is_unavailable() -> None:
    store = make_store()

    result = ExpectedEvaluator.evaluate_one(
        make_state_expected(),
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.UNAVAILABLE
    )
    assert not result.satisfied


def test_invalid_state_parameters_return_error() -> None:
    store = make_store()

    expected = ExpectedCondition(
        id="expected.invalid",
        kind=ExpectedKind.STATE,
        identifier="project.exists",
        version=1,
        parameters={
            "property": "project.exists",
        },
    )

    result = ExpectedEvaluator.evaluate_one(
        expected,
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.ERROR
    )


def test_test_expected_is_satisfied() -> None:
    store = make_store()

    store.add(
        make_test_evidence(
            "evidence.test.1",
            "PASSED",
        )
    )

    result = ExpectedEvaluator.evaluate_one(
        make_test_expected(),
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.SATISFIED
    )
    assert result.satisfied
    assert result.evidence_ids == (
        "evidence.test.1",
    )


def test_test_expected_can_fail() -> None:
    store = make_store()

    store.add(
        make_test_evidence(
            "evidence.test.1",
            "FAILED",
        )
    )

    result = ExpectedEvaluator.evaluate_one(
        make_test_expected(status="PASSED"),
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.NOT_SATISFIED
    )
    assert not result.satisfied


def test_invalid_test_evidence_does_not_satisfy() -> None:
    store = make_store()

    store.add(
        make_test_evidence(
            "evidence.test.1",
            "PASSED",
            evidence_status=EvidenceStatus.INVALID,
        )
    )

    result = ExpectedEvaluator.evaluate_one(
        make_test_expected(),
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.NOT_SATISFIED
    )


def test_missing_test_evidence_is_unavailable() -> None:
    store = make_store()

    result = ExpectedEvaluator.evaluate_one(
        make_test_expected(),
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.UNAVAILABLE
    )


def test_multiple_expected_conditions_are_evaluated_independently() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.state",
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

    expected = (
        make_state_expected(
            expected_id="expected.state"
        ),
        make_test_expected(
            expected_id="expected.test"
        ),
    )

    results = ExpectedEvaluator.evaluate_all(
        expected,
        store,
    )

    assert len(results) == 2
    assert all(
        result.status
        is ExpectedEvaluationStatus.SATISFIED
        for result in results
    )
    assert ExpectedEvaluator.all_satisfied(results)


def test_one_unsatisfied_expected_fails_all_satisfied() -> None:
    store = make_store()

    store.add(
        make_state_evidence(
            "evidence.state",
            "project.exists",
            True,
        )
    )

    expected = (
        make_state_expected(
            expected_id="expected.state",
            expected_value=True,
        ),
        make_state_expected(
            expected_id="expected.other",
            expected_value=False,
        ),
    )

    results = ExpectedEvaluator.evaluate_all(
        expected,
        store,
    )

    assert len(results) == 2
    assert results[0].satisfied
    assert (
        results[1].status
        is ExpectedEvaluationStatus.NOT_SATISFIED
    )
    assert not ExpectedEvaluator.all_satisfied(results)


def test_unsupported_expected_kind_is_error() -> None:
    store = make_store()

    expected = ExpectedCondition(
        id="expected.assertion",
        kind=ExpectedKind.ASSERTION,
        identifier="some.assertion",
        version=1,
        parameters={},
    )

    result = ExpectedEvaluator.evaluate_one(
        expected,
        store,
    )

    assert (
        result.status
        is ExpectedEvaluationStatus.ERROR
    )


def test_expected_evaluation_does_not_modify_evidence_store() -> None:
    store = make_store()

    evidence = make_state_evidence(
        "evidence.state",
        "project.exists",
        True,
    )

    store.add(evidence)

    before = store.list()

    ExpectedEvaluator.evaluate_one(
        make_state_expected(),
        store,
    )

    after = store.list()

    assert before == after
    assert store.get("evidence.state") is evidence


def test_expected_evidence_reference_is_preserved() -> None:
    store = make_store()

    evidence = make_state_evidence(
        "evidence.state",
        "project.exists",
        True,
    )

    store.add(evidence)

    result = ExpectedEvaluator.evaluate_one(
        make_state_expected(),
        store,
    )

    assert result.evidence_ids == (
        "evidence.state",
    )


def main() -> int:
    tests = [
        test_state_equals_is_satisfied,
        test_state_equals_can_fail,
        test_state_greater_is_supported,
        test_state_less_or_equal_is_supported,
        test_state_in_is_supported,
        test_state_contains_is_supported,
        test_missing_state_evidence_is_unavailable,
        test_invalid_state_parameters_return_error,
        test_test_expected_is_satisfied,
        test_test_expected_can_fail,
        test_invalid_test_evidence_does_not_satisfy,
        test_missing_test_evidence_is_unavailable,
        test_multiple_expected_conditions_are_evaluated_independently,
        test_one_unsatisfied_expected_fails_all_satisfied,
        test_unsupported_expected_kind_is_error,
        test_expected_evaluation_does_not_modify_evidence_store,
        test_expected_evidence_reference_is_preserved,
    ]

    print("=" * 70)
    print("EXPECTED EVALUATION TESTS")
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
        print("EXPECTED EVALUATION: PASS")
    else:
        print("EXPECTED EVALUATION: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())