from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    ExpectedCondition,
    ExpectedKind,
    ValidationSpec,
)
from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceStore,
)
from runtime.execution import (
    ExecutionResult,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
)
from runtime.expected import (
    ExpectedEvaluation,
    ExpectedEvaluationStatus,
)
from runtime.task_outcome import (
    TaskOutcomeEvaluator,
    TaskOutcomeStatus,
)
from runtime.validation import (
    ValidationResult,
    ValidationStatus,
)


def make_execution(
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
) -> ExecutionResult:
    plan = ExecutionPlan(
        status=PlanStatus.READY,
        task=None,
    )

    return ExecutionResult(
        plan=plan,
        status=status,
        completed_steps=(
            ("step.1",)
            if status is ExecutionStatus.SUCCEEDED
            else ()
        ),
    )


def make_expected(
    expected_id: str = "expected.1",
    status: ExpectedEvaluationStatus = (
        ExpectedEvaluationStatus.SATISFIED
    ),
) -> ExpectedEvaluation:
    return ExpectedEvaluation(
        expected_id=expected_id,
        kind=ExpectedKind.STATE,
        status=status,
        evidence_ids=("evidence.1",),
    )


def make_validation(
    validation_id: str = "validation.1",
    status: ValidationStatus = ValidationStatus.VALID,
) -> ValidationResult:
    return ValidationResult(
        validation_id=validation_id,
        status=status,
        evidence_ids=("evidence.1",),
    )


def test_success_when_execution_expected_and_validation_succeed() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(),
        ),
        (
            make_validation(),
        ),
    )

    assert result.status is TaskOutcomeStatus.SUCCEEDED
    assert result.succeeded


def test_success_without_expected_or_validation() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
    )

    assert result.status is TaskOutcomeStatus.SUCCEEDED
    assert result.succeeded


def test_execution_failure_precedes_expected() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(
            ExecutionStatus.FAILED
        ),
        (
            make_expected(
                status=ExpectedEvaluationStatus.ERROR
            ),
        ),
        (
            make_validation(
                status=ValidationStatus.ERROR
            ),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXECUTION_FAILED
    )


def test_blocked_execution_is_not_success() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(
            ExecutionStatus.BLOCKED
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXECUTION_FAILED
    )


def test_cancelled_execution_is_not_success() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(
            ExecutionStatus.CANCELLED
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXECUTION_FAILED
    )


def test_infrastructure_execution_error_is_not_success() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(
            ExecutionStatus.INFRASTRUCTURE_ERROR
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXECUTION_FAILED
    )


def test_expected_not_satisfied_blocks_success() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(
                status=(
                    ExpectedEvaluationStatus.NOT_SATISFIED
                )
            ),
        ),
        (
            make_validation(),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXPECTED_NOT_SATISFIED
    )
    assert not result.succeeded


def test_expected_unavailable_is_distinct() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(
                status=(
                    ExpectedEvaluationStatus.UNAVAILABLE
                )
            ),
        ),
        (
            make_validation(),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXPECTED_UNAVAILABLE
    )


def test_expected_error_is_distinct() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(
                status=ExpectedEvaluationStatus.ERROR
            ),
        ),
        (
            make_validation(),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXPECTED_ERROR
    )


def test_validation_invalid_blocks_success() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(),
        ),
        (
            make_validation(
                status=ValidationStatus.INVALID
            ),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.VALIDATION_INVALID
    )


def test_validation_insufficient_is_distinct() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(),
        ),
        (
            make_validation(
                status=ValidationStatus.INSUFFICIENT
            ),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.VALIDATION_INSUFFICIENT
    )


def test_validation_error_is_distinct() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(),
        ),
        (
            make_validation(
                status=ValidationStatus.ERROR
            ),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.VALIDATION_ERROR
    )


def test_all_expected_conditions_are_required() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(
                expected_id="expected.1",
                status=ExpectedEvaluationStatus.SATISFIED,
            ),
            make_expected(
                expected_id="expected.2",
                status=ExpectedEvaluationStatus.NOT_SATISFIED,
            ),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXPECTED_NOT_SATISFIED
    )


def test_all_validation_results_are_required() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(),
        ),
        (
            make_validation(
                validation_id="validation.1",
                status=ValidationStatus.VALID,
            ),
            make_validation(
                validation_id="validation.2",
                status=ValidationStatus.INSUFFICIENT,
            ),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.VALIDATION_INSUFFICIENT
    )


def test_expected_is_evaluated_before_validation() -> None:
    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (
            make_expected(
                status=ExpectedEvaluationStatus.NOT_SATISFIED
            ),
        ),
        (
            make_validation(
                status=ValidationStatus.INVALID
            ),
        ),
    )

    assert (
        result.status
        is TaskOutcomeStatus.EXPECTED_NOT_SATISFIED
    )


def test_result_preserves_expected_evaluations() -> None:
    expected = (
        make_expected(),
    )

    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        expected,
    )

    assert result.expected_evaluations == expected


def test_result_preserves_validation_results() -> None:
    validation = (
        make_validation(),
    )

    result = TaskOutcomeEvaluator.evaluate(
        make_execution(),
        (),
        validation,
    )

    assert result.validation_results == validation


def test_result_preserves_execution_identity() -> None:
    execution = make_execution()

    result = TaskOutcomeEvaluator.evaluate(
        execution,
    )

    assert result.execution is execution


def test_outcome_evaluation_is_deterministic() -> None:
    execution = make_execution()

    expected = (
        make_expected(),
    )

    validation = (
        make_validation(),
    )

    result_a = TaskOutcomeEvaluator.evaluate(
        execution,
        expected,
        validation,
    )

    result_b = TaskOutcomeEvaluator.evaluate(
        execution,
        expected,
        validation,
    )

    assert result_a == result_b


def test_evaluator_rejects_invalid_execution_type() -> None:
    try:
        TaskOutcomeEvaluator.evaluate(
            object(),
        )
    except TypeError:
        return

    raise AssertionError(
        "Invalid ExecutionResult type was accepted."
    )


def test_evaluator_does_not_modify_results() -> None:
    execution = make_execution()

    expected = (
        make_expected(),
    )

    validation = (
        make_validation(),
    )

    before_expected = expected
    before_validation = validation
    before_execution = execution

    result = TaskOutcomeEvaluator.evaluate(
        execution,
        expected,
        validation,
    )

    assert result.succeeded
    assert expected == before_expected
    assert validation == before_validation
    assert execution is before_execution


def main() -> int:
    tests = [
        test_success_when_execution_expected_and_validation_succeed,
        test_success_without_expected_or_validation,
        test_execution_failure_precedes_expected,
        test_blocked_execution_is_not_success,
        test_cancelled_execution_is_not_success,
        test_infrastructure_execution_error_is_not_success,
        test_expected_not_satisfied_blocks_success,
        test_expected_unavailable_is_distinct,
        test_expected_error_is_distinct,
        test_validation_invalid_blocks_success,
        test_validation_insufficient_is_distinct,
        test_validation_error_is_distinct,
        test_all_expected_conditions_are_required,
        test_all_validation_results_are_required,
        test_expected_is_evaluated_before_validation,
        test_result_preserves_expected_evaluations,
        test_result_preserves_validation_results,
        test_result_preserves_execution_identity,
        test_outcome_evaluation_is_deterministic,
        test_evaluator_rejects_invalid_execution_type,
        test_evaluator_does_not_modify_results,
    ]

    print("=" * 70)
    print("TASK OUTCOME TESTS")
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
        print("TASK OUTCOME: PASS")
    else:
        print("TASK OUTCOME: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())