from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    FailureMode,
    GoalKind,
    ParallelismPolicy,
    RollbackMode,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    TargetKind,
)

from runtime.execution import (
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
    PlanStep,
)
from runtime.execution_policy import (
    EffectiveExecutionPolicy,
)
from runtime.preconditions import (
    PreconditionsResult,
)


def make_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="scheduler-pipeline-test",
        description="Scheduler pipeline integration test.",
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=TaskTarget(
                kind=TargetKind.PROJECT,
                identifier="project",
                scope=TaskScope(
                    project="SimulationZero-Cpp"
                ),
            ),
            goal=TaskGoal(
                kind=GoalKind.OUTCOME,
                identifier="test.goal",
                version=1,
                parameters={},
            ),
        ),
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


def make_plan(
    steps: tuple[PlanStep, ...],
) -> ExecutionPlan:
    return ExecutionPlan(
        status=PlanStatus.READY,
        task=make_task(),
        steps=steps,
    )


def make_policy(
    max_workers: int,
) -> EffectiveExecutionPolicy:
    return EffectiveExecutionPolicy(
        timeout_seconds=None,
        max_attempts=1,
        max_workers=max_workers,
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
    )


def make_handlers(
    calls: list[str],
    *,
    failure_step: str | None = None,
):
    def make_handler(step_id: str):
        def handler(step):
            calls.append(step_id)

            if step_id == failure_step:
                raise RuntimeError(
                    f"failure in {step_id}"
                )

        return handler

    return {
        f"handler.{step.step_id}":
            make_handler(step.step_id)
        for step in [
            make_step("step.1"),
            make_step("step.2"),
            make_step("step.3"),
            make_step("step.4"),
        ]
    }


def test_scheduler_policy_is_applied_to_execution_order():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
        make_step("step.4"),
    )

    calls: list[str] = []

    result = ExecutionRuntime().execute(
        make_plan(steps),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: calls.append("step.1"),
            "handler.step.2": lambda step: calls.append("step.2"),
            "handler.step.3": lambda step: calls.append("step.3"),
            "handler.step.4": lambda step: calls.append("step.4"),
        },
        policy=make_policy(2),
    )

    assert result.status is ExecutionStatus.SUCCEEDED

    # Physical execution is still deterministic/sequential at this stage.
    assert calls == [
        "step.1",
        "step.2",
        "step.3",
        "step.4",
    ]

    assert result.completed_steps == (
        "step.1",
        "step.2",
        "step.3",
        "step.4",
    )


def test_dependencies_are_preserved_by_execution():
    steps = (
        make_step("step.1"),
        make_step(
            "step.2",
            depends_on=("step.1",),
        ),
        make_step("step.3"),
    )

    calls: list[str] = []

    result = ExecutionRuntime().execute(
        make_plan(steps),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: calls.append("step.1"),
            "handler.step.2": lambda step: calls.append("step.2"),
            "handler.step.3": lambda step: calls.append("step.3"),
        },
        policy=make_policy(2),
    )

    assert result.status is ExecutionStatus.SUCCEEDED

    assert calls.index("step.1") < calls.index("step.2")


def test_execution_result_preserves_deterministic_step_order():
    steps = (
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
    )

    result = ExecutionRuntime().execute(
        make_plan(steps),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: None,
            "handler.step.2": lambda step: None,
            "handler.step.3": lambda step: None,
        },
        policy=make_policy(2),
    )

    assert result.status is ExecutionStatus.SUCCEEDED

    assert tuple(
        item.step_id
        for item in result.step_results
    ) == (
        "step.1",
        "step.2",
        "step.3",
    )


def test_failure_stops_execution_after_failed_step():
    calls: list[str] = []

    result = ExecutionRuntime().execute(
        make_plan(
            (
                make_step("step.1"),
                make_step("step.2"),
                make_step("step.3"),
            )
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1":
                lambda step: calls.append("step.1"),

            "handler.step.2":
                lambda step: (
                    calls.append("step.2")
                    or (_ for _ in ()).throw(
                        RuntimeError("failure")
                    )
                ),

            "handler.step.3":
                lambda step: calls.append("step.3"),
        },
        policy=make_policy(2),
    )

    assert result.status is ExecutionStatus.FAILED

    assert calls == [
        "step.1",
        "step.2",
    ]

    assert result.completed_steps == (
        "step.1",
    )

    assert result.failed_step == "step.2"


def test_max_workers_one_preserves_single_step_execution_semantics():
    calls: list[str] = []

    result = ExecutionRuntime().execute(
        make_plan(
            (
                make_step("step.1"),
                make_step("step.2"),
                make_step("step.3"),
            )
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: calls.append("step.1"),
            "handler.step.2": lambda step: calls.append("step.2"),
            "handler.step.3": lambda step: calls.append("step.3"),
        },
        policy=make_policy(1),
    )

    assert result.status is ExecutionStatus.SUCCEEDED

    assert calls == [
        "step.1",
        "step.2",
        "step.3",
    ]


def test_policy_identity_is_preserved():
    policy = make_policy(3)

    result = ExecutionRuntime().execute(
        make_plan(
            (
                make_step("step.1"),
            )
        ),
        PreconditionsResult(
            evaluations=()
        ),
        handlers={
            "handler.step.1": lambda step: None,
        },
        policy=policy,
    )

    assert result.policy is policy


TESTS = [
    test_scheduler_policy_is_applied_to_execution_order,
    test_dependencies_are_preserved_by_execution,
    test_execution_result_preserves_deterministic_step_order,
    test_failure_stops_execution_after_failed_step,
    test_max_workers_one_preserves_single_step_execution_semantics,
    test_policy_identity_is_preserved,
]


def main():
    print("=" * 70)
    print("EXECUTION SCHEDULER PIPELINE TESTS")
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
            "EXECUTION SCHEDULER PIPELINE: PASS"
        )
    else:
        print(
            "EXECUTION SCHEDULER PIPELINE: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())