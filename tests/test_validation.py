from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    ValidationSpec,
)
from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceStore,
)
from runtime.validation import (
    ValidationEvaluator,
    ValidationStatus,
)


TASK_ID = "task-validation-test"


def make_store() -> EvidenceStore:
    return EvidenceStore(TASK_ID)


def make_evidence(
    evidence_id: str,
    source_kind: str,
    kind: EvidenceKind = EvidenceKind.EXECUTION,
    status: EvidenceStatus = EvidenceStatus.VALID,
    value=None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id=TASK_ID,
        kind=kind,
        status=status,
        value=value,
        provenance=EvidenceProvenance(
            source_kind=source_kind,
            source_id=f"source.{source_kind}",
        ),
        timestamp="2026-09-08T18:00:00+03:00",
    )


def make_spec(
    validation_id: str = "validation.execution",
    requirements=None,
) -> ValidationSpec:
    return ValidationSpec(
        id=validation_id,
        identifier="execution.evidence",
        version=1,
        applies_to=None,
        evidence_requirements=tuple(
            requirements or []
        ),
    )


def test_validation_is_valid_when_required_evidence_exists() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    spec = make_spec(
        requirements=[
            # EvidenceRequirement is created here without assuming
            # additional runtime machinery.
            __import__(
                "agent_task_v3",
                fromlist=["EvidenceRequirement"],
            ).EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert result.status is ValidationStatus.VALID
    assert result.valid
    assert result.evidence_ids == (
        "evidence.execution",
    )


def test_missing_required_evidence_is_insufficient() -> None:
    store = make_store()

    spec = make_spec(
        requirements=[
            __import__(
                "agent_task_v3",
                fromlist=["EvidenceRequirement"],
            ).EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert (
        result.status
        is ValidationStatus.INSUFFICIENT
    )
    assert not result.valid


def test_invalid_evidence_is_not_sufficient() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.invalid",
            "execution",
            status=EvidenceStatus.INVALID,
        )
    )

    spec = make_spec(
        requirements=[
            __import__(
                "agent_task_v3",
                fromlist=["EvidenceRequirement"],
            ).EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert (
        result.status
        is ValidationStatus.INSUFFICIENT
    )


def test_unavailable_evidence_is_not_sufficient() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.unavailable",
            "execution",
            status=EvidenceStatus.UNAVAILABLE,
        )
    )

    spec = make_spec(
        requirements=[
            __import__(
                "agent_task_v3",
                fromlist=["EvidenceRequirement"],
            ).EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert (
        result.status
        is ValidationStatus.INSUFFICIENT
    )


def test_error_evidence_is_not_sufficient() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.error",
            "execution",
            status=EvidenceStatus.ERROR,
        )
    )

    spec = make_spec(
        requirements=[
            __import__(
                "agent_task_v3",
                fromlist=["EvidenceRequirement"],
            ).EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert (
        result.status
        is ValidationStatus.INSUFFICIENT
    )


def test_multiple_requirements_use_and_semantics() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    store.add(
        make_evidence(
            "evidence.test",
            "test",
            kind=EvidenceKind.TEST,
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = make_spec(
        requirements=[
            EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
            EvidenceRequirement(
                source_kind="test",
                freshness=None,
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert result.status is ValidationStatus.VALID
    assert set(result.evidence_ids) == {
        "evidence.execution",
        "evidence.test",
    }


def test_one_missing_requirement_makes_validation_insufficient() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = make_spec(
        requirements=[
            EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
            EvidenceRequirement(
                source_kind="test",
                freshness=None,
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert (
        result.status
        is ValidationStatus.INSUFFICIENT
    )


def test_any_freshness_allows_existing_valid_evidence() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = make_spec(
        requirements=[
            EvidenceRequirement(
                source_kind="execution",
                freshness="ANY",
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert result.status is ValidationStatus.VALID


def test_current_freshness_allows_current_taskrun_evidence() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = make_spec(
        requirements=[
            EvidenceRequirement(
                source_kind="execution",
                freshness="CURRENT",
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert result.status is ValidationStatus.VALID


def test_invalid_freshness_is_not_satisfied() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = make_spec(
        requirements=[
            EvidenceRequirement(
                source_kind="execution",
                freshness="INVALID_POLICY",
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert (
        result.status
        is ValidationStatus.INSUFFICIENT
    )


def test_empty_validation_requirements_are_insufficient() -> None:
    store = make_store()

    spec = make_spec(
        requirements=[]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert (
        result.status
        is ValidationStatus.INSUFFICIENT
    )


def test_multiple_validation_specs_are_independent() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    specs = (
        make_spec(
            validation_id="validation.execution",
            requirements=[
                EvidenceRequirement(
                    source_kind="execution",
                    freshness=None,
                ),
            ],
        ),
        make_spec(
            validation_id="validation.test",
            requirements=[
                EvidenceRequirement(
                    source_kind="test",
                    freshness=None,
                ),
            ],
        ),
    )

    results = ValidationEvaluator.evaluate_many(
        specs,
        store,
    )

    assert len(results) == 2
    assert (
        results[0].status
        is ValidationStatus.VALID
    )
    assert (
        results[1].status
        is ValidationStatus.INSUFFICIENT
    )
    assert not ValidationEvaluator.all_valid(results)


def test_validation_does_not_modify_evidence_store() -> None:
    store = make_store()

    evidence = make_evidence(
        "evidence.execution",
        "execution",
    )

    store.add(evidence)

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = make_spec(
        requirements=[
            EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ]
    )

    before = store.list()

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    after = store.list()

    assert result.valid
    assert before == after
    assert store.get(evidence.evidence_id) is evidence


def test_unknown_validation_identifier_is_allowed_at_this_layer() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = ValidationSpec(
        id="validation.unknown.semantic",
        identifier="not.runtime-resolved-here",
        version=999,
        applies_to=None,
        evidence_requirements=(
            EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ),
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert result.status is ValidationStatus.VALID


def test_validation_result_preserves_evidence_ids() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = make_spec(
        requirements=[
            EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ]
    )

    result = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert result.evidence_ids == (
        "evidence.execution",
    )


def test_validation_result_is_deterministic() -> None:
    store = make_store()

    store.add(
        make_evidence(
            "evidence.execution",
            "execution",
        )
    )

    EvidenceRequirement = __import__(
        "agent_task_v3",
        fromlist=["EvidenceRequirement"],
    ).EvidenceRequirement

    spec = make_spec(
        requirements=[
            EvidenceRequirement(
                source_kind="execution",
                freshness=None,
            ),
        ]
    )

    result_a = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    result_b = ValidationEvaluator.evaluate(
        spec,
        store,
    )

    assert result_a == result_b


def main() -> int:
    tests = [
        test_validation_is_valid_when_required_evidence_exists,
        test_missing_required_evidence_is_insufficient,
        test_invalid_evidence_is_not_sufficient,
        test_unavailable_evidence_is_not_sufficient,
        test_error_evidence_is_not_sufficient,
        test_multiple_requirements_use_and_semantics,
        test_one_missing_requirement_makes_validation_insufficient,
        test_any_freshness_allows_existing_valid_evidence,
        test_current_freshness_allows_current_taskrun_evidence,
        test_invalid_freshness_is_not_satisfied,
        test_empty_validation_requirements_are_insufficient,
        test_multiple_validation_specs_are_independent,
        test_validation_does_not_modify_evidence_store,
        test_unknown_validation_identifier_is_allowed_at_this_layer,
        test_validation_result_preserves_evidence_ids,
        test_validation_result_is_deterministic,
    ]

    print("=" * 70)
    print("VALIDATION RUNTIME TESTS")
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
        print("VALIDATION RUNTIME: PASS")
    else:
        print("VALIDATION RUNTIME: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())