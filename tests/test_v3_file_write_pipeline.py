from __future__ import annotations

from pathlib import Path

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
from registries.handler_resolver import HandlerRuntimeContext
from runtime.v3_registry import (
    FILE_WRITE_GOAL_ID,
    FILE_WRITE_GOAL_VERSION,
)
from runtime.v3_runtime import V3Runtime


PROJECT_ROOT = Path(
    r"C:\Users\Gycha\SimulationZero-Cpp"
)


def make_file_write_task(
    relative_path: str,
    content: str,
) -> TaskV3:
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
            "path": relative_path,
            "content": content,
        },
    )

    return TaskV3(
        schema_version=3,
        task_id="v3-file-write-production-test",
        description=(
            "Write a file through the production V3 runtime."
        ),
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=target,
            goal=goal,
        ),
    )


def test_file_write_uses_default_v3_runtime(
    tmp_path: Path,
) -> None:
    runtime = V3Runtime.create_default()

    relative_path = (
        "Temp/"
        f"v3_production_{tmp_path.name}.txt"
    )
    content = "Production V3 runtime test."

    task = make_file_write_task(
        relative_path,
        content,
    )

    result = runtime.execute(
        task,
        handler_context=HandlerRuntimeContext(
            capabilities=frozenset(
                {"filesystem.write"}
            )
        ),
    )

    assert result.completed

    target = PROJECT_ROOT / relative_path

    try:
        assert target.is_file()
        assert target.read_text(
            encoding="utf-8",
        ) == content
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
