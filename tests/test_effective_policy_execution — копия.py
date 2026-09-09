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
    ResourcePolicy,
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
        task_id="effective-policy-execution-test",
        description="Verify effective policy execution.",
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
    handler_policy: HandlerExecutionPolicy | None = None,
    runtime_limits: RuntimeExecutionLimits | None = None,
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
        runtime_execution_limits=(
            runtime_limits
            if runtime_limits is not None
            else RuntimeExecutionLimits()
        ),
    )


def test_task_run_and_execution_share_effective_policy() -> None:
    handler_policy = HandlerExecutionPolicy(
        timeout_seconds=60,
        max_attempts=4,
        max_workers=3,
    )

    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=120,
        max_attempts=8,
        max_workers=6,
    )

    executor = make_executor(
        handler_policy=handler_policy,
        runtime_limits=runtime_limits,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED
    assert result.run.effective_execution_policy is not None
    assert result.run.execution is not None
    assert result.run.execution.policy is not None

    assert (
        result.run.effective_execution_policy
        is result.run.execution.policy
    )


def test_execution_result_preserves_policy_on_success() -> None:
    handler_policy = HandlerExecutionPolicy(
        timeout_seconds=45,
        max_attempts=5,
        max_workers=2,
    )

    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=120,
        max_attempts=10,
        max_workers=10,
    )

    executor = make_executor(
        handler_policy=handler_policy,
        runtime_limits=runtime_limits,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.completed
    assert result.run.execution is not None
    assert result.run.execution.policy is not None

    assert result.run.execution.policy.timeout_seconds == 45
    assert result.run.execution.policy.max_attempts == 5
    assert result.run.execution.policy.max_workers == 2


def test_execution_result_preserves_policy_on_failure() -> None:
    handler_policy = HandlerExecutionPolicy(
        timeout_seconds=45,
        max_attempts=5,
        max_workers=2,
    )

    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=120,
        max_attempts=10,
        max_workers=10,
    )

    executor = make_executor(
        handler_policy=handler_policy,
        runtime_limits=runtime_limits,
    )

    def failing_handler(step):
        raise RuntimeError("execution failed")

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: failing_handler,
        },
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.execution is not None
    assert result.run.execution.policy is not None

    assert result.run.execution.policy.timeout_seconds == 45
    assert result.run.execution.policy.max_attempts == 5
    assert result.run.execution.policy.max_workers == 2



def test_effective_max_attempts_controls_retry_limit() -> None:
    handler_policy = HandlerExecutionPolicy(
        max_attempts=3,
    )

    runtime_limits = RuntimeExecutionLimits(
        max_attempts=10,
        max_workers=4,
    )

    executor = make_executor(
        handler_policy=handler_policy,
        runtime_limits=runtime_limits,
    )

    attempts = 0

    def failing_handler(step):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("retry failure")

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: failing_handler,
        },
    )

    assert not result.completed
    assert result.run.execution is not None
    assert result.run.execution.status.name == "FAILED"

    step_result = result.run.execution.step_results[0]

    assert step_result.attempts == 3
    assert attempts == 3

