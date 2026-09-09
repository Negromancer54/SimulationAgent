from runtime.task_run import TaskPhase, V3TaskPhase
from runtime.task_run_phase_mapper import TaskRunPhaseMapper


def test_legacy_phase_to_v3_phase_mapping():
    assert (
        TaskRunPhaseMapper.map_legacy_phase(TaskPhase.CREATED)
        is V3TaskPhase.PRECHECK
    )
    assert (
        TaskRunPhaseMapper.map_legacy_phase(TaskPhase.VALIDATING)
        is V3TaskPhase.PRECHECK
    )
    assert (
        TaskRunPhaseMapper.map_legacy_phase(TaskPhase.RESOLVING)
        is V3TaskPhase.RESOLUTION
    )
    assert (
        TaskRunPhaseMapper.map_legacy_phase(TaskPhase.PLANNING)
        is V3TaskPhase.PLANNING
    )
    assert (
        TaskRunPhaseMapper.map_legacy_phase(
            TaskPhase.CHECKING_PRECONDITIONS
        )
        is V3TaskPhase.PRECHECK
    )
    assert (
        TaskRunPhaseMapper.map_legacy_phase(TaskPhase.EXECUTING)
        is V3TaskPhase.EXECUTION
    )
    assert (
        TaskRunPhaseMapper.map_legacy_phase(
            TaskPhase.POST_EXECUTION
        )
        is V3TaskPhase.POST_EXECUTION
    )


def test_evaluating_has_no_single_v3_phase_equivalent():
    assert (
        TaskRunPhaseMapper.map_legacy_phase(TaskPhase.EVALUATING)
        is None
    )


def test_terminal_legacy_phases_map_to_v3_complete():
    assert (
        TaskRunPhaseMapper.map_legacy_phase(TaskPhase.COMPLETED)
        is V3TaskPhase.COMPLETE
    )
    assert (
        TaskRunPhaseMapper.map_legacy_phase(TaskPhase.FAILED)
        is V3TaskPhase.COMPLETE
    )