from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    ExecutionPolicy,
    FailureMode,
    FailurePolicy,
    ParallelismPolicy,
    ResourcePolicy as TaskResourcePolicy,
    RetryPolicy,
    RollbackMode,
    RollbackPolicy,
    TimeoutPolicy,
)

from runtime.execution_policy import (
    EffectiveExecutionPolicy,
    ExecutionPolicyResolver,
    ExecutionPolicyStatus,
    ResourcePolicy,
    RuntimeExecutionLimits,
)


def make_task_policy() -> ExecutionPolicy:
    return ExecutionPolicy(
        timeout=TimeoutPolicy(
            total_seconds=60,
        ),
        retry=RetryPolicy(
            max_attempts=3,
        ),
        parallelism=ParallelismPolicy(
            max_workers=4,
        ),
        resources=TaskResourcePolicy(
            values={},
        ),
        failure=FailurePolicy(
            mode=FailureMode.ABORT,
        ),
        rollback=RollbackPolicy(
            mode=RollbackMode.REQUIRED,
        ),
    )


def test_empty_resource_policy():
    policy = ResourcePolicy(
        values={}
    )

    assert policy.values == {}


def test_single_resource_limit():
    policy = ResourcePolicy(
        values={
            "memory_mb": 4096,
        }
    )

    assert policy.values == {
        "memory_mb": 4096,
    }


def test_multiple_resource_limits():
    policy = ResourcePolicy(
        values={
            "memory_mb": 4096,
            "cpu_threads": 4,
            "disk_mb": 10240,
        }
    )

    assert policy.values == {
        "memory_mb": 4096,
        "cpu_threads": 4,
        "disk_mb": 10240,
    }


def test_runtime_resource_limits_are_preserved():
    runtime_limits = RuntimeExecutionLimits(
        resources=ResourcePolicy(
            values={
                "memory_mb": 2048,
                "cpu_threads": 2,
            }
        )
    )

    result = ExecutionPolicyResolver().resolve(
        make_task_policy(),
        runtime_limits,
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None
    assert isinstance(
        result.policy,
        EffectiveExecutionPolicy,
    )
    assert result.policy.resources.values == {
        "memory_mb": 2048,
        "cpu_threads": 2,
    }


def test_runtime_resource_limits_are_available_without_task_policy():
    runtime_limits = RuntimeExecutionLimits(
        resources=ResourcePolicy(
            values={
                "memory_mb": 2048,
                "cpu_threads": 2,
            }
        )
    )

    result = ExecutionPolicyResolver().resolve(
        None,
        runtime_limits,
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None
    assert result.policy.resources.values == {
        "memory_mb": 2048,
        "cpu_threads": 2,
    }


def test_task_policy_without_runtime_resources_has_empty_runtime_resources():
    result = ExecutionPolicyResolver().resolve(
        make_task_policy(),
        RuntimeExecutionLimits(),
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None
    assert result.policy.resources.values == {}


def test_runtime_resource_policy_is_not_mixed_with_capabilities():
    runtime_limits = RuntimeExecutionLimits(
        resources=ResourcePolicy(
            values={
                "cpu_threads": 2,
            }
        )
    )

    result = ExecutionPolicyResolver().resolve(
        None,
        runtime_limits,
    )

    assert result.status is ExecutionPolicyStatus.READY
    assert result.policy is not None
    assert "cpu_threads" in result.policy.resources.values


def test_invalid_resource_policy_is_rejected_at_construction():
    try:
        ResourcePolicy(
            values={
                "memory_mb": 0,
            }
        )
    except ValueError:
        return

    raise AssertionError(
        "ResourcePolicy must reject non-positive limits."
    )


TESTS = [
    test_empty_resource_policy,
    test_single_resource_limit,
    test_multiple_resource_limits,
    test_runtime_resource_limits_are_preserved,
    test_runtime_resource_limits_are_available_without_task_policy,
    test_task_policy_without_runtime_resources_has_empty_runtime_resources,
    test_runtime_resource_policy_is_not_mixed_with_capabilities,
    test_invalid_resource_policy_is_rejected_at_construction,
]


def main():
    print("=" * 70)
    print("RESOURCE POLICY TESTS")
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
            "RESOURCE POLICY: PASS"
        )
    else:
        print(
            "RESOURCE POLICY: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())