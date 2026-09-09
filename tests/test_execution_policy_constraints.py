from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from runtime.execution_policy import (
    HandlerExecutionPolicy,
    ResourcePolicy,
)
from agent_task_v3 import (
    FailureMode,
    RollbackMode,
)


def test_empty_constraint():
    policy = HandlerExecutionPolicy()

    assert policy.timeout_seconds is None
    assert policy.max_attempts is None
    assert policy.max_workers is None
    assert policy.resources is None
    assert policy.failure_mode is None
    assert policy.rollback_mode is None


def test_valid_numeric_constraints():
    policy = HandlerExecutionPolicy(
        timeout_seconds=30,
        max_attempts=3,
        max_workers=4,
    )

    assert policy.timeout_seconds == 30
    assert policy.max_attempts == 3
    assert policy.max_workers == 4


def test_valid_resource_constraint():
    policy = HandlerExecutionPolicy(
        resources=ResourcePolicy(
            values={
                "cpu": 4,
                "memory": 8192,
            }
        )
    )

    assert policy.resources is not None
    assert policy.resources.values == {
        "cpu": 4,
        "memory": 8192,
    }


def test_valid_failure_and_rollback_constraints():
    policy = HandlerExecutionPolicy(
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
    )

    assert policy.failure_mode is FailureMode.ABORT
    assert policy.rollback_mode is RollbackMode.REQUIRED


def test_invalid_timeout_is_rejected():
    try:
        HandlerExecutionPolicy(timeout_seconds=0)
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for invalid timeout."
    )


def test_invalid_max_attempts_is_rejected():
    try:
        HandlerExecutionPolicy(max_attempts=-1)
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for invalid max_attempts."
    )


def test_invalid_max_workers_is_rejected():
    try:
        HandlerExecutionPolicy(max_workers=True)
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for invalid max_workers."
    )


def test_invalid_resources_type_is_rejected():
    try:
        HandlerExecutionPolicy(resources={})
    except TypeError:
        return

    raise AssertionError(
        "Expected TypeError for invalid resources."
    )


def test_invalid_failure_mode_is_rejected():
    try:
        HandlerExecutionPolicy(
            failure_mode="ABORT"
        )
    except TypeError:
        return

    raise AssertionError(
        "Expected TypeError for invalid failure_mode."
    )


def test_invalid_rollback_mode_is_rejected():
    try:
        HandlerExecutionPolicy(
            rollback_mode="REQUIRED"
        )
    except TypeError:
        return

    raise AssertionError(
        "Expected TypeError for invalid rollback_mode."
    )


def test_handler_spec_preserves_execution_policy():
    from registries.handler_registry import (
        HandlerSpec,
    )

    policy = HandlerExecutionPolicy(
        timeout_seconds=20,
        max_attempts=2,
        max_workers=3,
    )

    spec = HandlerSpec(
        handler_id="handler.test",
        goal_identifier="goal.test",
        goal_version=1,
        execution_policy=policy,
    )

    assert spec.execution_policy is policy


def test_handler_registry_state_changes_preserve_execution_policy():
    from registries.handler_registry import (
        HandlerRegistry,
        HandlerSpec,
    )

    policy = HandlerExecutionPolicy(
        timeout_seconds=20,
        max_attempts=2,
        max_workers=3,
    )

    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="handler.test",
            goal_identifier="goal.test",
            goal_version=1,
            execution_policy=policy,
        )
    )

    registry.disable("handler.test")

    disabled = registry.get("handler.test")

    assert disabled is not None
    assert disabled.execution_policy is policy

    registry.deprecate("handler.test")

    deprecated = registry.get("handler.test")

    assert deprecated is not None
    assert deprecated.execution_policy is policy


TESTS = (
    test_empty_constraint,
    test_valid_numeric_constraints,
    test_valid_resource_constraint,
    test_valid_failure_and_rollback_constraints,
    test_invalid_timeout_is_rejected,
    test_invalid_max_attempts_is_rejected,
    test_invalid_max_workers_is_rejected,
    test_invalid_resources_type_is_rejected,
    test_invalid_failure_mode_is_rejected,
    test_invalid_rollback_mode_is_rejected,
    test_handler_spec_preserves_execution_policy,
    test_handler_registry_state_changes_preserve_execution_policy,
)


def main() -> int:
    print("=" * 70)
    print("EXECUTION POLICY CONSTRAINT TESTS")
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
        print("EXECUTION POLICY CONSTRAINTS: FAIL")
        return 1

    print("EXECUTION POLICY CONSTRAINTS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
