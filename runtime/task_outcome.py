from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from runtime.execution import (
    ExecutionResult,
    ExecutionStatus,
)
from runtime.expected import (
    ExpectedEvaluation,
    ExpectedEvaluationStatus,
)
from runtime.validation import (
    ValidationResult,
    ValidationStatus,
)


class TaskOutcomeStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXPECTED_NOT_SATISFIED = "EXPECTED_NOT_SATISFIED"
    EXPECTED_UNAVAILABLE = "EXPECTED_UNAVAILABLE"
    EXPECTED_ERROR = "EXPECTED_ERROR"
    VALIDATION_INVALID = "VALIDATION_INVALID"
    VALIDATION_INSUFFICIENT = "VALIDATION_INSUFFICIENT"
    VALIDATION_ERROR = "VALIDATION_ERROR"


@dataclass(frozen=True)
class TaskOutcome:
    status: TaskOutcomeStatus
    execution: ExecutionResult
    expected_evaluations: tuple[ExpectedEvaluation, ...] = ()
    validation_results: tuple[ValidationResult, ...] = ()
    message: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status is TaskOutcomeStatus.SUCCEEDED


class TaskOutcomeEvaluator:
    """
    Produces the final semantic outcome of one TaskRun.

    Decision order:

        1. Execution must have succeeded.
        2. Every required Expected must be SATISFIED.
        3. Every required Validation must be VALID.
        4. Otherwise the corresponding failure class is returned.

    Expected and Validation remain independent consumers of Evidence.
    This layer only combines their already-computed results.
    """

    @staticmethod
    def _map_execution_failure(
        execution: ExecutionResult,
    ) -> TaskOutcomeStatus:
        if execution.status is ExecutionStatus.FAILED:
            return TaskOutcomeStatus.EXECUTION_FAILED

        if execution.status is ExecutionStatus.BLOCKED:
            return TaskOutcomeStatus.EXECUTION_FAILED

        if execution.status is ExecutionStatus.CANCELLED:
            return TaskOutcomeStatus.EXECUTION_FAILED

        if (
            execution.status
            is ExecutionStatus.INFRASTRUCTURE_ERROR
        ):
            return TaskOutcomeStatus.EXECUTION_FAILED

        return TaskOutcomeStatus.EXECUTION_FAILED

    @staticmethod
    def _evaluate_expected(
        evaluations: tuple[ExpectedEvaluation, ...],
    ) -> tuple[bool, TaskOutcomeStatus | None, str]:
        for evaluation in evaluations:
            if (
                evaluation.status
                is ExpectedEvaluationStatus.NOT_SATISFIED
            ):
                return (
                    False,
                    TaskOutcomeStatus.EXPECTED_NOT_SATISFIED,
                    (
                        "One or more Expected conditions "
                        "are not satisfied."
                    ),
                )

            if (
                evaluation.status
                is ExpectedEvaluationStatus.UNAVAILABLE
            ):
                return (
                    False,
                    TaskOutcomeStatus.EXPECTED_UNAVAILABLE,
                    (
                        "One or more Expected conditions "
                        "are unavailable."
                    ),
                )

            if (
                evaluation.status
                is ExpectedEvaluationStatus.ERROR
            ):
                return (
                    False,
                    TaskOutcomeStatus.EXPECTED_ERROR,
                    (
                        "One or more Expected conditions "
                        "returned an evaluation error."
                    ),
                )

            if (
                evaluation.status
                is not ExpectedEvaluationStatus.SATISFIED
            ):
                return (
                    False,
                    TaskOutcomeStatus.EXPECTED_ERROR,
                    (
                        "An Expected evaluation returned "
                        "an unsupported status."
                    ),
                )

        return True, None, ""

    @staticmethod
    def _evaluate_validation(
        results: tuple[ValidationResult, ...],
    ) -> tuple[bool, TaskOutcomeStatus | None, str]:
        for result in results:
            if result.status is ValidationStatus.INVALID:
                return (
                    False,
                    TaskOutcomeStatus.VALIDATION_INVALID,
                    (
                        "One or more Validation results "
                        "are INVALID."
                    ),
                )

            if (
                result.status
                is ValidationStatus.INSUFFICIENT
            ):
                return (
                    False,
                    TaskOutcomeStatus.VALIDATION_INSUFFICIENT,
                    (
                        "One or more Validation results "
                        "are INSUFFICIENT."
                    ),
                )

            if result.status is ValidationStatus.ERROR:
                return (
                    False,
                    TaskOutcomeStatus.VALIDATION_ERROR,
                    (
                        "One or more Validation results "
                        "returned an error."
                    ),
                )

            if result.status is not ValidationStatus.VALID:
                return (
                    False,
                    TaskOutcomeStatus.VALIDATION_ERROR,
                    (
                        "A Validation result returned "
                        "an unsupported status."
                    ),
                )

        return True, None, ""

    @classmethod
    def evaluate(
        cls,
        execution: ExecutionResult,
        expected_evaluations: tuple[ExpectedEvaluation, ...] = (),
        validation_results: tuple[ValidationResult, ...] = (),
    ) -> TaskOutcome:
        if not isinstance(execution, ExecutionResult):
            raise TypeError(
                "TaskOutcomeEvaluator requires an ExecutionResult."
            )

        if execution.status is not ExecutionStatus.SUCCEEDED:
            return TaskOutcome(
                status=cls._map_execution_failure(
                    execution
                ),
                execution=execution,
                expected_evaluations=expected_evaluations,
                validation_results=validation_results,
                message=(
                    "Task execution did not succeed."
                ),
            )

        expected_ok, expected_status, expected_message = (
            cls._evaluate_expected(
                expected_evaluations
            )
        )

        if not expected_ok:
            return TaskOutcome(
                status=expected_status,
                execution=execution,
                expected_evaluations=expected_evaluations,
                validation_results=validation_results,
                message=expected_message,
            )

        validation_ok, validation_status, validation_message = (
            cls._evaluate_validation(
                validation_results
            )
        )

        if not validation_ok:
            return TaskOutcome(
                status=validation_status,
                execution=execution,
                expected_evaluations=expected_evaluations,
                validation_results=validation_results,
                message=validation_message,
            )

        return TaskOutcome(
            status=TaskOutcomeStatus.SUCCEEDED,
            execution=execution,
            expected_evaluations=expected_evaluations,
            validation_results=validation_results,
            message="",
        )