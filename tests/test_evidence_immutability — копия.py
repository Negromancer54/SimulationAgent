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


def make_evidence(
    evidence_id: str,
    value: object = "initial",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id="task-immutability",
        kind=EvidenceKind.STATE,
        status=EvidenceStatus.VALID,
        value=value,
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="immutability",
        ),
        timestamp="runtime",
    )


def test_stored_evidence_identity_is_preserved() -> None:
    store = EvidenceStore("task-immutability")
    evidence = make_evidence("evidence.1")

    store.add(evidence)

    assert store.get("evidence.1") is evidence
    assert store.list() == (evidence,)


def test_duplicate_add_does_not_replace_original_evidence() -> None:
    store = EvidenceStore("task-immutability")

    first = make_evidence(
        "evidence.1",
        value="first",
    )

    second = make_evidence(
        "evidence.1",
        value="second",
    )

    store.add(first)

    try:
        store.add(second)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "EvidenceStore replaced an existing Evidence item."
        )

    assert store.get("evidence.1") is first
    assert store.get("evidence.1").value == "first"
    assert store.count() == 1


def test_get_does_not_create_a_new_evidence_object() -> None:
    store = EvidenceStore("task-immutability")
    evidence = make_evidence("evidence.1")

    store.add(evidence)

    retrieved = store.get("evidence.1")

    assert retrieved is evidence
    assert retrieved is not None


def test_list_preserves_original_evidence_objects() -> None:
    store = EvidenceStore("task-immutability")

    evidence_1 = make_evidence("evidence.1")
    evidence_2 = make_evidence("evidence.2")

    store.add(evidence_1)
    store.add(evidence_2)

    listed = store.list()

    assert listed[0] is evidence_1
    assert listed[1] is evidence_2


def test_adding_new_evidence_does_not_replace_previous_objects() -> None:
    store = EvidenceStore("task-immutability")

    evidence_1 = make_evidence(
        "evidence.1",
        value="first",
    )

    store.add(evidence_1)

    evidence_2 = make_evidence(
        "evidence.2",
        value="second",
    )

    store.add(evidence_2)

    assert store.get("evidence.1") is evidence_1
    assert store.get("evidence.2") is evidence_2
    assert evidence_1.value == "first"
    assert evidence_2.value == "second"
    assert store.count() == 2


def test_evidence_remains_immutable_after_storage() -> None:
    store = EvidenceStore("task-immutability")

    evidence = make_evidence(
        "evidence.1",
        value={
            "state": "ready",
        },
    )

    store.add(evidence)

    try:
        evidence.status = EvidenceStatus.ERROR
    except Exception as exc:
        assert isinstance(
            exc,
            (AttributeError, TypeError),
        )
    else:
        raise AssertionError(
            "Stored Evidence accepted mutation."
        )

    retrieved = store.get("evidence.1")

    assert retrieved is evidence
    assert retrieved.status is EvidenceStatus.VALID
    assert retrieved.value == {
        "state": "ready",
    }
