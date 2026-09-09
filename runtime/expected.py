from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from agent_task_v3 import ExpectedCondition, ExpectedKind
from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceStatus,
    EvidenceStore,
)


class ExpectedEvaluationStatus(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ExpectedEvaluation:
    expected_id: str
    kind: ExpectedKind
    status: ExpectedEvaluationStatus
    evidence_ids: tuple[str, ...] = ()
    message: str = ""

    @property
    def satisfied(self) -> bool:
        return self.status is ExpectedEvaluationStatus.SATISFIED


class ExpectedEvaluator:
    """
    Read-only evaluator of ExpectedCondition instances against EvidenceStore.

    Current supported kinds:
        - STATE
        - TEST

    The evaluator:
        - never creates Evidence;
        - never mutates Evidence;
        - never mutates TaskRun state;
        - only consumes existing Evidence.
    """

    @staticmethod
    def _state_expected_value(expected: ExpectedCondition) -> Any:
        parameters = expected.parameters

        if not isinstance(parameters, dict):
            raise ValueError(
                "STATE ExpectedCondition.parameters must be a dictionary."
            )

        if "property" not in parameters:
            raise ValueError(
                "STATE ExpectedCondition requires 'property'."
            )

        if "operator" not in parameters:
            raise ValueError(
                "STATE ExpectedCondition requires 'operator'."
            )

        if "expected_value" not in parameters:
            raise ValueError(
                "STATE ExpectedCondition requires 'expected_value'."
            )

        return parameters["expected_value"]

    @staticmethod
    def _state_operator(expected: ExpectedCondition) -> str:
        return expected.parameters["operator"]

    @staticmethod
    def _state_property(expected: ExpectedCondition) -> str:
        return expected.parameters["property"]

    @staticmethod
    def _compare(
        observed: Any,
        operator: str,
        expected_value: Any,
    ) -> bool:
        if operator == "EQUALS":
            return observed == expected_value

        if operator == "NOT_EQUALS":
            return observed != expected_value

        if operator == "GREATER":
            return observed > expected_value

        if operator == "GREATER_OR_EQUAL":
            return observed >= expected_value

        if operator == "LESS":
            return observed < expected_value

        if operator == "LESS_OR_EQUAL":
            return observed <= expected_value

        if operator == "IN":
            return observed in expected_value

        if operator == "CONTAINS":
            return expected_value in observed

        raise ValueError(
            f"Unsupported STATE operator: {operator}"
        )

    @classmethod
    def _find_state_evidence(
        cls,
        expected: ExpectedCondition,
        evidence_store: EvidenceStore,
    ) -> list[Evidence]:
        property_name = cls._state_property(expected)

        matching: list[Evidence] = []

        for evidence in evidence_store.list():
            if evidence.kind is not EvidenceKind.STATE:
                continue

            if evidence.status is not EvidenceStatus.VALID:
                continue

            if not isinstance(evidence.value, dict):
                continue

            if evidence.value.get("property") == property_name:
                matching.append(evidence)

        return matching

    @classmethod
    def _evaluate_state(
        cls,
        expected: ExpectedCondition,
        evidence_store: EvidenceStore,
    ) -> ExpectedEvaluation:
        try:
            expected_value = cls._state_expected_value(
                expected
            )
            operator = cls._state_operator(expected)

            evidence = cls._find_state_evidence(
                expected,
                evidence_store,
            )
        except Exception as exc:
            return ExpectedEvaluation(
                expected_id=expected.id,
                kind=expected.kind,
                status=ExpectedEvaluationStatus.ERROR,
                message=(
                    f"STATE expectation could not be evaluated: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if not evidence:
            return ExpectedEvaluation(
                expected_id=expected.id,
                kind=expected.kind,
                status=ExpectedEvaluationStatus.UNAVAILABLE,
                message=(
                    "No valid STATE evidence was found for "
                    f"property '{cls._state_property(expected)}'."
                ),
            )

        evidence_ids = tuple(
            item.evidence_id
            for item in evidence
        )

        for item in evidence:
            try:
                if cls._compare(
                    item.value["value"],
                    operator,
                    expected_value,
                ):
                    return ExpectedEvaluation(
                        expected_id=expected.id,
                        kind=expected.kind,
                        status=ExpectedEvaluationStatus.SATISFIED,
                        evidence_ids=evidence_ids,
                        message="",
                    )
            except Exception as exc:
                return ExpectedEvaluation(
                    expected_id=expected.id,
                    kind=expected.kind,
                    status=ExpectedEvaluationStatus.ERROR,
                    evidence_ids=evidence_ids,
                    message=(
                        f"STATE evidence comparison failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                )

        return ExpectedEvaluation(
            expected_id=expected.id,
            kind=expected.kind,
            status=ExpectedEvaluationStatus.NOT_SATISFIED,
            evidence_ids=evidence_ids,
            message=(
                "Available STATE evidence does not satisfy "
                "the expected condition."
            ),
        )

    @staticmethod
    def _test_expected_status(
        expected: ExpectedCondition,
    ) -> str:
        parameters = expected.parameters

        if not isinstance(parameters, dict):
            raise ValueError(
                "TEST ExpectedCondition.parameters must be a dictionary."
            )

        if "status" not in parameters:
            raise ValueError(
                "TEST ExpectedCondition requires 'status'."
            )

        return parameters["status"]

    @classmethod
    def _evaluate_test(
        cls,
        expected: ExpectedCondition,
        evidence_store: EvidenceStore,
    ) -> ExpectedEvaluation:
        try:
            expected_status = cls._test_expected_status(
                expected
            )
        except Exception as exc:
            return ExpectedEvaluation(
                expected_id=expected.id,
                kind=expected.kind,
                status=ExpectedEvaluationStatus.ERROR,
                message=(
                    f"TEST expectation could not be evaluated: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        matching: list[Evidence] = []

        for evidence in evidence_store.list():
            if evidence.kind is not EvidenceKind.TEST:
                continue

            if evidence.status is EvidenceStatus.ERROR:
                continue

            if not isinstance(evidence.value, dict):
                continue

            matching.append(evidence)

        if not matching:
            return ExpectedEvaluation(
                expected_id=expected.id,
                kind=expected.kind,
                status=ExpectedEvaluationStatus.UNAVAILABLE,
                message="No TEST evidence was found.",
            )

        evidence_ids = tuple(
            item.evidence_id
            for item in matching
        )

        for evidence in matching:
            observed_status = evidence.value.get("status")

            if observed_status == expected_status:
                if evidence.status is EvidenceStatus.VALID:
                    return ExpectedEvaluation(
                        expected_id=expected.id,
                        kind=expected.kind,
                        status=ExpectedEvaluationStatus.SATISFIED,
                        evidence_ids=evidence_ids,
                        message="",
                    )

                return ExpectedEvaluation(
                    expected_id=expected.id,
                    kind=expected.kind,
                    status=ExpectedEvaluationStatus.NOT_SATISFIED,
                    evidence_ids=evidence_ids,
                    message=(
                        "TEST evidence has the expected status "
                        "but is not VALID evidence."
                    ),
                )

        return ExpectedEvaluation(
            expected_id=expected.id,
            kind=expected.kind,
            status=ExpectedEvaluationStatus.NOT_SATISFIED,
            evidence_ids=evidence_ids,
            message=(
                "Available TEST evidence does not contain "
                f"the expected status '{expected_status}'."
            ),
        )

    @classmethod
    def evaluate_one(
        cls,
        expected: ExpectedCondition,
        evidence_store: EvidenceStore,
    ) -> ExpectedEvaluation:
        if not isinstance(expected, ExpectedCondition):
            raise TypeError(
                "ExpectedEvaluator accepts only ExpectedCondition instances."
            )

        if not isinstance(evidence_store, EvidenceStore):
            raise TypeError(
                "ExpectedEvaluator requires an EvidenceStore."
            )

        if expected.kind is ExpectedKind.STATE:
            return cls._evaluate_state(
                expected,
                evidence_store,
            )

        if expected.kind is ExpectedKind.TEST:
            return cls._evaluate_test(
                expected,
                evidence_store,
            )

        return ExpectedEvaluation(
            expected_id=expected.id,
            kind=expected.kind,
            status=ExpectedEvaluationStatus.ERROR,
            message=(
                f"Expected kind '{expected.kind.value}' "
                "is not supported by the current evaluator."
            ),
        )

    @classmethod
    def evaluate_all(
        cls,
        expected_conditions: tuple[ExpectedCondition, ...],
        evidence_store: EvidenceStore,
    ) -> tuple[ExpectedEvaluation, ...]:
        evaluations = [
            cls.evaluate_one(
                expected,
                evidence_store,
            )
            for expected in expected_conditions
        ]

        return tuple(evaluations)

    @staticmethod
    def all_satisfied(
        evaluations: tuple[ExpectedEvaluation, ...],
    ) -> bool:
        return all(
            evaluation.satisfied
            for evaluation in evaluations
        )