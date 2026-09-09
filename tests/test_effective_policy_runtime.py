from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import TaskV3

from runtime.execution import (
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
    PlanStep,
    ResourceRequirements,
)
from runtime.execution_policy import (
    EffectiveExecutionPolicy,
    FailureMode,
    ResourcePolicy,
    RollbackMode,
)
from runtime.preconditions import PreconditionsResult


HANDLER_ID = "change.handler"


def make_task() -> TaskV3:
    from agent_task_v3 import (
        GoalKind,
        TaskGoal,
        TaskIntent,
        TaskOperation,
        TaskScope,
        TaskTarget,
        TargetKind,
    )

    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp",
        ),
    )

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=1,
        parameters={},
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id="effective-policy-runtime-test",
        description="Verify effective policy at execution-runtime level.",
        intent=intent,
    )


def make_preconditions() -> PreconditionsResult:
    return PreconditionsResult(
        evaluations=(),
        message="Synthetic satisfied preconditions.",
    )


def make_policy(
    *,
    timeout_seconds: int | None = None,
    max_attempts: int = 1,
    max_workers: int = 1,
    resources: dict[str, int] | None = None,
) -> EffectiveExecutionPolicy:
    return EffectiveExecutionPolicy(
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        max_workers=max_workers,
        failure_mode=FailureMode.ABORT,
        rollback_mode=RollbackMode.REQUIRED,
        resources=ResourcePolicy(
            values=(
                resources
                if resources is not None
                else {}
            )
        ),
    )


def make_step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    resources: dict[str, int] | None = None,
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        handler_id=HANDLER_ID,
        target_kind="PROJECT",
        target_identifier="simulation_zero",
        goal_identifier="component.add_generic_api",
        goal_version=1,
        depends_on=depends_on,
        resources=ResourceRequirements(
            resources=(
                resources
                if resources is not None
                else {}
            )
        ),
    )


def make_plan(
    *steps: PlanStep,
) -> ExecutionPlan:
    return ExecutionPlan(
        status=PlanStatus.READY,
        task=make_task(),
        steps=tuple(steps),
    )


def test_policy_snapshot_is_preserved_by_runtime() -> None:
    policy = make_policy(
        timeout_seconds=30,
        max_attempts=4,
        max_workers=3,
    )

    plan = make_plan(
        make_step("step.1"),
    )

    result = ExecutionRuntime().execute(
        plan,
        make_preconditions(),
        {HANDLER_ID: lambda step: None},
        policy=policy,
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.policy is policy


def test_effective_max_workers_controls_real_batches() -> None:
    plan = make_plan(
        make_step("step.1"),
        make_step("step.2"),
        make_step("step.3"),
        make_step("step.4"),
    )

    policy = make_policy(
        max_attempts=1,
        max_workers=2,
    )

    result = ExecutionRuntime().execute(
        plan,
        make_preconditions(),
        {HANDLER_ID: lambda step: None},
        policy=policy,
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.policy is policy
    assert result.schedule is not None

    assert len(result.schedule.batches) == 2
    assert result.schedule.batches[0].steps == (
        plan.steps[0],
        plan.steps[1],
    )
    assert result.schedule.batches[1].steps == (
        plan.steps[2],
        plan.steps[3],
    )

    assert result.completed_steps == (
        "step.1",
        "step.2",
        "step.3",
        "step.4",
    )


def test_effective_max_attempts_controls_runtime_retries() -> None:
    plan = make_plan(
        make_step("step.1"),
    )

    policy = make_policy(
        max_attempts=3,
        max_workers=1,
    )

    attempts = 0

    def failing_handler(step):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("retry failure")

    result = ExecutionRuntime().execute(
        plan,
        make_preconditions(),
        {HANDLER_ID: failing_handler},
        policy=policy,
    )

    assert result.status is ExecutionStatus.FAILED
    assert result.policy is policy
    assert len(result.step_results) == 1
    assert result.step_results[0].attempts == 3
    assert attempts == 3


def test_resource_admission_blocks_step_with_insufficient_resources() -> None:
    plan = make_plan(
        make_step(
            "step.1",
            resources={
                "gpu": 4,
            },
        ),
    )

    policy = make_policy(
        max_attempts=1,
        max_workers=1,
        resources={
            "gpu": 2,
        },
    )

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    result = ExecutionRuntime().execute(
        plan,
        make_preconditions(),
        {HANDLER_ID: handler},
        policy=policy,
    )

    assert result.status is ExecutionStatus.BLOCKED
    assert result.policy is policy
    assert result.completed_steps == ()
    assert result.failed_step == "step.1"
    assert len(result.step_results) == 1
    assert result.step_results[0].status is ExecutionStatus.BLOCKED
    assert result.step_results[0].attempts == 0
    assert calls == []
