from runtime.task_run import V3TaskIntegrity, V3TaskPhase
from agent_task_v3 import TaskV3
from runtime.task_run import TaskRun, V3TaskPhase, TaskPhase
from runtime.task_run import (
    FailureCode,
    Recoverability,
    TaskRun,
    TaskPhase,
    V3TaskIntegrity,
    V3TaskPhase,
    TaskStatus,
)
from runtime.execution import ExecutionStatus
from runtime.task_run_executor import TaskRunExecutor
def test_v3_task_phase_contract():
    assert [phase.value for phase in V3TaskPhase] == [
        "PRECHECK",
        "RESOLUTION",
        "PLANNING",
        "CHECKPOINT",
        "EXECUTION",
        "POST_EXECUTION",
        "EXPECTED_EVALUATION",
        "VALIDATION",
        "ROLLBACK",
        "COMPLETE",
    ]


def test_v3_task_integrity_contract():
    assert [integrity.value for integrity in V3TaskIntegrity] == [
        "PRESERVED",
        "DEGRADED",
        "UNKNOWN",
    ]



def test_task_run_has_independent_v3_phase():
    run = TaskRun(
        TaskV3(
            schema_version=1,
            task_id="TASK-V3-PHASE-001",
            description="V3 phase contract test.",
            intent={},
            preconditions=[],
            expected=[],
            validation=[],
            execution_policy={},
        )
    )

    assert run.v3_phase is V3TaskPhase.PRECHECK
    assert run.v3_lifecycle_phase is V3TaskPhase.PRECHECK


def test_task_run_can_set_v3_phase_independently():
    run = TaskRun(
        TaskV3(
            schema_version=1,
            task_id="TASK-V3-PHASE-002",
            description="V3 phase mutation test.",
            intent={},
            preconditions=[],
            expected=[],
            validation=[],
            execution_policy={},
        )
    )

    run.set_v3_phase(V3TaskPhase.EXECUTION)

    assert run.v3_phase is V3TaskPhase.EXECUTION
    assert run.phase is TaskPhase.CREATED
    
def test_v3_runtime_reaches_complete_v3_phase():
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
    from runtime.v3_targets import register_v3_targets
    from registries.goal_registry import GoalRegistry
    from registries.handler_registry import HandlerRegistry
    from registries.target_directory import TargetDirectory
    from runtime.task_run import V3TaskPhase

    goal_registry = GoalRegistry()
    handler_registry = HandlerRegistry()
    target_directory = TargetDirectory()

    from runtime.v3_registry import register_v3_defaults

    register_v3_defaults(
        goal_registry,
        handler_registry,
    )
    register_v3_targets(
        target_directory,
    )

    runtime = V3Runtime(
        goal_registry=goal_registry,
        target_directory=target_directory,
        handler_registry=handler_registry,
    )

    task = TaskV3(
        schema_version=3,
        task_id="v3-phase-integration-test",
        description="Verify V3 lifecycle phase integration.",
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
                    "path": "Temp/v3_phase_integration_test.txt",
                    "content": "V3 phase integration test.",
                },
            ),
        ),
    )

    result = runtime.execute(
        task,
        handler_context=HandlerRuntimeContext(
            capabilities=frozenset(
                {"filesystem.write"}
            )
        ),
    )

    target = (
        Path(r"C:\Users\Gycha\SimulationZero-Cpp")
        / "Temp"
        / "v3_phase_integration_test.txt"
    )

    try:
        assert result.completed
        assert result.run.v3_phase is V3TaskPhase.COMPLETE
        assert result.run.v3_lifecycle_phase is V3TaskPhase.COMPLETE
        assert result.run.task_status.value == "SUCCEEDED"
    finally:
        if target.exists():
            target.unlink()
def test_failure_code_contract():
    assert [code.value for code in FailureCode] == [
        "TASK.INVALID",
        "TASK.MISSING_FIELD",
        "RESOLUTION.UNKNOWN_GOAL",
        "RESOLUTION.UNKNOWN_TARGET",
        "RESOLUTION.HANDLER_UNAVAILABLE",
        "RESOLUTION.HANDLER_AMBIGUOUS",
        "PRECONDITION.FAILED",
        "PRECONDITION.UNAVAILABLE",
        "PRECONDITION.ERROR",
        "PRECONDITION.CONFLICT",
        "PLANNING.FAILED",
        "EXECUTION.FAILED",
        "EXECUTION.TIMEOUT",
        "EXECUTION.CANCELLED",
        "EXECUTION.PROCESS_TERMINATION_FAILED",
        "EXPECTED.NOT_SATISFIED",
        "EXPECTED.UNAVAILABLE",
        "EXPECTED.ERROR",
        "VALIDATION.INVALID",
        "VALIDATION.INSUFFICIENT",
        "VALIDATION.ERROR",
        "ROLLBACK.FAILED",
        "INFRASTRUCTURE.ERROR",
    ]


def test_recoverability_contract():
    assert [item.value for item in Recoverability] == [
        "NON_RECOVERABLE",
        "RETRYABLE",
        "USER_ACTION_REQUIRED",
        "ROLLBACK_REQUIRED",
    ]
def test_v3_result_dimensions_default_state():
    run = TaskRun(
        TaskV3(
            schema_version=1,
            task_id="TASK-V3-RESULT-DIMENSIONS",
            description="V3 result dimensions contract test.",
            intent={},
            preconditions=[],
            expected=[],
            validation=[],
            execution_policy={},
        )
    )

    assert run.failure_code is None
    assert run.recoverability is None
    assert run.v3_integrity is V3TaskIntegrity.UNKNOWN
def test_v3_failure_sets_failure_code_and_recoverability():
    run = TaskRun(
        TaskV3(
            schema_version=1,
            task_id="TASK-V3-RESULT-DIMENSIONS",
            description="V3 result dimensions contract test.",
            intent={},
            preconditions=[],
            expected=[],
            validation=[],
            execution_policy={},
        )
    )

    run.set_failure(
        FailureCode.EXECUTION_TIMEOUT,
        Recoverability.RETRYABLE,
    )

    assert run.failure_code is FailureCode.EXECUTION_TIMEOUT
    assert run.recoverability is Recoverability.RETRYABLE
def test_v3_failure_does_not_mutate_status_or_integrity():
    run = TaskRun(
        TaskV3(
            schema_version=1,
            task_id="TASK-V3-RESULT-DIMENSIONS",
            description="V3 result dimensions contract test.",
            intent={},
            preconditions=[],
            expected=[],
            validation=[],
            execution_policy={},
        )
    )

    run.set_failure(
        FailureCode.EXECUTION_TIMEOUT,
        Recoverability.RETRYABLE,
    )

    assert run.task_status is TaskStatus.PENDING
    assert run.v3_phase is V3TaskPhase.PRECHECK
    assert run.v3_integrity is V3TaskIntegrity.UNKNOWN
def test_v3_integrity_is_independent_dimension():
    run = TaskRun(
        TaskV3(
            schema_version=1,
            task_id="TASK-V3-RESULT-DIMENSIONS",
            description="V3 result dimensions contract test.",
            intent={},
            preconditions=[],
            expected=[],
            validation=[],
            execution_policy={},
        )
    )

    run.set_v3_integrity(V3TaskIntegrity.DEGRADED)

    assert run.v3_integrity is V3TaskIntegrity.DEGRADED
    assert run.task_status is TaskStatus.PENDING
    assert run.failure_code is None
    assert run.recoverability is None
def test_execution_timeout_maps_to_timeout_failure_code():
    code = TaskRunExecutor._map_execution_failure_code(
        ExecutionStatus.CANCELLED,
        "Execution timeout reached.",
    )

    assert code is FailureCode.EXECUTION_TIMEOUT


def test_execution_cancellation_maps_to_cancelled_failure_code():
    code = TaskRunExecutor._map_execution_failure_code(
        ExecutionStatus.CANCELLED,
        "Execution cancellation requested.",
    )

    assert code is FailureCode.EXECUTION_CANCELLED
def test_execution_blocked_maps_to_precondition_failure_code():
    code = TaskRunExecutor._map_execution_failure_code(
        ExecutionStatus.BLOCKED,
        "Execution blocked by unsatisfied preconditions.",
    )

    assert code is FailureCode.PRECONDITION_FAILED