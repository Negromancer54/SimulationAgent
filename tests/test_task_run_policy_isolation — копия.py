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
    TargetKind,
    TaskV3,
)

from registries.goal_registry import (
    GoalRegistry,
    GoalSpec,
)

from registries.handler_registry import (
    HandlerApplicability,
    HandlerExecutionPolicy,
    HandlerRegistry,
    HandlerSpec,
)

from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)

from runtime.assertions import AssertionRegistry

from runtime.execution_policy import (
    RuntimeExecutionLimits,
)

from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
)

from runtime.task_run import (
    TaskRunStatus,
)

from runtime.task_run_executor import (
    TaskRunExecutor,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


def make_task(task_id: str) -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp",
        ),
    )

    goal = TaskGoal(
        identifier=GOAL_ID,
        kind=GoalKind.OUTCOME,
        version=GOAL_VERSION,
        parameters={},
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id=task_id,
        description="Verify policy isolation across attempts.",
        intent=intent,
    )


def make_executor(
    runtime_limits: RuntimeExecutionLimits,
) -> TaskRunExecutor:
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="Add the generic component API.",
            owner="PROJECT",
        )
    )

    target_directory = TargetDirectory()

    target_directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    handler_registry = HandlerRegistry()

    handler_registry.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,),
            ),
            execution_policy=HandlerExecutionPolicy(
                max_attempts=5,
                max_workers=4,
            ),
        )
    )

    return TaskRunExecutor(
        goal_registry,
        target_directory,
        handler_registry,
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        AssertionRegistry(),
        runtime_execution_limits=runtime_limits,
    )


def test_policy_isolated_between_task_runs() -> None:
    executor_1 = make_executor(
        RuntimeExecutionLimits(
            max_attempts=5,
            max_workers=4,
        )
    )

    result_1 = executor_1.execute(
        make_task("attempt-1"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_1.run.status is TaskRunStatus.COMPLETED
    assert result_1.run.effective_execution_policy is not None

    policy_1 = result_1.run.effective_execution_policy

    assert policy_1.max_attempts == 5
    assert policy_1.max_workers == 4

    executor_2 = make_executor(
        RuntimeExecutionLimits(
            max_attempts=2,
            max_workers=1,
        )
    )

    result_2 = executor_2.execute(
        make_task("attempt-2"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_2.completed
    assert result_2.run.status is TaskRunStatus.COMPLETED
    assert result_2.run.effective_execution_policy is not None

    policy_2 = result_2.run.effective_execution_policy

    assert policy_2.max_attempts == 2
    assert policy_2.max_workers == 1

    assert policy_1.max_attempts == 5
    assert policy_1.max_workers == 4


def test_previous_execution_result_keeps_original_policy() -> None:
    executor_1 = make_executor(
        RuntimeExecutionLimits(
            max_attempts=5,
            max_workers=4,
        )
    )

    result_1 = executor_1.execute(
        make_task("attempt-1"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_1.run.execution is not None
    assert result_1.run.execution.policy is not None

    previous_policy = result_1.run.execution.policy

    executor_2 = make_executor(
        RuntimeExecutionLimits(
            max_attempts=2,
            max_workers=1,
        )
    )

    result_2 = executor_2.execute(
        make_task("attempt-2"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_2.completed
    assert result_2.run.execution is not None
    assert result_2.run.execution.policy is not None

    assert previous_policy.max_attempts == 5
    assert previous_policy.max_workers == 4

    assert result_2.run.execution.policy.max_attempts == 2
    assert result_2.run.execution.policy.max_workers == 1


def test_previous_task_run_remains_terminal_after_new_attempt() -> None:
    executor_1 = make_executor(
        RuntimeExecutionLimits(
            max_attempts=5,
            max_workers=4,
        )
    )

    result_1 = executor_1.execute(
        make_task("attempt-1"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_1.run.terminal
    assert result_1.run.status is TaskRunStatus.COMPLETED

    executor_2 = make_executor(
        RuntimeExecutionLimits(
            max_attempts=2,
            max_workers=1,
        )
    )

    result_2 = executor_2.execute(
        make_task("attempt-2"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_2.completed
    assert result_2.run.terminal
    assert result_2.run is not result_1.run

    assert result_1.run.status is TaskRunStatus.COMPLETED
    assert result_1.run.terminal
