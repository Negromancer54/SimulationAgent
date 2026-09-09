from __future__ import annotations

from pathlib import Path

from agent import run_task_v3
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
from runtime.task_run_executor import TaskRunExecutorResult
from runtime.v3_registry import (
    FILE_WRITE_GOAL_ID,
    FILE_WRITE_GOAL_VERSION,
)


PROJECT_ROOT = Path(
    r"C:\Users\Gycha\SimulationZero-Cpp"
)


def make_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="agent-v3-entrypoint-test",
        description="Test the V3 agent entrypoint.",
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=TaskTarget(
                kind=TargetKind.PROJECT,
                identifier="simulation_zero",
                scope=TaskScope(
                    project="SimulationZero-Cpp",
                ),
            ),
            goal=TaskGoal(
                identifier=FILE_WRITE_GOAL_ID,
                kind=GoalKind.OUTCOME,
                version=FILE_WRITE_GOAL_VERSION,
                parameters={
                    "path": (
                        "Temp/"
                        "agent_v3_entrypoint_test.txt"
                    ),
                    "content": (
                        "agent.run_task_v3() test."
                    ),
                },
            ),
        ),
    )


def test_run_task_v3_uses_production_runtime() -> None:
    task = make_task()

    result = run_task_v3(task)

    assert isinstance(
        result,
        TaskRunExecutorResult,
    )
    assert result.completed

    target = (
        PROJECT_ROOT
        / "Temp"
        / "agent_v3_entrypoint_test.txt"
    )

    try:
        assert target.is_file()
        assert target.read_text(
            encoding="utf-8",
        ) == "agent.run_task_v3() test."
    finally:
        if target.exists():
            target.unlink()

        parent = target.parent

        while parent != PROJECT_ROOT:
            try:
                parent.rmdir()
            except OSError:
                break

            parent = parent.parent
