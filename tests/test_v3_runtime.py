from __future__ import annotations

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
from registries.goal_registry import GoalRegistry
from registries.handler_registry import HandlerRegistry
from registries.target_directory import TargetDirectory
from registries.handler_resolver import HandlerRuntimeContext
from runtime.task_run_executor import TaskRunExecutor
from runtime.v3_registry import (
    FILE_WRITE_GOAL_ID,
    FILE_WRITE_GOAL_VERSION,
    register_v3_defaults,
)
from runtime.v3_runtime import V3Runtime
from runtime.v3_targets import register_v3_targets


def make_runtime() -> V3Runtime:
    goal_registry = GoalRegistry()
    handler_registry = HandlerRegistry()
    target_directory = TargetDirectory()

    register_v3_defaults(
        goal_registry,
        handler_registry,
    )
    register_v3_targets(
        target_directory,
    )

    return V3Runtime(
        goal_registry=goal_registry,
        target_directory=target_directory,
        handler_registry=handler_registry,
    )


def make_task() -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp",
        ),
    )

    goal = TaskGoal(
        identifier=FILE_WRITE_GOAL_ID,
        kind=GoalKind.OUTCOME,
        version=FILE_WRITE_GOAL_VERSION,
        parameters={
            "path": "Temp/v3_runtime_api_test.txt",
            "content": "V3Runtime.execute test.",
        },
    )

    return TaskV3(
        schema_version=3,
        task_id="v3-runtime-api-test",
        description="Test the public V3Runtime execution API.",
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=target,
            goal=goal,
        ),
    )


def test_v3_runtime_assembles_executor() -> None:
    runtime = make_runtime()

    assert isinstance(
        runtime.executor,
        TaskRunExecutor,
    )


def test_v3_runtime_execute_runs_production_handler() -> None:
    runtime = make_runtime()

    result = runtime.execute(
        make_task(),
        handler_context=HandlerRuntimeContext(
            capabilities=frozenset(
                {"filesystem.write"}
            )
        ),
    )

    assert result.completed

    from pathlib import Path

    target = (
        Path(r"C:\Users\Gycha\SimulationZero-Cpp")
        / "Temp"
        / "v3_runtime_api_test.txt"
    )

    try:
        assert target.is_file()
        assert target.read_text(
            encoding="utf-8",
        ) == "V3Runtime.execute test."
    finally:
        if target.exists():
            target.unlink()

        parent = target.parent

        while parent != Path(
            r"C:\Users\Gycha\SimulationZero-Cpp"
        ):
            try:
                parent.rmdir()
            except OSError:
                break

            parent = parent.parent


def test_v3_runtime_accepts_injected_registries() -> None:
    goal_registry = GoalRegistry()
    target_directory = TargetDirectory()
    handler_registry = HandlerRegistry()

    from runtime.assertions import AssertionRegistry
    from runtime.preconditions import PreconditionRegistry

    precondition_registry = PreconditionRegistry()
    assertion_registry = AssertionRegistry()

    runtime = V3Runtime(
        goal_registry=goal_registry,
        target_directory=target_directory,
        handler_registry=handler_registry,
        precondition_registry=precondition_registry,
        assertion_registry=assertion_registry,
    )

    assert runtime.precondition_registry is precondition_registry
    assert runtime.assertion_registry is assertion_registry
    assert isinstance(runtime.executor, TaskRunExecutor)
