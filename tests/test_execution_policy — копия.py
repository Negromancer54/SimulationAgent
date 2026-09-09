from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    EffectiveExecutionPolicy,
    ExecutionPolicyResolver,
    ExecutionPolicyStatus,
    RuntimeExecutionLimits,
)


def make_policy(
    *,
    timeout=120,
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
        failure=FailurePolicy(
            mode=failure
        ),
        rollback=RollbackPolicy(
            mode=rollback
        ),
    )


def test_task_policy_without_runtime_limits_is_preserved():
    result = ExecutionPolicyResolver().resolve(
        make_policy(
            timeout=120,
            attempts=5,
            workers=8,
        ),
        RuntimeExecutionLimits(),
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None

    assert result.policy.timeout_seconds == 120
    assert result.policy.max_attempts == 5
    assert result.policy.max_workers == 8


def test_runtime_limits_restrict_timeout():
    result = ExecutionPolicyResolver().resolve(
        make_policy(
            timeout=120,
        ),
        RuntimeExecutionLimits(
            timeout_seconds=30,
        ),
    )

    assert result.ready
    assert result.policy is not None
    assert result.policy.timeout_seconds == 30


def test_runtime_limits_restrict_retry_attempts():
    result = ExecutionPolicyResolver().resolve(
        make_policy(
            attempts=10,
        ),
        RuntimeExecutionLimits(
            max_attempts=3,
        ),
    )

    assert result.ready
    assert result.policy is not None
    assert result.policy.max_attempts == 3


def test_runtime_limits_restrict_parallelism():
    result = ExecutionPolicyResolver().resolve(
        make_policy(
            workers=16,
        ),
        RuntimeExecutionLimits(
            max_workers=4,
        ),
    )

    assert result.ready
    assert result.policy is not None
    assert result.policy.max_workers == 4


def test_runtime_limits_do_not_expand_task_policy():
    result = ExecutionPolicyResolver().resolve(
        make_policy(
            timeout=30,
            attempts=2,
            workers=2,
        ),
        RuntimeExecutionLimits(
            timeout_seconds=120,
            max_attempts=10,
            max_workers=16,
        ),
    )

    assert result.ready
    assert result.policy is not None

    assert result.policy.timeout_seconds == 30
    assert result.policy.max_attempts == 2
    assert result.policy.max_workers == 2


def test_missing_task_policy_uses_runtime_limits():
    result = ExecutionPolicyResolver().resolve(
        None,
        RuntimeExecutionLimits(
            timeout_seconds=45,
            max_attempts=4,
            max_workers=6,
        ),
    )

    assert result.ready
    assert result.policy is not None

    assert result.policy.timeout_seconds == 45
    assert result.policy.max_attempts == 4
    assert result.policy.max_workers == 6


def test_missing_task_policy_without_limits_uses_runtime_defaults():
    result = ExecutionPolicyResolver().resolve(
        None,
        RuntimeExecutionLimits(),
    )

    assert result.ready
    assert result.policy is not None

    assert result.policy.timeout_seconds is None
    assert result.policy.max_attempts == 1
    assert result.policy.max_workers == 1


def test_failure_and_rollback_modes_are_preserved():
    result = ExecutionPolicyResolver().resolve(
        make_policy(
            failure=FailureMode.ROLLBACK,
            rollback=RollbackMode.OPTIONAL,
        ),
        RuntimeExecutionLimits(),
    )

    assert result.ready
    assert result.policy is not None

    assert (
        result.policy.failure_mode
        is FailureMode.ROLLBACK
    )

    assert (
        result.policy.rollback_mode
        is RollbackMode.OPTIONAL
    )


def test_invalid_task_timeout_is_rejected():
    result = ExecutionPolicyResolver().resolve(
        make_policy(
            timeout=0,
        ),
        RuntimeExecutionLimits(),
    )

    assert result.status is ExecutionPolicyStatus.INVALID
    assert result.policy is None


def test_invalid_runtime_limit_type_is_rejected():
    try:
        ExecutionPolicyResolver().resolve(
            None,
            runtime_limits=123,
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Invalid runtime limits were accepted."
        )


def test_invalid_task_policy_type_is_rejected():
    try:
        ExecutionPolicyResolver().resolve(
            task_policy="invalid",
            runtime_limits=RuntimeExecutionLimits(),
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Invalid task execution policy was accepted."
        )


TESTS = [
    test_task_policy_without_runtime_limits_is_preserved,
    test_runtime_limits_restrict_timeout,
    test_runtime_limits_restrict_retry_attempts,
    test_runtime_limits_restrict_parallelism,
    test_runtime_limits_do_not_expand_task_policy,
    test_missing_task_policy_uses_runtime_limits,
    test_missing_task_policy_without_limits_uses_runtime_defaults,
    test_failure_and_rollback_modes_are_preserved,
    test_invalid_task_timeout_is_rejected,
    test_invalid_runtime_limit_type_is_rejected,
    test_invalid_task_policy_type_is_rejected,
]


def main():
    print("=" * 70)
    print("EXECUTION POLICY TESTS")
    print("=" * 70)

    passed = 0

    for test in TESTS:
        try:
            test()
            print(
                f"[PASS] {test.__name__}"
            )
            passed += 1
        except Exception as exc:
            print(
                f"[FAIL] {test.__name__}"
            )
            print(
                f"       {type(exc).__name__}: {exc}"
            )

    print()
    print(
        f"Tests: {passed}/{len(TESTS)}"
    )

    if passed == len(TESTS):
        print(
            "EXECUTION POLICY: PASS"
        )
    else:
        print(
            "EXECUTION POLICY: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())