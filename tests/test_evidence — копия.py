from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceStore,
)


TASK_ID = "task-evidence-test"


def make_evidence(
    evidence_id: str = "evidence.1",
    task_id: str = TASK_ID,
    kind: EvidenceKind = EvidenceKind.STATE,
    status: EvidenceStatus = EvidenceStatus.VALID,
    value=None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id=task_id,
        kind=kind,
        status=status,
        value=value,
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="test-source",
        ),
        timestamp="2026-09-08T12:00:00+03:00",
    )


def test_evidence_can_be_created() -> None:
    evidence = make_evidence(
        value={"project_exists": True}
    )

    assert evidence.evidence_id == "evidence.1"
    assert evidence.task_id == TASK_ID
    assert evidence.kind is EvidenceKind.STATE
    assert evidence.status is EvidenceStatus.VALID
    assert evidence.value == {"project_exists": True}


def test_provenance_is_preserved() -> None:
    evidence = make_evidence()

    assert evidence.provenance.source_kind == "test"
    assert evidence.provenance.source_id == "test-source"


def test_context_is_preserved() -> None:
    evidence = Evidence(
        evidence_id="evidence.context",
        task_id=TASK_ID,
        kind=EvidenceKind.EXECUTION,
        status=EvidenceStatus.VALID,
        value="ok",
        provenance=EvidenceProvenance(
            source_kind="execution",
            source_id="step.1",
        ),
        timestamp="2026-09-08T12:00:00+03:00",
        context=(
            ("attempt", 1),
            ("worker", "worker.0"),
        ),
    )

    assert evidence.context == (
        ("attempt", 1),
        ("worker", "worker.0"),
    )


def test_store_belongs_to_one_task_run() -> None:
    store = EvidenceStore(TASK_ID)

    assert store.task_id == TASK_ID
    assert store.count() == 0


def test_evidence_can_be_added_and_retrieved() -> None:
    store = EvidenceStore(TASK_ID)
    evidence = make_evidence(
        value=42
    )

    store.add(evidence)

    assert store.contains("evidence.1")
    assert store.get("evidence.1") is evidence
    assert store.count() == 1


def test_multiple_evidence_items_are_preserved() -> None:
    store = EvidenceStore(TASK_ID)

    first = make_evidence(
        evidence_id="evidence.1",
        value="first",
    )

    second = make_evidence(
        evidence_id="evidence.2",
        kind=EvidenceKind.EXECUTION,
        value="second",
    )

    store.add(first)
    store.add(second)

    assert store.count() == 2
    assert store.list() == (
        first,
        second,
    )


def test_duplicate_evidence_id_is_rejected() -> None:
    store = EvidenceStore(TASK_ID)

    store.add(
        make_evidence()
    )

    try:
        store.add(
            make_evidence(
                value="duplicate",
            )
        )
    except ValueError:
        return

    raise AssertionError(
        "Duplicate evidence ID was accepted."
    )


def test_evidence_from_another_task_run_is_rejected() -> None:
    store = EvidenceStore(TASK_ID)

    foreign = make_evidence(
        evidence_id="foreign",
        task_id="another-task",
    )

    try:
        store.add(foreign)
    except ValueError:
        return

    raise AssertionError(
        "Evidence from another TaskRun was accepted."
    )


def test_stored_evidence_is_immutable() -> None:
    store = EvidenceStore(TASK_ID)

    evidence = make_evidence(
        value={"state": "before"}
    )

    store.add(evidence)

    try:
        evidence.value = {"state": "after"}
    except Exception:
        pass
    else:
        raise AssertionError(
            "Stored Evidence was mutable."
        )

    assert (
        store.get("evidence.1").value
        == {"state": "before"}
    )


def test_invalid_evidence_kind_is_rejected() -> None:
    try:
        Evidence(
            evidence_id="bad",
            task_id=TASK_ID,
            kind="STATE",
            status=EvidenceStatus.VALID,
            value=None,
            provenance=EvidenceProvenance(
                source_kind="test",
                source_id="source",
            ),
            timestamp="2026-09-08T12:00:00+03:00",
        )
    except ValueError:
        return

    raise AssertionError(
        "Invalid Evidence.kind was accepted."
    )


def test_invalid_evidence_status_is_rejected() -> None:
    try:
        Evidence(
            evidence_id="bad",
            task_id=TASK_ID,
            kind=EvidenceKind.STATE,
            status="VALID",
            value=None,
            provenance=EvidenceProvenance(
                source_kind="test",
                source_id="source",
            ),
            timestamp="2026-09-08T12:00:00+03:00",
        )
    except ValueError:
        return

    raise AssertionError(
        "Invalid Evidence.status was accepted."
    )


def test_invalid_provenance_is_rejected() -> None:
    try:
        Evidence(
            evidence_id="bad",
            task_id=TASK_ID,
            kind=EvidenceKind.STATE,
            status=EvidenceStatus.VALID,
            value=None,
            provenance=object(),
            timestamp="2026-09-08T12:00:00+03:00",
        )
    except ValueError:
        return

    raise AssertionError(
        "Invalid Evidence provenance was accepted."
    )


def test_unknown_evidence_returns_none() -> None:
    store = EvidenceStore(TASK_ID)

    assert store.get("missing") is None
    assert not store.contains("missing")


def test_different_evidence_statuses_are_distinct() -> None:
    valid = make_evidence(
        evidence_id="valid",
        status=EvidenceStatus.VALID,
    )

    invalid = make_evidence(
        evidence_id="invalid",
        status=EvidenceStatus.INVALID,
    )

    unavailable = make_evidence(
        evidence_id="unavailable",
        status=EvidenceStatus.UNAVAILABLE,
    )

    error = make_evidence(
        evidence_id="error",
        status=EvidenceStatus.ERROR,
    )

    assert valid.status is EvidenceStatus.VALID
    assert invalid.status is EvidenceStatus.INVALID
    assert unavailable.status is EvidenceStatus.UNAVAILABLE
    assert error.status is EvidenceStatus.ERROR


def test_store_preserves_insertion_order() -> None:
    store = EvidenceStore(TASK_ID)

    first = make_evidence(
        evidence_id="evidence.1"
    )
    second = make_evidence(
        evidence_id="evidence.2"
    )
    third = make_evidence(
        evidence_id="evidence.3"
    )

    store.add(first)
    store.add(second)
    store.add(third)

    assert store.list() == (
        first,
        second,
        third,
    )


def main() -> int:
    tests = [
        test_evidence_can_be_created,
        test_provenance_is_preserved,
        test_context_is_preserved,
        test_store_belongs_to_one_task_run,
        test_evidence_can_be_added_and_retrieved,
        test_multiple_evidence_items_are_preserved,
        test_duplicate_evidence_id_is_rejected,
        test_evidence_from_another_task_run_is_rejected,
        test_stored_evidence_is_immutable,
        test_invalid_evidence_kind_is_rejected,
        test_invalid_evidence_status_is_rejected,
        test_invalid_provenance_is_rejected,
        test_unknown_evidence_returns_none,
        test_different_evidence_statuses_are_distinct,
        test_store_preserves_insertion_order,
    ]

    print("=" * 70)
    print("EVIDENCE RUNTIME TESTS")
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
        print("EVIDENCE RUNTIME: PASS")
    else:
        print("EVIDENCE RUNTIME: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())