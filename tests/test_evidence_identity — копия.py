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
    task_id: str = "task-1",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id=task_id,
        kind=EvidenceKind.STATE,
        status=EvidenceStatus.VALID,
        value={
            "ready": True,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="identity",
        ),
        timestamp="runtime",
    )


def test_evidence_is_immutable() -> None:
    evidence = make_evidence("evidence.1")

    try:
        evidence.status = EvidenceStatus.ERROR
    except Exception as exc:
        assert isinstance(
            exc,
            (AttributeError, TypeError),
        )
    else:
        raise AssertionError(
            "Evidence accepted mutation after creation."
        )

    assert evidence.status is EvidenceStatus.VALID


def test_store_accepts_only_evidence() -> None:
    store = EvidenceStore("task-1")

    try:
        store.add(object())
    except TypeError:
        pass
    else:
        raise AssertionError(
            "EvidenceStore accepted a non-Evidence object."
        )

    assert store.count() == 0


def test_store_rejects_evidence_from_another_task() -> None:
    store = EvidenceStore("task-1")

    try:
        store.add(
            make_evidence(
                "evidence.1",
                task_id="task-2",
            )
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "EvidenceStore accepted evidence owned by another task."
        )

    assert store.count() == 0


def test_store_rejects_duplicate_evidence_id() -> None:
    store = EvidenceStore("task-1")

    first = make_evidence("evidence.1")
    second = make_evidence("evidence.1")

    store.add(first)

    try:
        store.add(second)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "EvidenceStore accepted a duplicate evidence_id."
        )

    assert store.count() == 1
    assert store.get("evidence.1") is first


def test_store_preserves_registered_evidence() -> None:
    store = EvidenceStore("task-1")

    evidence_1 = make_evidence("evidence.1")
    evidence_2 = make_evidence("evidence.2")

    store.add(evidence_1)
    store.add(evidence_2)

    assert store.count() == 2
    assert store.list() == (
        evidence_1,
        evidence_2,
    )

    assert store.get("evidence.1") is evidence_1
    assert store.get("evidence.2") is evidence_2


def test_different_stores_are_independent() -> None:
    store_1 = EvidenceStore("task-1")
    store_2 = EvidenceStore("task-2")

    evidence_1 = make_evidence(
        "evidence.1",
        task_id="task-1",
    )

    evidence_2 = make_evidence(
        "evidence.1",
        task_id="task-2",
    )

    store_1.add(evidence_1)
    store_2.add(evidence_2)

    assert store_1 is not store_2

    assert store_1.count() == 1
    assert store_2.count() == 1

    assert store_1.get("evidence.1") is evidence_1
    assert store_2.get("evidence.1") is evidence_2
