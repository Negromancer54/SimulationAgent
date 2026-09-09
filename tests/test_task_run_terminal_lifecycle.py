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
    TaskRun,
    TaskRunStatus,
    TaskRunTransitionError,
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
        task_id="task-run-terminal-lifecycle-test",
        description="Verify terminal TaskRun lifecycle.",
        intent=intent,
    )


def make_executor() -> TaskRunExecutor:
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
        runtime_execution_limits=RuntimeExecutionLimits(
            max_attempts=3,
            max_workers=2,
        ),
    )


def test_failed_task_run_is_terminal() -> None:
    executor = make_executor()

    def failing_handler(step):
        raise RuntimeError("terminal failure")

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: failing_handler,
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.terminal


def test_completed_task_run_is_terminal() -> None:
    executor = make_executor()

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED
    assert result.run.terminal
    assert result.run.successful


def test_failed_task_run_rejects_further_phase_transition() -> None:
    executor = make_executor()

    def failing_handler(step):
        raise RuntimeError("terminal failure")

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: failing_handler,
        },
    )

    assert result.run.status is TaskRunStatus.FAILED

    history_before = list(result.run.history)

    try:
        result.run.transition(TaskRunStatus.EXECUTING)
    except TaskRunTransitionError:
        pass
    else:
        raise AssertionError(
            "FAILED TaskRun accepted a further lifecycle transition."
        )

    assert result.run.history == history_before
    assert result.run.status is TaskRunStatus.FAILED


def test_completed_task_run_rejects_further_phase_transition() -> None:
    executor = make_executor()

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.run.status is TaskRunStatus.COMPLETED

    history_before = list(result.run.history)

    try:
        result.run.transition(TaskRunStatus.EXECUTING)
    except TaskRunTransitionError:
        pass
    else:
        raise AssertionError(
            "COMPLETED TaskRun accepted a further lifecycle transition."
        )

    assert result.run.history == history_before
    assert result.run.status is TaskRunStatus.COMPLETED


def test_terminal_failed_run_does_not_become_running_via_cancel() -> None:
    executor = make_executor()

    def failing_handler(step):
        raise RuntimeError("terminal failure")

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: failing_handler,
        },
    )

    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.task_status.value == "FAILED"

    history_before = list(result.run.history)

    result.run.cancel()

    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.task_status.value == "FAILED"
    assert result.run.history == history_before


def test_new_execute_creates_new_terminal_lifecycle() -> None:
    executor = make_executor()

    result_1 = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.completed
    assert result_1.run.status is TaskRunStatus.COMPLETED

    history_1 = list(result_1.run.history)

    result_2 = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_2.completed
    assert result_2.run.status is TaskRunStatus.COMPLETED

    assert result_1.run is not result_2.run
    assert result_1.run.history == history_1
    assert result_2.run.history[0] is TaskRunStatus.CREATED
