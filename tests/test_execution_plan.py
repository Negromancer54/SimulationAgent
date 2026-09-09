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
from runtime.execution_plan import (
    ExecutionPlan,
    ExecutionPlanner,
    PlanStatus,
)
from runtime.task_resolution import (
    TaskResolutionResult,
    TaskResolutionStatus,
    TaskResolver,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1


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
            handler_id="change.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
            required_capabilities=(
                "filesystem.write",
            ),
        )
    )

    return registry


def make_task() -> TaskV3:
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
        task_id="execution-plan-test",
        description="Build an execution plan.",
        intent=intent,
    )


def make_resolution() -> TaskResolutionResult:
    resolver = TaskResolver(
        make_goal_registry(),
        make_target_directory(),
        make_handler_registry(),
    )

    return resolver.resolve(
        make_task(),
        HandlerRuntimeContext(
            capabilities=frozenset(
                {"filesystem.write"}
            )
        ),
    )

def test_plan_carries_goal_parameters() -> None:
    resolver = TaskResolver(
        make_goal_registry(),
        make_target_directory(),
        make_handler_registry(),
    )

    resolution = resolver.resolve(
        make_parameterized_task(),
        HandlerRuntimeContext(
            capabilities=frozenset(
                {"filesystem.write"}
            )
        ),
    )

    assert resolution.status is TaskResolutionStatus.RESOLVED

    plan = ExecutionPlanner().build(resolution)

    assert plan.status is PlanStatus.READY
    assert len(plan.steps) == 1

    assert plan.steps[0].parameters == {
        "path": "src/test_file.cpp",
        "content": "hello",
    }

    assert resolution.task.intent.goal.parameters == {
        "path": "src/test_file.cpp",
        "content": "hello",
    }
def test_successful_resolution_produces_ready_plan() -> None:
    resolution = make_resolution()

    assert resolution.status is TaskResolutionStatus.RESOLVED

    planner = ExecutionPlanner()
    plan = planner.build(resolution)

    assert plan.status is PlanStatus.READY
    assert plan.ready
    assert len(plan.steps) == 1


def test_plan_contains_resolved_target() -> None:
    plan = ExecutionPlanner().build(
        make_resolution()
    )

    step = plan.steps[0]

    assert step.target_kind == "PROJECT"
    assert step.target_identifier == "simulation_zero"


def test_plan_contains_resolved_goal() -> None:
    plan = ExecutionPlanner().build(
        make_resolution()
    )

    step = plan.steps[0]

    assert step.goal_identifier == GOAL_ID
    assert step.goal_version == GOAL_VERSION


def test_plan_contains_selected_handler() -> None:
    plan = ExecutionPlanner().build(
        make_resolution()
    )

    step = plan.steps[0]

    assert step.handler_id == "change.handler"


def test_handler_capabilities_are_carried_into_plan() -> None:
    plan = ExecutionPlanner().build(
        make_resolution()
    )

    step = plan.steps[0]

    assert (
        step.resources.capabilities
        == ("filesystem.write",)
    )


def test_plan_step_is_deterministic() -> None:
    resolution = make_resolution()
    planner = ExecutionPlanner()

    plan_a = planner.build(resolution)
    plan_b = planner.build(resolution)

    assert plan_a == plan_b
    assert plan_a.steps[0].step_id == "step.1"
    assert plan_a.steps[0].depends_on == ()


def test_unresolved_task_cannot_produce_ready_plan() -> None:
    resolution = make_resolution()

    unresolved = TaskResolutionResult(
        status=TaskResolutionStatus.HANDLER_NOT_FOUND,
        task=resolution.task,
        validation=resolution.validation,
    )

    plan = ExecutionPlanner().build(unresolved)

    assert (
        plan.status
        is PlanStatus.INVALID_RESOLUTION
    )
    assert not plan.ready
    assert plan.steps == ()


def test_missing_target_record_is_rejected() -> None:
    resolution = make_resolution()

    invalid_resolution = TaskResolutionResult(
        status=TaskResolutionStatus.RESOLVED,
        task=resolution.task,
        validation=resolution.validation,
        target_resolution=resolution.target_resolution,
        goal_resolution=resolution.goal_resolution,
        handler_resolution=resolution.handler_resolution,
        target_record=None,
        goal_spec=resolution.goal_spec,
        handler_spec=resolution.handler_spec,
    )

    plan = ExecutionPlanner().build(
        invalid_resolution
    )

    assert (
        plan.status
        is PlanStatus.INVALID_RESOLUTION
    )
    assert plan.steps == ()


def test_missing_goal_spec_is_rejected() -> None:
    resolution = make_resolution()

    invalid_resolution = TaskResolutionResult(
        status=TaskResolutionStatus.RESOLVED,
        task=resolution.task,
        validation=resolution.validation,
        target_resolution=resolution.target_resolution,
        goal_resolution=resolution.goal_resolution,
        handler_resolution=resolution.handler_resolution,
        target_record=resolution.target_record,
        goal_spec=None,
        handler_spec=resolution.handler_spec,
    )

    plan = ExecutionPlanner().build(
        invalid_resolution
    )

    assert (
        plan.status
        is PlanStatus.INVALID_RESOLUTION
    )
    assert plan.steps == ()


def test_missing_handler_spec_is_rejected() -> None:
    resolution = make_resolution()

    invalid_resolution = TaskResolutionResult(
        status=TaskResolutionStatus.RESOLVED,
        task=resolution.task,
        validation=resolution.validation,
        target_resolution=resolution.target_resolution,
        goal_resolution=resolution.goal_resolution,
        handler_resolution=resolution.handler_resolution,
        target_record=resolution.target_record,
        goal_spec=resolution.goal_spec,
        handler_spec=None,
    )

    plan = ExecutionPlanner().build(
        invalid_resolution
    )

    assert (
        plan.status
        is PlanStatus.INVALID_RESOLUTION
    )
    assert plan.steps == ()


def test_planning_does_not_mutate_task() -> None:
    task = make_task()
    resolution = make_resolution()

    before = (
        task.schema_version,
        task.task_id,
        task.description,
        task.intent,
    )

    ExecutionPlanner().build(resolution)

    after = (
        task.schema_version,
        task.task_id,
        task.description,
        task.intent,
    )

    assert before == after
def make_parameterized_task() -> TaskV3:
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
        parameters={
            "path": "src/test_file.cpp",
            "content": "hello",
        },
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id="execution-plan-parameter-test",
        description="Build an execution plan with goal parameters.",
        intent=intent,
    )

def test_plan_keeps_original_task_identity() -> None:
    resolution = make_resolution()

    plan = ExecutionPlanner().build(resolution)

    assert plan.task is resolution.task


def main() -> int:
    tests = [
        test_successful_resolution_produces_ready_plan,
        test_plan_contains_resolved_target,
        test_plan_contains_resolved_goal,
        test_plan_contains_selected_handler,
        test_handler_capabilities_are_carried_into_plan,
        test_plan_step_is_deterministic,
        test_unresolved_task_cannot_produce_ready_plan,
        test_missing_target_record_is_rejected,
        test_missing_goal_spec_is_rejected,
        test_missing_handler_spec_is_rejected,
        test_planning_does_not_mutate_task,
        test_plan_keeps_original_task_identity,
    ]

    print("=" * 70)
    print("EXECUTION PLAN TESTS")
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
        print("EXECUTION PLAN: PASS")
    else:
        print("EXECUTION PLAN: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())