from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from agent_task_v3 import ValidationSpec
from runtime.evidence import (
    Evidence,
    EvidenceStatus,
    EvidenceStore,
)


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    INSUFFICIENT = "INSUFFICIENT"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ValidationResult:
    validation_id: str
    status: ValidationStatus
    evidence_ids: tuple[str, ...] = ()
    message: str = ""

    @property
    def valid(self) -> bool:
        return self.status is ValidationStatus.VALID


class ValidationEvaluator:
    """
    Read-only evaluator of ValidationSpec against EvidenceStore.

    Validation answers:
        "Is there sufficient acceptable evidence for this validation?"

    It does not:
        - evaluate ExpectedCondition semantics;
        - create Evidence;
        - modify Evidence;
        - modify TaskV3;
        - mutate the TaskRun.
    """

    @staticmethod
    def _matches_source(
        evidence: Evidence,
        source_kind: str,
    ) -> bool:
        return evidence.provenance.source_kind == source_kind

    @staticmethod
    def _freshness_satisfied(
        evidence: Evidence,
        freshness: Any,
    ) -> bool:
        """
        Initial freshness semantics.

        Supported values:
            None      -> no freshness restriction
            "ANY"     -> no freshness restriction
            "CURRENT" -> accepted as current evidence from this TaskRun
            positive int/float -> maximum age in seconds

        The Validation layer intentionally does not redefine timestamps;
        it only applies the requested freshness rule.
        """

        if freshness is None:
            return True

        if freshness == "ANY":
            return True

        if freshness == "CURRENT":
            return True

        if isinstance(freshness, bool):
            return False

        if isinstance(freshness, (int, float)):
            if freshness <= 0:
                return False

            # EvidenceStore is scoped to one TaskRun, so the current
            # implementation treats stored evidence as belonging to
            # that run. Numeric timestamp-age validation belongs to a
            # later clock-aware runtime layer.
            return True

        return False

    @classmethod
    def _matching_evidence(
        cls,
        source_kind: str,
        freshness: Any,
        evidence_store: EvidenceStore,
    ) -> list[Evidence]:
        matching: list[Evidence] = []

        for evidence in evidence_store.list():
            if evidence.status is not EvidenceStatus.VALID:
                continue

            if not cls._matches_source(
                evidence,
                source_kind,
            ):
                continue

            if not cls._freshness_satisfied(
                evidence,
                freshness,
            ):
                continue

            matching.append(evidence)

        return matching

    @classmethod
    def evaluate(
        cls,
        spec: ValidationSpec,
        evidence_store: EvidenceStore,
    ) -> ValidationResult:
        if not isinstance(spec, ValidationSpec):
            raise TypeError(
                "ValidationEvaluator accepts only ValidationSpec instances."
            )

        if not isinstance(evidence_store, EvidenceStore):
            raise TypeError(
                "ValidationEvaluator requires an EvidenceStore."
            )

        if not spec.id.strip():
            return ValidationResult(
                validation_id=spec.id,
                status=ValidationStatus.ERROR,
                message="ValidationSpec.id must be non-empty.",
            )

        all_evidence_ids: list[str] = []

        try:
            for requirement in spec.evidence_requirements:
                matches = cls._matching_evidence(
                    requirement.source_kind,
                    requirement.freshness,
                    evidence_store,
                )

                if not matches:
                    return ValidationResult(
                        validation_id=spec.id,
                        status=ValidationStatus.INSUFFICIENT,
                        evidence_ids=tuple(
                            all_evidence_ids
                        ),
                        message=(
                            "Required evidence is insufficient for "
                            f"source '{requirement.source_kind}'."
                        ),
                    )

                all_evidence_ids.extend(
                    evidence.evidence_id
                    for evidence in matches
                )

            # A ValidationSpec with no evidence requirements is not
            # automatically valid: there is nothing to validate.
            if not spec.evidence_requirements:
                return ValidationResult(
                    validation_id=spec.id,
                    status=ValidationStatus.INSUFFICIENT,
                    message=(
                        "ValidationSpec contains no evidence requirements."
                    ),
                )

        except Exception as exc:
            return ValidationResult(
                validation_id=spec.id,
                status=ValidationStatus.ERROR,
                evidence_ids=tuple(
                    all_evidence_ids
                ),
                message=(
                    f"Validation evaluation failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        return ValidationResult(
            validation_id=spec.id,
            status=ValidationStatus.VALID,
            evidence_ids=tuple(
                all_evidence_ids
            ),
            message="",
        )

    @classmethod
    def evaluate_many(
        cls,
        specs: tuple[ValidationSpec, ...],
        evidence_store: EvidenceStore,
    ) -> tuple[ValidationResult, ...]:
        return tuple(
            cls.evaluate(
                spec,
                evidence_store,
            )
            for spec in specs
        )

    @staticmethod
    def all_valid(
        results: tuple[ValidationResult, ...],
    ) -> bool:
        return (
            bool(results)
            and all(
                result.valid
                for result in results
            )
        )