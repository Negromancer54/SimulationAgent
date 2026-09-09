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


def make_task() -> TaskV3:
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
        task_id="task-run-attempt-lifecycle-test",
        description="Verify independent TaskRun attempt lifecycles.",
        intent=intent,
    )


def make_target_directory() -> TargetDirectory:
    directory = TargetDirectory()

    directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    return directory


def make_handler_registry(
    execution_policy: HandlerExecutionPolicy | None = None,
) -> HandlerRegistry:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,),
            ),
            execution_policy=execution_policy,
        )
    )

    return registry


def make_executor(
    runtime_limits: RuntimeExecutionLimits,
    handler_policy: HandlerExecutionPolicy | None = None,
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

    return TaskRunExecutor(
        goal_registry,
        make_target_directory(),
        make_handler_registry(handler_policy),
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        AssertionRegistry(),
        runtime_execution_limits=runtime_limits,
    )


def test_two_execute_calls_create_independent_task_runs() -> None:
    executor = make_executor(
        RuntimeExecutionLimits(
            timeout_seconds=60,
            max_attempts=5,
            max_workers=2,
        )
    )

    task = make_task()

    result_1 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    result_2 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_2.completed

    assert result_1.run is not result_2.run
    assert result_1.run.task is task
    assert result_2.run.task is task


def test_task_run_histories_are_independent() -> None:
    executor = make_executor(
        RuntimeExecutionLimits(
            max_attempts=5,
            max_workers=2,
        )
    )

    task = make_task()

    result_1 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    result_2 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_2.completed

    assert result_1.run.history == result_2.run.history

    result_1.run.history.append(TaskRunStatus.FAILED)

    assert result_1.run.history != result_2.run.history
    assert TaskRunStatus.FAILED not in result_2.run.history


def test_task_run_evidence_stores_are_independent() -> None:
    executor = make_executor(
        RuntimeExecutionLimits(
            max_attempts=5,
            max_workers=2,
        )
    )

    task = make_task()

    result_1 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    result_2 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_2.completed

    assert result_1.run.evidence is not None
    assert result_2.run.evidence is not None

    assert result_1.run.evidence is not result_2.run.evidence

    assert result_1.run.evidence.count() == 1
    assert result_2.run.evidence.count() == 1


def test_task_run_execution_results_are_independent() -> None:
    executor = make_executor(
        RuntimeExecutionLimits(
            max_attempts=5,
            max_workers=2,
        )
    )

    task = make_task()

    result_1 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    result_2 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_2.completed

    assert result_1.run.execution is not None
    assert result_2.run.execution is not None

    assert result_1.run.execution is not result_2.run.execution


def test_task_run_policy_snapshots_are_independent() -> None:
    executor = make_executor(
        RuntimeExecutionLimits(
            timeout_seconds=60,
            max_attempts=5,
            max_workers=2,
        ),
        handler_policy=HandlerExecutionPolicy(
            timeout_seconds=45,
            max_attempts=4,
            max_workers=2,
        ),
    )

    task = make_task()

    result_1 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    result_2 = executor.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_2.completed

    policy_1 = result_1.run.effective_execution_policy
    policy_2 = result_2.run.effective_execution_policy

    assert policy_1 is not None
    assert policy_2 is not None

    assert policy_1 is result_1.run.execution.policy
    assert policy_2 is result_2.run.execution.policy

    assert policy_1 is not policy_2
    assert policy_1 == policy_2


def test_new_run_resolves_policy_again() -> None:
    task = make_task()

    executor_1 = make_executor(
        RuntimeExecutionLimits(
            timeout_seconds=60,
            max_attempts=5,
            max_workers=2,
        ),
        handler_policy=HandlerExecutionPolicy(
            max_attempts=5,
        ),
    )

    result_1 = executor_1.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_1.run.effective_execution_policy is not None
    assert result_1.run.effective_execution_policy.max_attempts == 5

    executor_2 = make_executor(
        RuntimeExecutionLimits(
            timeout_seconds=60,
            max_attempts=2,
            max_workers=2,
        ),
        handler_policy=HandlerExecutionPolicy(
            max_attempts=5,
        ),
    )

    result_2 = executor_2.execute(
        task,
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_2.completed
    assert result_2.run.effective_execution_policy is not None
    assert result_2.run.effective_execution_policy.max_attempts == 2

    assert result_1.run.effective_execution_policy is not None
    assert result_1.run.effective_execution_policy.max_attempts == 5
