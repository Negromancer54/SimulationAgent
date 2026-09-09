from __future__ import annotations

from runtime.v3_runtime import V3Runtime
from runtime.v3_registry import (
    FILE_WRITE_GOAL_ID,
    FILE_WRITE_GOAL_VERSION,
)
from runtime.v3_targets import (
    SIMULATION_ZERO_PROJECT,
    SIMULATION_ZERO_TARGET_ID,
)


def test_v3_runtime_create_default_builds_production_runtime() -> None:
    runtime = V3Runtime.create_default()

    assert runtime.goal_registry.resolve(
        FILE_WRITE_GOAL_ID,
        FILE_WRITE_GOAL_VERSION,
    ).spec is not None

    assert runtime.handler_registry.contains(
        "file.write.handler"
    )

    from agent_task_v3 import (
        TargetKind,
        TaskScope,
        TaskTarget,
    )

    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier=SIMULATION_ZERO_TARGET_ID,
        scope=TaskScope(
            project=SIMULATION_ZERO_PROJECT,
        ),
    )

    assert runtime.target_directory.contains(target)
