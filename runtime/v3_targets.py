from __future__ import annotations

from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)
from agent_task_v3 import TargetKind


SIMULATION_ZERO_TARGET_ID = "simulation_zero"
SIMULATION_ZERO_PROJECT = "SimulationZero-Cpp"


def register_v3_targets(
    directory: TargetDirectory,
) -> None:
    directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier=SIMULATION_ZERO_TARGET_ID,
            scope=SIMULATION_ZERO_PROJECT,
        )
    )