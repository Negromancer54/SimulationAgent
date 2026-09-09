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
)


def make_evidence(timestamp: str) -> Evidence:
    return Evidence(
        evidence_id="evidence.timestamp.1",
        task_id="task-timestamp",
        kind=EvidenceKind.STATE,
        status=EvidenceStatus.VALID,
        value={
            "ready": True,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="timestamp",
        ),
        timestamp=timestamp,
    )


def test_timestamp_is_required() -> None:
    try:
        make_evidence("")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Evidence accepted an empty timestamp."
        )


def test_timestamp_is_preserved() -> None:
    timestamp = "2026-09-08T21:00:00Z"

    evidence = make_evidence(timestamp)

    assert evidence.timestamp == timestamp


def test_different_timestamps_are_distinguishable() -> None:
    evidence_1 = make_evidence(
        "2026-09-08T21:00:00Z"
    )

    evidence_2 = Evidence(
        evidence_id="evidence.timestamp.2",
        task_id="task-timestamp",
        kind=EvidenceKind.STATE,
        status=EvidenceStatus.VALID,
        value={
            "ready": True,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="timestamp",
        ),
        timestamp="2026-09-08T21:01:00Z",
    )

    assert evidence_1.timestamp != evidence_2.timestamp


def test_timestamp_is_part_of_immutable_evidence() -> None:
    timestamp = "2026-09-08T21:00:00Z"
    evidence = make_evidence(timestamp)

    try:
        evidence.timestamp = "2026-09-08T22:00:00Z"
    except Exception as exc:
        assert isinstance(
            exc,
            (AttributeError, TypeError),
        )
    else:
        raise AssertionError(
            "Evidence accepted timestamp mutation."
        )

    assert evidence.timestamp == timestamp


def test_timestamp_survives_value_object_identity() -> None:
    timestamp = "2026-09-08T21:00:00Z"
    evidence = make_evidence(timestamp)

    assert evidence.timestamp is timestamp
    assert str(evidence.timestamp) == timestamp


def test_empty_or_whitespace_timestamp_is_rejected() -> None:
    for timestamp in ("", "   ", "\t", "\n"):
        try:
            make_evidence(timestamp)
        except ValueError:
            continue

        raise AssertionError(
            "Evidence accepted an empty/whitespace timestamp."
        )
