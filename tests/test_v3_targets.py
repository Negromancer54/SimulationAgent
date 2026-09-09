from __future__ import annotations

from agent_task_v3 import (
    TargetKind,
    TaskScope,
    TaskTarget,
)
from registries.target_directory import TargetDirectory
from runtime.v3_targets import (
    SIMULATION_ZERO_PROJECT,
    SIMULATION_ZERO_TARGET_ID,
    register_v3_targets,
)


def test_register_v3_targets_registers_simulation_zero() -> None:
    directory = TargetDirectory()

    register_v3_targets(directory)

    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier=SIMULATION_ZERO_TARGET_ID,
        scope=TaskScope(
            project=SIMULATION_ZERO_PROJECT,
        ),
    )

    assert directory.contains(target)

    candidates = directory.resolve_candidates(target)

    assert len(candidates) == 1
    assert candidates[0].kind is TargetKind.PROJECT
    assert candidates[0].identifier == SIMULATION_ZERO_TARGET_ID
    assert candidates[0].scope == SIMULATION_ZERO_PROJECT
