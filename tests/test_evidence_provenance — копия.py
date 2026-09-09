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


def make_evidence(
    provenance: EvidenceProvenance,
) -> Evidence:
    return Evidence(
        evidence_id="evidence.provenance.1",
        task_id="task-provenance",
        kind=EvidenceKind.STATE,
        status=EvidenceStatus.VALID,
        value={
            "state": "ready",
        },
        provenance=provenance,
        timestamp="runtime",
    )


def test_evidence_rejects_empty_source_kind() -> None:
    try:
        make_evidence(
            EvidenceProvenance(
                source_kind="",
                source_id="source-1",
            )
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Evidence accepted an empty provenance source_kind."
        )


def test_evidence_rejects_empty_source_id() -> None:
    try:
        make_evidence(
            EvidenceProvenance(
                source_kind="test",
                source_id="",
            )
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Evidence accepted an empty provenance source_id."
        )


def test_provenance_is_immutable() -> None:
    provenance = EvidenceProvenance(
        source_kind="test",
        source_id="source-1",
    )

    try:
        provenance.source_id = "source-2"
    except Exception as exc:
        assert isinstance(
            exc,
            (AttributeError, TypeError),
        )
    else:
        raise AssertionError(
            "EvidenceProvenance accepted mutation."
        )

    assert provenance.source_id == "source-1"


def test_evidence_preserves_provenance_identity() -> None:
    provenance = EvidenceProvenance(
        source_kind="test",
        source_id="source-1",
    )

    evidence = make_evidence(provenance)

    assert evidence.provenance is provenance
    assert evidence.provenance.source_kind == "test"
    assert evidence.provenance.source_id == "source-1"


def test_different_sources_remain_distinguishable() -> None:
    provenance_1 = EvidenceProvenance(
        source_kind="test",
        source_id="source-1",
    )

    provenance_2 = EvidenceProvenance(
        source_kind="test",
        source_id="source-2",
    )

    assert provenance_1 != provenance_2


def test_different_source_kinds_remain_distinguishable() -> None:
    provenance_1 = EvidenceProvenance(
        source_kind="test",
        source_id="source-1",
    )

    provenance_2 = EvidenceProvenance(
        source_kind="build",
        source_id="source-1",
    )

    assert provenance_1 != provenance_2

