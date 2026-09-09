from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    GoalKind,
    Precondition,
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
from registries.handler_resolver import (
    HandlerRuntimeContext,
)
from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)
from runtime.execution import (
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    ExecutionPlanner,
    PlanStatus,
)
from runtime.preconditions import (
    PreconditionEvaluation,
    PreconditionEvaluator,
    PreconditionRegistry,
    PreconditionScope,
    PreconditionStatus,
    PreconditionsResult,
)
from runtime.task_resolution import (
    TaskResolutionStatus,
    TaskResolver,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


def make_task(
    preconditions: tuple[Precondition, ...] = (),
) -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp"
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
        task_id="task-pipeline-test",
        description="Run the complete Task V3 pipeline.",
        intent=intent,
        preconditions=preconditions,
    )


def make_goal_registry() -> GoalRegistry:
    registry = GoalRegistry()

    registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract=(
                "Add the generic component API."
            ),
            owner="PROJECT",
        )
    )

    return registry


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


def make_handler_registry() -> HandlerRegistry:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    return registry


def make_resolver() -> TaskResolver:
    return TaskResolver(
        make_goal_registry(),
        make_target_directory(),
        make_handler_registry(),
    )


def resolve_and_plan(
    task: TaskV3,
):
    resolution = make_resolver().resolve(
        task,
        HandlerRuntimeContext(),
    )

    assert resolution.status is TaskResolutionStatus.RESOLVED

    plan = ExecutionPlanner().build(
        resolution
    )

    assert plan.status is PlanStatus.READY

    return resolution, plan


def make_satisfied_preconditions(
    task: TaskV3,
) -> PreconditionsResult:
    registry = PreconditionRegistry()

    registry.register(
        "runtime.ready",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    precondition = Precondition(
        id="pc.runtime.ready",
        kind="STATE",
        identifier="runtime.ready",
        version=1,
        parameters={},
    )

    task_with_precondition = TaskV3(
        schema_version=task.schema_version,
        task_id=task.task_id,
        description=task.description,
        intent=task.intent,
        preconditions=(precondition,),
    )

    return PreconditionEvaluator(registry).evaluate(
        task_with_precondition
    )


def test_complete_pipeline_succeeds() -> None:
    task = make_task()

    resolution, plan = resolve_and_plan(task)

    preconditions = make_satisfied_preconditions(task)

    assert resolution.resolved
    assert plan.ready
    assert preconditions.satisfied

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    execution = ExecutionRuntime().execute(
        plan,
        preconditions,
        {HANDLER_ID: handler},
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.succeeded
    assert execution.completed_steps == ("step.1",)
    assert execution.failed_step is None
    assert calls == ["step.1"]


def test_pipeline_stops_at_preconditions() -> None:
    task = make_task()

    _, plan = resolve_and_plan(task)

    failed_preconditions = PreconditionsResult(
        evaluations=(
            PreconditionEvaluation(
                precondition_id="pc.runtime.ready",
                scope=PreconditionScope.RUNTIME_SAFETY,
                status=PreconditionStatus.FAILED,
                message="Runtime is not ready.",
            ),
        ),
    )

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    execution = ExecutionRuntime().execute(
        plan,
        failed_preconditions,
        {HANDLER_ID: handler},
    )

    assert execution.status is ExecutionStatus.BLOCKED
    assert execution.completed_steps == ()
    assert execution.failed_step is None
    assert calls == []


def test_pipeline_preserves_layer_boundaries() -> None:
    task = make_task()

    resolution, plan = resolve_and_plan(task)

    assert resolution.task is task
    assert plan.task is task

    assert resolution.target_record is not None
    assert resolution.goal_spec is not None
    assert resolution.handler_spec is not None

    assert plan.steps[0].target_identifier == (
        resolution.target_record.identifier
    )
    assert plan.steps[0].goal_identifier == (
        resolution.goal_spec.identifier
    )
    assert plan.steps[0].handler_id == (
        resolution.handler_spec.handler_id
    )


def test_resolution_failure_prevents_planning_execution() -> None:
    task = make_task()

    resolver = TaskResolver(
        make_goal_registry(),
        TargetDirectory(),
        make_handler_registry(),
    )

    resolution = resolver.resolve(
        task,
        HandlerRuntimeContext(),
    )

    assert (
        resolution.status
        is TaskResolutionStatus.TARGET_NOT_FOUND
    )

    plan = ExecutionPlanner().build(
        resolution
    )

    assert (
        plan.status
        is PlanStatus.INVALID_RESOLUTION
    )

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    execution = ExecutionRuntime().execute(
        plan,
        PreconditionsResult(
            evaluations=(),
        ),
        {HANDLER_ID: handler},
    )

    assert (
        execution.status
        is ExecutionStatus.INFRASTRUCTURE_ERROR
    )
    assert calls == []


def test_handler_failure_does_not_become_resolution_failure() -> None:
    task = make_task()

    resolution, plan = resolve_and_plan(task)

    assert resolution.status is TaskResolutionStatus.RESOLVED
    assert plan.status is PlanStatus.READY

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)
        raise RuntimeError("execution failure")

    execution = ExecutionRuntime().execute(
        plan,
        PreconditionsResult(
            evaluations=(),
        ),
        {HANDLER_ID: handler},
    )

    assert execution.status is ExecutionStatus.FAILED
    assert calls == ["step.1"]


def test_full_pipeline_is_repeatable() -> None:
    task = make_task()

    resolution_a, plan_a = resolve_and_plan(task)
    resolution_b, plan_b = resolve_and_plan(task)

    preconditions = PreconditionsResult(
        evaluations=(),
    )

    runtime = ExecutionRuntime()

    result_a = runtime.execute(
        plan_a,
        preconditions,
        {HANDLER_ID: lambda step: None},
    )

    result_b = runtime.execute(
        plan_b,
        preconditions,
        {HANDLER_ID: lambda step: None},
    )

    assert resolution_a == resolution_b
    assert plan_a == plan_b
    assert result_a.status is ExecutionStatus.SUCCEEDED
    assert result_b.status is ExecutionStatus.SUCCEEDED
    assert (
        result_a.completed_steps
        == result_b.completed_steps
    )


def main() -> int:
    tests = [
        test_complete_pipeline_succeeds,
        test_pipeline_stops_at_preconditions,
        test_pipeline_preserves_layer_boundaries,
        test_resolution_failure_prevents_planning_execution,
        test_handler_failure_does_not_become_resolution_failure,
        test_full_pipeline_is_repeatable,
    ]

    print("=" * 70)
    print("TASK PIPELINE TESTS")
    print("=" * 70)

    passed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test.__name__}")
            print(
                f"       {type(exc).__name__}: {exc}"
            )

    print()
    print(f"Tests: {passed}/{len(tests)}")

    if passed == len(tests):
        print("TASK PIPELINE: PASS")
    else:
        print("TASK PIPELINE: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())