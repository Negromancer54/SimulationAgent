from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_task_v3 import (
    FailureMode,
    RollbackMode,
)

from runtime.execution_policy import (
    ExecutionPolicyConstraint,
    HandlerExecutionPolicy,
    ResourcePolicy,
    TransactionExecutionPolicy,
)


def test_transaction_policy_is_distinct_type():
    policy = TransactionExecutionPolicy(
        timeout_seconds=15,
        max_attempts=2,
        max_workers=1,
    )

    assert isinstance(
        policy,
        TransactionExecutionPolicy,
    )

    assert isinstance(
        policy,
        ExecutionPolicyConstraint,
    )

    assert type(policy) is TransactionExecutionPolicy


def test_handler_and_transaction_policies_are_distinct_types():
    handler_policy = HandlerExecutionPolicy(
        max_workers=4,
    )

    transaction_policy = TransactionExecutionPolicy(
        max_workers=2,
    )

    assert type(handler_policy) is HandlerExecutionPolicy
    assert type(transaction_policy) is TransactionExecutionPolicy

    assert type(handler_policy) is not type(
        transaction_policy
    )


def test_transaction_policy_supports_resources():
    policy = TransactionExecutionPolicy(
        resources=ResourcePolicy(
            values={
                "cpu": 2,
                "memory": 4096,
            }
        )
    )

    assert policy.resources is not None
    assert policy.resources.values == {
        "cpu": 2,
        "memory": 4096,
    }


def test_transaction_policy_supports_failure_and_rollback():
    policy = TransactionExecutionPolicy(
        failure_mode=FailureMode.ROLLBACK,
        rollback_mode=RollbackMode.REQUIRED,
    )

    assert policy.failure_mode is FailureMode.ROLLBACK
    assert policy.rollback_mode is RollbackMode.REQUIRED


def test_transaction_policy_reuses_constraint_validation():
    try:
        TransactionExecutionPolicy(
            timeout_seconds=0
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for invalid transaction timeout."
    )


def test_transaction_policy_without_constraints_is_unrestricted():
    policy = TransactionExecutionPolicy()

    assert policy.timeout_seconds is None
    assert policy.max_attempts is None
    assert policy.max_workers is None
    assert policy.resources is None
    assert policy.failure_mode is None
    assert policy.rollback_mode is None


TESTS = (
    test_transaction_policy_is_distinct_type,
    test_handler_and_transaction_policies_are_distinct_types,
    test_transaction_policy_supports_resources,
    test_transaction_policy_supports_failure_and_rollback,
    test_transaction_policy_reuses_constraint_validation,
    test_transaction_policy_without_constraints_is_unrestricted,
)


def main() -> int:
    print("=" * 70)
    print("TRANSACTION EXECUTION POLICY TESTS")
    print("=" * 70)

    passed = 0

    for test in TESTS:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test.__name__}")
            print(f"       {type(exc).__name__}: {exc}")

    print()
    print(f"Tests: {passed}/{len(TESTS)}")

    if passed != len(TESTS):
        print("TRANSACTION EXECUTION POLICY: FAIL")
        return 1

    print("TRANSACTION EXECUTION POLICY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
