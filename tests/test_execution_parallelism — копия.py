from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    GoalKind,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    TargetKind,
)

from runtime.execution_plan import (
    PlanStep,
)
from runtime.scheduler import (
    Scheduler,
)


def make_step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        handler_id=f"handler.{step_id}",
        target_kind="PROJECT",
        target_identifier="project",
        goal_identifier="test.goal",
        goal_version=1,
        depends_on=depends_on,
    )


def test_single_step_creates_one_batch():
    schedule = Scheduler().build(
        (make_step("step.1"),),
        max_workers=1,
    )

    assert len(schedule.batches) == 1
    assert schedule.batches[0].steps == (
        make_step("step.1"),
    )


def test_independent_steps_share_batch_up_to_worker_limit():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
        make_step("step.4"),
    )

    schedule = Scheduler().build(
        steps,
        max_workers=2,
    )

    assert len(schedule.batches) == 2

    assert schedule.batches[0].steps == (
        steps[0],
        steps[1],
    )

    assert schedule.batches[1].steps == (
        steps[2],
        steps[3],
    )


def test_large_worker_limit_does_not_split_independent_steps():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    schedule = Scheduler().build(
        steps,
        max_workers=10,
    )

    assert len(schedule.batches) == 1
    assert schedule.batches[0].steps == steps


def test_dependency_delays_step_until_dependency_batch_completes():
    steps = (
        make_step("step.1"),
        make_step(
            "step.2",
            depends_on=("step.1",),
        ),
        make_step("step.3"),
    )

    schedule = Scheduler().build(
        steps,
        max_workers=2,
    )

    assert len(schedule.batches) == 2

    assert schedule.batches[0].steps == (
        steps[0],
        steps[2],
    )

    assert schedule.batches[1].steps == (
        steps[1],
    )


def test_dependency_chain_creates_sequential_batches():
    steps = (
        make_step("step.1"),
        make_step(
            "step.2",
            depends_on=("step.1",),
        ),
        make_step(
            "step.3",
            depends_on=("step.2",),
        ),
    )

    schedule = Scheduler().build(
        steps,
        max_workers=8,
    )

    assert len(schedule.batches) == 3

    assert schedule.batches[0].steps == (
        steps[0],
    )

    assert schedule.batches[1].steps == (
        steps[1],
    )

    assert schedule.batches[2].steps == (
        steps[2],
    )


def test_schedule_preserves_plan_order_for_eligible_steps():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    schedule = Scheduler().build(
        steps,
        max_workers=2,
    )

    assert schedule.batches[0].steps == (
        steps[0],
        steps[1],
    )

    assert schedule.batches[1].steps == (
        steps[2],
    )


def test_zero_workers_are_rejected():
    try:
        Scheduler().build(
            (),
            max_workers=0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "max_workers=0 was accepted."
        )


def test_invalid_worker_type_is_rejected():
    try:
        Scheduler().build(
            (),
            max_workers="2",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Invalid max_workers type was accepted."
        )


def test_cyclic_dependency_is_rejected():
    steps = (
        make_step(
            "step.1",
            depends_on=("step.2",),
        ),
        make_step(
            "step.2",
            depends_on=("step.1",),
        ),
    )

    try:
        Scheduler().build(
            steps,
            max_workers=2,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Cyclic dependency was accepted."
        )


TESTS = [
    test_single_step_creates_one_batch,
    test_independent_steps_share_batch_up_to_worker_limit,
    test_large_worker_limit_does_not_split_independent_steps,
    test_dependency_delays_step_until_dependency_batch_completes,
    test_dependency_chain_creates_sequential_batches,
    test_schedule_preserves_plan_order_for_eligible_steps,
    test_zero_workers_are_rejected,
    test_invalid_worker_type_is_rejected,
    test_cyclic_dependency_is_rejected,
]


def main():
    print("=" * 70)
    print("EXECUTION PARALLELISM TESTS")
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
            "EXECUTION PARALLELISM: PASS"
        )
    else:
        print(
            "EXECUTION PARALLELISM: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())