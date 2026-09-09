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
    GoalSpecStatus,
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
from runtime.task_resolution import (
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

    registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=2,
            semantic_contract=(
                "Version 2 of the generic component API."
            ),
            owner="PROJECT",
        )
    )

    registry.register(
        GoalSpec(
            identifier="component.disabled",
            kind=GoalKind.OUTCOME,
            version=1,
            status=GoalSpecStatus.DISABLED,
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
            handler_id="generic.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
        )
    )

    registry.register(
        HandlerSpec(
            handler_id="change.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    return registry


def make_task(
    goal_identifier: str = GOAL_ID,
    goal_version: int = GOAL_VERSION,
    target_identifier: str = "simulation_zero",
    target_scope: str = "SimulationZero-Cpp",
) -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier=target_identifier,
        scope=TaskScope(
            project=target_scope
        ),
    )

    goal = TaskGoal(
        identifier=goal_identifier,
        kind=GoalKind.OUTCOME,
        version=goal_version,
        parameters={},
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id="task-resolution-test",
        description="Resolve a TaskV3 target, goal and handler.",
        intent=intent,
    )


def make_resolver(
    goal_registry: GoalRegistry | None = None,
    target_directory: TargetDirectory | None = None,
    handler_registry: HandlerRegistry | None = None,
) -> TaskResolver:
    return TaskResolver(
        goal_registry or make_goal_registry(),
        target_directory or make_target_directory(),
        handler_registry or make_handler_registry(),
    )


def test_full_resolution_succeeds() -> None:
    resolver = make_resolver()

    result = resolver.resolve(make_task())

    assert result.status is TaskResolutionStatus.RESOLVED
    assert result.resolved

    assert result.target_resolution is not None
    assert result.target_resolution.resolved

    assert result.goal_resolution is not None
    assert result.goal_resolution.resolved

    assert result.handler_resolution is not None
    assert result.handler_resolution.resolved

    assert result.target_record is not None
    assert result.goal_spec is not None
    assert result.handler_spec is not None


def test_more_specific_handler_is_selected() -> None:
    resolver = make_resolver()

    result = resolver.resolve(make_task())

    assert result.status is TaskResolutionStatus.RESOLVED
    assert result.handler_spec is not None
    assert result.handler_spec.handler_id == "change.handler"


def test_handler_context_is_forwarded() -> None:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="secure.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            required_capabilities=("filesystem.write",),
        )
    )

    resolver = make_resolver(
        handler_registry=registry
    )

    without_capability = resolver.resolve(
        make_task(),
        HandlerRuntimeContext(),
    )

    with_capability = resolver.resolve(
        make_task(),
        HandlerRuntimeContext(
            capabilities=frozenset(
                {"filesystem.write"}
            )
        ),
    )

    assert (
        without_capability.status
        is TaskResolutionStatus.HANDLER_UNAVAILABLE
    )

    assert (
        with_capability.status
        is TaskResolutionStatus.RESOLVED
    )

    assert with_capability.handler_spec is not None
    assert (
        with_capability.handler_spec.handler_id
        == "secure.handler"
    )


def test_target_not_found_is_preserved() -> None:
    resolver = make_resolver()

    result = resolver.resolve(
        make_task(
            target_identifier="missing_project"
        )
    )

    assert result.status is TaskResolutionStatus.TARGET_NOT_FOUND
    assert not result.resolved

    assert result.target_resolution is not None
    assert not result.target_resolution.resolved

    assert result.goal_resolution is not None
    assert result.goal_resolution.resolved

    assert result.handler_resolution is not None
    assert result.handler_resolution.resolved

    assert result.target_record is None
    assert result.goal_spec is not None
    assert result.handler_spec is not None


def test_goal_not_found_is_preserved() -> None:
    resolver = make_resolver()

    result = resolver.resolve(
        make_task(
            goal_identifier="unknown.goal"
        )
    )

    assert result.status is TaskResolutionStatus.GOAL_NOT_FOUND
    assert not result.resolved

    assert result.target_resolution is not None
    assert result.target_resolution.resolved

    assert result.goal_resolution is not None
    assert not result.goal_resolution.resolved

    assert result.handler_resolution is not None
    assert not result.handler_resolution.resolved

    assert result.goal_spec is None


def test_handler_not_found_is_reported() -> None:
    empty_handler_registry = HandlerRegistry()

    resolver = make_resolver(
        handler_registry=empty_handler_registry
    )

    result = resolver.resolve(make_task())

    assert result.status is TaskResolutionStatus.HANDLER_NOT_FOUND
    assert not result.resolved

    assert result.target_resolution is not None
    assert result.target_resolution.resolved

    assert result.goal_resolution is not None
    assert result.goal_resolution.resolved

    assert result.handler_resolution is not None
    assert (
        not result.handler_resolution.resolved
    )

    assert result.target_record is not None
    assert result.goal_spec is not None
    assert result.handler_spec is None


def test_handler_ambiguity_is_reported() -> None:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="operation.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    registry.register(
        HandlerSpec(
            handler_id="project.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                projects=("SimulationZero-Cpp",)
            ),
        )
    )

    resolver = make_resolver(
        handler_registry=registry
    )

    result = resolver.resolve(make_task())

    assert result.status is TaskResolutionStatus.HANDLER_AMBIGUOUS
    assert not result.resolved

    assert result.target_resolution is not None
    assert result.target_resolution.resolved

    assert result.goal_resolution is not None
    assert result.goal_resolution.resolved

    assert result.handler_resolution is not None
    assert not result.handler_resolution.resolved

    assert len(result.handler_resolution.candidates) == 2


def test_disabled_goal_is_reported() -> None:
    resolver = make_resolver()

    result = resolver.resolve(
        make_task(
            goal_identifier="component.disabled",
            goal_version=1,
        )
    )

    assert result.status is TaskResolutionStatus.GOAL_DISABLED
    assert not result.resolved

    assert result.target_resolution is not None
    assert result.target_resolution.resolved

    assert result.goal_resolution is not None
    assert not result.goal_resolution.resolved


def test_invalid_task_stops_before_resolution() -> None:
    resolver = make_resolver()

    valid_task = make_task()

    invalid_task = TaskV3(
        schema_version=2,
        task_id=valid_task.task_id,
        description=valid_task.description,
        intent=valid_task.intent,
    )

    result = resolver.resolve(invalid_task)

    assert result.status is TaskResolutionStatus.INVALID_TASK
    assert not result.resolved
    assert result.target_resolution is None
    assert result.goal_resolution is None
    assert result.handler_resolution is None


def test_both_resolver_results_are_preserved_on_target_failure() -> None:
    resolver = make_resolver()

    result = resolver.resolve(
        make_task(
            target_identifier="missing_project",
            goal_identifier="unknown.goal",
        )
    )

    assert result.status is TaskResolutionStatus.TARGET_NOT_FOUND

    assert result.target_resolution is not None
    assert result.goal_resolution is not None
    assert result.handler_resolution is not None

    assert not result.target_resolution.resolved
    assert not result.goal_resolution.resolved
    assert not result.handler_resolution.resolved


def test_original_task_is_preserved() -> None:
    resolver = make_resolver()

    task = make_task()
    result = resolver.resolve(task)

    assert result.task is task


def test_resolution_does_not_mutate_task() -> None:
    resolver = make_resolver()

    task = make_task()

    before = (
        task.schema_version,
        task.task_id,
        task.description,
        task.intent,
    )

    resolver.resolve(task)

    after = (
        task.schema_version,
        task.task_id,
        task.description,
        task.intent,
    )

    assert before == after


def test_resolved_objects_match_nested_results() -> None:
    resolver = make_resolver()

    result = resolver.resolve(make_task())

    assert result.target_resolution is not None
    assert result.target_record is result.target_resolution.record

    assert result.goal_resolution is not None
    assert result.goal_spec is result.goal_resolution.spec

    assert result.handler_resolution is not None
    assert result.handler_spec is result.handler_resolution.handler


def test_handler_failure_does_not_erase_target_or_goal() -> None:
    resolver = make_resolver(
        handler_registry=HandlerRegistry()
    )

    result = resolver.resolve(make_task())

    assert result.status is TaskResolutionStatus.HANDLER_NOT_FOUND
    assert result.target_record is not None
    assert result.goal_spec is not None
    assert result.handler_spec is None


def main() -> int:
    tests = [
        test_full_resolution_succeeds,
        test_more_specific_handler_is_selected,
        test_handler_context_is_forwarded,
        test_target_not_found_is_preserved,
        test_goal_not_found_is_preserved,
        test_handler_not_found_is_reported,
        test_handler_ambiguity_is_reported,
        test_disabled_goal_is_reported,
        test_invalid_task_stops_before_resolution,
        test_both_resolver_results_are_preserved_on_target_failure,
        test_original_task_is_preserved,
        test_resolution_does_not_mutate_task,
        test_resolved_objects_match_nested_results,
        test_handler_failure_does_not_erase_target_or_goal,
    ]

    print("=" * 70)
    print("TASK RESOLUTION TESTS")
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
        print("TASK RESOLUTION: PASS")
    else:
        print("TASK RESOLUTION: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())