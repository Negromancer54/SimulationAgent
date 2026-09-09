from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EvidenceKind(str, Enum):
    STATE = "STATE"
    ASSERTION = "ASSERTION"
    TEST = "TEST"
    CHANGESET = "CHANGESET"
    EXECUTION = "EXECUTION"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class EvidenceProvenance:
    """
    Identifies where an evidence item came from.

    source_id is deliberately opaque to the Evidence layer.
    The producer owns the meaning of this identifier.
    """

    source_kind: str
    source_id: str


@dataclass(frozen=True)
class Evidence:
    """
    Immutable observation produced during one TaskRun.
    """

    evidence_id: str
    task_id: str
    kind: EvidenceKind
    status: EvidenceStatus
    value: Any
    provenance: EvidenceProvenance
    timestamp: str
    context: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError(
                "Evidence.evidence_id must be a non-empty string."
            )

        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError(
                "Evidence.task_id must be a non-empty string."
            )

        if not isinstance(self.kind, EvidenceKind):
            raise ValueError(
                "Evidence.kind must be an EvidenceKind."
            )

        if not isinstance(self.status, EvidenceStatus):
            raise ValueError(
                "Evidence.status must be an EvidenceStatus."
            )

        if not isinstance(self.provenance, EvidenceProvenance):
            raise ValueError(
                "Evidence.provenance must be EvidenceProvenance."
            )

        if (
            not isinstance(self.provenance.source_kind, str)
            or not self.provenance.source_kind.strip()
        ):
            raise ValueError(
                "EvidenceProvenance.source_kind must be a "
                "non-empty string."
            )

        if (
            not isinstance(self.provenance.source_id, str)
            or not self.provenance.source_id.strip()
        ):
            raise ValueError(
                "EvidenceProvenance.source_id must be a "
                "non-empty string."
            )

        if not isinstance(self.timestamp, str) or not self.timestamp.strip():
            raise ValueError(
                "Evidence.timestamp must be a non-empty string."
            )

        normalized_context = tuple(self.context)

        for item in normalized_context:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError(
                    "Evidence.context must contain key/value tuples."
                )

            key, _ = item

            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    "Evidence.context keys must be non-empty strings."
                )

        object.__setattr__(
            self,
            "context",
            normalized_context,
        )


class EvidenceStore:
    """
    Immutable-evidence store belonging to one TaskRun.

    The store itself is mutable because new observations are produced,
    but an already stored Evidence object is never modified.
    """

    def __init__(self, task_id: str) -> None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(
                "EvidenceStore.task_id must be a non-empty string."
            )

        self._task_id = task_id
        self._evidence: dict[str, Evidence] = {}

    @property
    def task_id(self) -> str:
        return self._task_id

    def add(self, evidence: Evidence) -> None:
        if not isinstance(evidence, Evidence):
            raise TypeError(
                "EvidenceStore accepts only Evidence instances."
            )

        if evidence.task_id != self._task_id:
            raise ValueError(
                "Evidence.task_id does not match the owning TaskRun."
            )

        if evidence.evidence_id in self._evidence:
            raise ValueError(
                f"Evidence is already registered: {evidence.evidence_id}"
            )

        self._evidence[evidence.evidence_id] = evidence

    def contains(self, evidence_id: str) -> bool:
        return evidence_id in self._evidence

    def get(self, evidence_id: str) -> Evidence | None:
        return self._evidence.get(evidence_id)

    def list(self) -> tuple[Evidence, ...]:
        return tuple(self._evidence.values())

    def count(self) -> int:
        return len(self._evidence)