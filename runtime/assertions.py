from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceStatus,
    EvidenceStore,
)


class AssertionResultStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class AssertionObservationRequirement:
    """
    Declarative description of one observation required by an assertion.

    Currently an assertion may require:
        - an EvidenceKind;
        - a property name contained in STATE evidence.

    property_name=None means that any evidence of the specified kind
    may satisfy the observation requirement.
    """

    kind: EvidenceKind
    property_name: str | None = None


@dataclass(frozen=True)
class AssertionSpec:
    """
    Registered semantic definition of an assertion.

    evaluator is the implementation of the assertion semantics.
    required_observations describe the evidence that must be available.
    """

    identifier: str
    version: int
    required_observations: tuple[
        AssertionObservationRequirement, ...
    ] = ()
    evaluator: Callable[
        [tuple[Evidence, ...]],
        bool,
    ] | None = None


@dataclass(frozen=True)
class AssertionResult:
    identifier: str
    version: int
    status: AssertionResultStatus
    evidence_ids: tuple[str, ...] = ()
    message: str = ""

    @property
    def passed(self) -> bool:
        return self.status is AssertionResultStatus.PASS


class AssertionRegistry:
    """
    Registry of versioned AssertionSpec definitions.
    """

    def __init__(self) -> None:
        self._specs: dict[
            tuple[str, int],
            AssertionSpec,
        ] = {}

    @staticmethod
    def _validate_spec(spec: AssertionSpec) -> None:
        if not isinstance(spec, AssertionSpec):
            raise ValueError(
                "AssertionRegistry accepts only AssertionSpec instances."
            )

        if (
            not isinstance(spec.identifier, str)
            or not spec.identifier.strip()
        ):
            raise ValueError(
                "AssertionSpec.identifier must be a non-empty string."
            )

        if (
            not isinstance(spec.version, int)
            or isinstance(spec.version, bool)
            or spec.version <= 0
        ):
            raise ValueError(
                "AssertionSpec.version must be a positive integer."
            )

        if not isinstance(
            spec.required_observations,
            tuple,
        ):
            raise ValueError(
                "AssertionSpec.required_observations must be a tuple."
            )

        for requirement in spec.required_observations:
            if not isinstance(
                requirement,
                AssertionObservationRequirement,
            ):
                raise ValueError(
                    "AssertionSpec.required_observations must contain "
                    "AssertionObservationRequirement instances."
                )

            if requirement.property_name is not None:
                if (
                    not isinstance(
                        requirement.property_name,
                        str,
                    )
                    or not requirement.property_name.strip()
                ):
                    raise ValueError(
                        "Assertion observation property_name must be "
                        "None or a non-empty string."
                    )

        if spec.evaluator is not None and not callable(spec.evaluator):
            raise ValueError(
                "AssertionSpec.evaluator must be callable or None."
            )

    def register(self, spec: AssertionSpec) -> None:
        self._validate_spec(spec)

        key = (
            spec.identifier,
            spec.version,
        )

        if key in self._specs:
            raise ValueError(
                "AssertionSpec is already registered: "
                f"{spec.identifier}@{spec.version}"
            )

        self._specs[key] = spec

    def contains(
        self,
        identifier: str,
        version: int,
    ) -> bool:
        return (
            identifier,
            version,
        ) in self._specs

    def resolve(
        self,
        identifier: str,
        version: int,
    ) -> AssertionSpec | None:
        return self._specs.get(
            (
                identifier,
                version,
            )
        )

    def list_versions(
        self,
        identifier: str,
    ) -> list[int]:
        versions = [
            version
            for (
                registered_identifier,
                version,
            ) in self._specs
            if registered_identifier == identifier
        ]

        versions.sort()
        return versions


class AssertionEvaluator:
    """
    Evaluates registered assertions against read-only EvidenceStore.

    The evaluator never:
        - creates Evidence;
        - modifies Evidence;
        - modifies EvidenceStore;
        - executes project mutations.
    """

    def __init__(
        self,
        registry: AssertionRegistry,
    ) -> None:
        self._registry = registry

    @staticmethod
    def _find_evidence_for_requirement(
        requirement: AssertionObservationRequirement,
        evidence_store: EvidenceStore,
    ) -> list[Evidence]:
        matches: list[Evidence] = []

        for evidence in evidence_store.list():
            if evidence.status is not EvidenceStatus.VALID:
                continue

            if evidence.kind is not requirement.kind:
                continue

            if (
                requirement.property_name is not None
                and (
                    evidence.kind is not EvidenceKind.STATE
                    or not isinstance(evidence.value, dict)
                    or evidence.value.get("property")
                    != requirement.property_name
                )
            ):
                continue

            matches.append(evidence)

        return matches

    @classmethod
    def _collect_required_evidence(
        cls,
        spec: AssertionSpec,
        evidence_store: EvidenceStore,
    ) -> tuple[
        tuple[Evidence, ...],
        tuple[str, ...],
    ] | None:
        selected: list[Evidence] = []

        for requirement in spec.required_observations:
            matches = cls._find_evidence_for_requirement(
                requirement,
                evidence_store,
            )

            if not matches:
                return None

            selected.append(matches[0])

        evidence_ids = tuple(
            evidence.evidence_id
            for evidence in selected
        )

        return (
            tuple(selected),
            evidence_ids,
        )

    def evaluate(
        self,
        identifier: str,
        version: int,
        evidence_store: EvidenceStore,
    ) -> AssertionResult:
        if not isinstance(evidence_store, EvidenceStore):
            raise TypeError(
                "AssertionEvaluator requires an EvidenceStore."
            )

        spec = self._registry.resolve(
            identifier,
            version,
        )

        if spec is None:
            return AssertionResult(
                identifier=identifier,
                version=version,
                status=AssertionResultStatus.UNAVAILABLE,
                message=(
                    f"Assertion '{identifier}@{version}' "
                    "is not registered."
                ),
            )

        if spec.evaluator is None:
            return AssertionResult(
                identifier=identifier,
                version=version,
                status=AssertionResultStatus.ERROR,
                message=(
                    f"Assertion '{identifier}@{version}' "
                    "has no evaluator implementation."
                ),
            )

        collected = self._collect_required_evidence(
            spec,
            evidence_store,
        )

        if collected is None:
            return AssertionResult(
                identifier=identifier,
                version=version,
                status=AssertionResultStatus.UNAVAILABLE,
                message=(
                    "One or more required observations "
                    "are unavailable."
                ),
            )

        evidence, evidence_ids = collected

        try:
            passed = spec.evaluator(evidence)
        except Exception as exc:
            return AssertionResult(
                identifier=identifier,
                version=version,
                status=AssertionResultStatus.ERROR,
                evidence_ids=evidence_ids,
                message=(
                    f"Assertion evaluator raised "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if not isinstance(passed, bool):
            return AssertionResult(
                identifier=identifier,
                version=version,
                status=AssertionResultStatus.ERROR,
                evidence_ids=evidence_ids,
                message=(
                    "Assertion evaluator must return bool."
                ),
            )

        if passed:
            return AssertionResult(
                identifier=identifier,
                version=version,
                status=AssertionResultStatus.PASS,
                evidence_ids=evidence_ids,
                message="",
            )

        return AssertionResult(
            identifier=identifier,
            version=version,
            status=AssertionResultStatus.FAIL,
            evidence_ids=evidence_ids,
            message="Assertion condition evaluated to false.",
        )

    def evaluate_many(
        self,
        assertions: tuple[
            tuple[str, int],
            ...
        ],
        evidence_store: EvidenceStore,
    ) -> tuple[AssertionResult, ...]:
        return tuple(
            self.evaluate(
                identifier,
                version,
                evidence_store,
            )
            for identifier, version in assertions
        )