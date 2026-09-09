from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_task_v3 import (
    ExecutionPolicy,
    FailureMode,
    RollbackMode,
    TimeoutPolicy,
    RetryPolicy,
    ParallelismPolicy,
    FailurePolicy,
    RollbackPolicy,
)

from runtime.execution_policy import (
    ExecutionPolicyResolver,
    ExecutionPolicyStatus,
    HandlerExecutionPolicy,
    RuntimeExecutionLimits,
    ResourcePolicy,
    TransactionExecutionPolicy,
)


def make_task_policy(
    timeout=60,
    attempts=5,
    workers=8,
    failure=FailureMode.ABORT,
    rollback=RollbackMode.REQUIRED,
):
    return ExecutionPolicy(
        timeout=TimeoutPolicy(
            total_seconds=timeout
        ),
        retry=RetryPolicy(
            max_attempts=attempts
        ),
        parallelism=ParallelismPolicy(
            max_workers=workers
        ),
        resources={},
        failure=FailurePolicy(
            mode=failure
        ),
        rollback=RollbackPolicy(
            mode=rollback
        ),
    )


def test_task_and_handler_intersection():
    resolver = ExecutionPolicyResolver()

    result = resolver.resolve(
        make_task_policy(),
        RuntimeExecutionLimits(),
        handler_policy=HandlerExecutionPolicy(
            timeout_seconds=30,
            max_attempts=3,
            max_workers=4,
        ),
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None

    assert result.policy.timeout_seconds == 30
    assert result.policy.max_attempts == 3
    assert result.policy.max_workers == 4


def test_all_numeric_sources_use_intersection():
    resolver = ExecutionPolicyResolver()

    result = resolver.resolve(
        make_task_policy(
            timeout=60,
            attempts=8,
            workers=8,
        ),
        RuntimeExecutionLimits(
            timeout_seconds=50,
            max_attempts=6,
            max_workers=6,
        ),
        handler_policy=HandlerExecutionPolicy(
            timeout_seconds=40,
            max_attempts=5,
            max_workers=4,
        ),
        transaction_policy=TransactionExecutionPolicy(
            timeout_seconds=30,
            max_attempts=3,
            max_workers=2,
        ),
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None

    assert result.policy.timeout_seconds == 30
    assert result.policy.max_attempts == 3
    assert result.policy.max_workers == 2


def test_transaction_policy_can_restrict_runtime_defaults():
    resolver = ExecutionPolicyResolver()

    result = resolver.resolve(
        None,
        RuntimeExecutionLimits(),
        transaction_policy=TransactionExecutionPolicy(
            max_attempts=1,
            max_workers=1,
        ),
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None

    assert result.policy.max_attempts == 1
    assert result.policy.max_workers == 1


def test_resource_limits_are_intersected():
    resolver = ExecutionPolicyResolver()

    result = resolver.resolve(
        make_task_policy(),
        RuntimeExecutionLimits(
            resources=ResourcePolicy(
                values={
                    "cpu": 8,
                    "memory": 16384,
                }
            )
        ),
        handler_policy=HandlerExecutionPolicy(
            resources=ResourcePolicy(
                values={
                    "cpu": 4,
                    "memory": 8192,
                }
            )
        ),
        transaction_policy=TransactionExecutionPolicy(
            resources=ResourcePolicy(
                values={
                    "cpu": 2,
                    "memory": 4096,
                }
            )
        ),
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None

    assert result.policy.resources.values == {
        "cpu": 2,
        "memory": 4096,
    }


def test_matching_failure_modes_are_accepted():
    resolver = ExecutionPolicyResolver()

    result = resolver.resolve(
        make_task_policy(
            failure=FailureMode.ABORT,
        ),
        RuntimeExecutionLimits(
            failure_mode=FailureMode.ABORT,
        ),
        handler_policy=HandlerExecutionPolicy(
            failure_mode=FailureMode.ABORT,
        ),
        transaction_policy=TransactionExecutionPolicy(
            failure_mode=FailureMode.ABORT,
        ),
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None
    assert result.policy.failure_mode is FailureMode.ABORT


def test_conflicting_failure_modes_are_rejected():
    resolver = ExecutionPolicyResolver()

    result = resolver.resolve(
        make_task_policy(
            failure=FailureMode.ABORT,
        ),
        RuntimeExecutionLimits(
            failure_mode=FailureMode.ROLLBACK,
        ),
    )

    assert result.status is ExecutionPolicyStatus.CONFLICT
    assert result.policy is None
    assert "failure_mode" in result.message


def test_conflicting_rollback_modes_are_rejected():
    resolver = ExecutionPolicyResolver()

    result = resolver.resolve(
        make_task_policy(
            rollback=RollbackMode.REQUIRED,
        ),
        RuntimeExecutionLimits(
            rollback_mode=RollbackMode.OPTIONAL,
        ),
    )

    assert result.status is ExecutionPolicyStatus.CONFLICT
    assert result.policy is None
    assert "rollback_mode" in result.message


def test_old_two_argument_resolver_call_still_works():
    resolver = ExecutionPolicyResolver()

    result = resolver.resolve(
        make_task_policy(
            timeout=20,
            attempts=2,
            workers=3,
        ),
        RuntimeExecutionLimits(),
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None

    assert result.policy.timeout_seconds == 20
    assert result.policy.max_attempts == 2
    assert result.policy.max_workers == 3


def test_handler_policy_type_is_required():
    resolver = ExecutionPolicyResolver()

    try:
        resolver.resolve(
            make_task_policy(),
            RuntimeExecutionLimits(),
            handler_policy=object(),
        )
    except TypeError:
        return

    raise AssertionError(
        "Expected TypeError for invalid handler policy."
    )


def test_transaction_policy_type_is_required():
    resolver = ExecutionPolicyResolver()

    try:
        resolver.resolve(
            make_task_policy(),
            RuntimeExecutionLimits(),
            transaction_policy=object(),
        )
    except TypeError:
        return

    raise AssertionError(
        "Expected TypeError for invalid transaction policy."
    )


TESTS = (
    test_task_and_handler_intersection,
    test_all_numeric_sources_use_intersection,
    test_transaction_policy_can_restrict_runtime_defaults,
    test_resource_limits_are_intersected,
    test_matching_failure_modes_are_accepted,
    test_conflicting_failure_modes_are_rejected,
    test_conflicting_rollback_modes_are_rejected,
    test_old_two_argument_resolver_call_still_works,
    test_handler_policy_type_is_required,
    test_transaction_policy_type_is_required,
)


def main() -> int:
    print("=" * 70)
    print("EXECUTION POLICY AGGREGATION TESTS")
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
        print("EXECUTION POLICY AGGREGATION: FAIL")
        return 1

    print("EXECUTION POLICY AGGREGATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
