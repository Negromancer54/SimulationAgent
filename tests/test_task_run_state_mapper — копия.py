from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from runtime.execution import ExecutionStatus
from runtime.task_run import (
    TaskIntegrity,
    TaskStatus,
)
from runtime.task_run_state_mapper import (
    TaskRunStateMapper,
)


def test_succeeded_maps_to_succeeded():
    mapping = TaskRunStateMapper.map(
        ExecutionStatus.SUCCEEDED
    )

    assert mapping.task_status is TaskStatus.SUCCEEDED
    assert mapping.integrity is None
    assert mapping.changes_task_status is True
    assert mapping.changes_integrity is False


def test_failed_maps_to_failed():
    mapping = TaskRunStateMapper.map(
        ExecutionStatus.FAILED
    )

    assert mapping.task_status is TaskStatus.FAILED
    assert mapping.integrity is None


def test_infrastructure_error_maps_to_failed():
    mapping = TaskRunStateMapper.map(
        ExecutionStatus.INFRASTRUCTURE_ERROR
    )

    assert mapping.task_status is TaskStatus.FAILED
    assert mapping.integrity is None


def test_cancelled_maps_to_cancelled():
    mapping = TaskRunStateMapper.map(
        ExecutionStatus.CANCELLED
    )

    assert mapping.task_status is TaskStatus.CANCELLED
    assert mapping.integrity is None


def test_blocked_does_not_map_to_failed():
    mapping = TaskRunStateMapper.map(
        ExecutionStatus.BLOCKED
    )

    assert mapping.task_status is None
    assert mapping.integrity is None
    assert mapping.changes_task_status is False
    assert mapping.changes_integrity is False


def test_mapper_never_infers_integrity():
    statuses = (
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.INFRASTRUCTURE_ERROR,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.BLOCKED,
    )

    for status in statuses:
        mapping = TaskRunStateMapper.map(status)

        assert mapping.integrity is None


def test_invalid_status_type_is_rejected():
    try:
        TaskRunStateMapper.map(
            "SUCCEEDED"
        )
    except TypeError:
        return

    raise AssertionError(
        "Invalid execution status type must be rejected."
    )


TESTS = [
    test_succeeded_maps_to_succeeded,
    test_failed_maps_to_failed,
    test_infrastructure_error_maps_to_failed,
    test_cancelled_maps_to_cancelled,
    test_blocked_does_not_map_to_failed,
    test_mapper_never_infers_integrity,
    test_invalid_status_type_is_rejected,
]


def main():
    print("=" * 70)
    print("TASK RUN STATE MAPPER TESTS")
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
            "TASK RUN STATE MAPPER: PASS"
        )
    else:
        print(
            "TASK RUN STATE MAPPER: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())