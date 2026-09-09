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
from registries.handler_registry import (
    HandlerApplicability,
    HandlerRegistry,
    HandlerSpec,
    HandlerSpecStatus,
)
from registries.handler_resolver import (
    HandlerResolution,
    HandlerResolver,
    HandlerResolverStatus,
    HandlerRuntimeContext,
    SpecificityRelation,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1


def make_task(
    operation: TaskOperation = TaskOperation.CHANGE,
    target_kind: TargetKind = TargetKind.PROJECT,
    project: str = "SimulationZero-Cpp",
) -> TaskV3:
    target = TaskTarget(
        kind=target_kind,
        identifier="simulation_zero",
        scope=TaskScope(
            project=project,
            path=None,
            namespace=None,
        ),
    )

    goal = TaskGoal(
        identifier=GOAL_ID,
        kind=GoalKind.OUTCOME,
        version=GOAL_VERSION,
        parameters={},
    )

    intent = TaskIntent(
        operation=operation,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id="handler-resolution-test",
        description="Resolve a TaskV3 handler.",
        intent=intent,
    )


def make_registry() -> HandlerRegistry:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="generic.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
        )
    )

    return registry


def make_resolver(
    registry: HandlerRegistry | None = None,
) -> HandlerResolver:
    return HandlerResolver(
        registry or make_registry()
    )


def test_basic_handler_resolution() -> None:
    resolver = make_resolver()

    result = resolver.resolve(make_task())

    assert result.status is HandlerResolverStatus.FOUND
    assert result.resolved
    assert result.handler is not None
    assert result.handler.handler_id == "generic.handler"


def test_unknown_goal_has_no_handler() -> None:
    resolver = make_resolver()

    task = make_task()
    task = TaskV3(
        schema_version=3,
        task_id=task.task_id,
        description=task.description,
        intent=TaskIntent(
            operation=task.intent.operation,
            target=task.intent.target,
            goal=TaskGoal(
                identifier="unknown.goal",
                kind=GoalKind.OUTCOME,
                version=1,
                parameters={},
            ),
        ),
    )

    result = resolver.resolve(task)

    assert result.status is HandlerResolverStatus.NOT_FOUND
    assert not result.resolved
    assert result.handler is None


def test_operation_applicability() -> None:
    registry = HandlerRegistry()

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

    resolver = make_resolver(registry)

    change_result = resolver.resolve(
        make_task(TaskOperation.CHANGE)
    )

    verify_result = resolver.resolve(
        make_task(TaskOperation.VERIFY)
    )

    assert change_result.status is HandlerResolverStatus.FOUND
    assert verify_result.status is HandlerResolverStatus.UNAVAILABLE


def test_target_kind_applicability() -> None:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="project.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                target_kinds=(TargetKind.PROJECT,)
            ),
        )
    )

    resolver = make_resolver(registry)

    project_result = resolver.resolve(
        make_task(target_kind=TargetKind.PROJECT)
    )

    file_result = resolver.resolve(
        make_task(target_kind=TargetKind.FILE)
    )

    assert project_result.status is HandlerResolverStatus.FOUND
    assert file_result.status is HandlerResolverStatus.UNAVAILABLE


def test_capability_filter() -> None:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="secure.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            required_capabilities=(
                "filesystem.write",
            ),
        )
    )

    resolver = make_resolver(registry)

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
        is HandlerResolverStatus.UNAVAILABLE
    )
    assert with_capability.status is HandlerResolverStatus.FOUND
    assert with_capability.handler is not None


def test_more_specific_handler_wins() -> None:
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

    resolver = make_resolver(registry)

    result = resolver.resolve(
        make_task(TaskOperation.CHANGE)
    )

    assert result.status is HandlerResolverStatus.FOUND
    assert result.handler is not None
    assert result.handler.handler_id == "change.handler"


def test_project_specific_handler_beats_operation_only_handler() -> None:
    registry = HandlerRegistry()

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

    resolver = make_resolver(registry)

    result = resolver.resolve(
        make_task(TaskOperation.CHANGE)
    )

    assert result.status is HandlerResolverStatus.AMBIGUOUS


def test_equivalent_profiles_use_stable_handler_id() -> None:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="handler.b",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    registry.register(
        HandlerSpec(
            handler_id="handler.a",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    resolver = make_resolver(registry)

    result = resolver.resolve(
        make_task(TaskOperation.CHANGE)
    )

    assert result.status is HandlerResolverStatus.FOUND
    assert result.handler is not None
    assert result.handler.handler_id == "handler.a"


def test_incomparable_profiles_are_ambiguous() -> None:
    registry = HandlerRegistry()

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

    resolver = make_resolver(registry)

    result = resolver.resolve(
        make_task(TaskOperation.CHANGE)
    )

    assert result.status is HandlerResolverStatus.AMBIGUOUS
    assert len(result.candidates) == 2


def test_specificity_relations() -> None:
    generic = HandlerSpec(
        handler_id="generic",
        goal_identifier=GOAL_ID,
        goal_version=GOAL_VERSION,
    )

    change = HandlerSpec(
        handler_id="change",
        goal_identifier=GOAL_ID,
        goal_version=GOAL_VERSION,
        applicability=HandlerApplicability(
            operations=(TaskOperation.CHANGE,)
        ),
    )

    verify = HandlerSpec(
        handler_id="verify",
        goal_identifier=GOAL_ID,
        goal_version=GOAL_VERSION,
        applicability=HandlerApplicability(
            operations=(TaskOperation.VERIFY,)
        ),
    )

    same_change = HandlerSpec(
        handler_id="same-change",
        goal_identifier=GOAL_ID,
        goal_version=GOAL_VERSION,
        applicability=HandlerApplicability(
            operations=(TaskOperation.CHANGE,)
        ),
    )

    resolver = make_resolver()

    assert (
        resolver.compare_specificity(
            change,
            generic,
        )
        is SpecificityRelation.MORE_SPECIFIC
    )

    assert (
        resolver.compare_specificity(
            generic,
            change,
        )
        is SpecificityRelation.LESS_SPECIFIC
    )

    assert (
        resolver.compare_specificity(
            change,
            same_change,
        )
        is SpecificityRelation.EQUIVALENT
    )

    assert (
        resolver.compare_specificity(
            change,
            verify,
        )
        is SpecificityRelation.INCOMPARABLE
    )


def test_disabled_handlers_do_not_resolve() -> None:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="disabled.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            status=HandlerSpecStatus.DISABLED,
        )
    )

    resolver = make_resolver(registry)

    result = resolver.resolve(make_task())

    assert result.status is HandlerResolverStatus.UNAVAILABLE
    assert result.handler is None


def test_deprecated_handler_remains_usable() -> None:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id="deprecated.handler",
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            status=HandlerSpecStatus.DEPRECATED,
        )
    )

    resolver = make_resolver(registry)

    result = resolver.resolve(make_task())

    assert result.status is HandlerResolverStatus.FOUND
    assert result.handler is not None
    assert (
        result.handler.status
        is HandlerSpecStatus.DEPRECATED
    )


def test_task_is_not_mutated() -> None:
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


def main() -> int:
    tests = [
        test_basic_handler_resolution,
        test_unknown_goal_has_no_handler,
        test_operation_applicability,
        test_target_kind_applicability,
        test_capability_filter,
        test_more_specific_handler_wins,
        test_project_specific_handler_beats_operation_only_handler,
        test_equivalent_profiles_use_stable_handler_id,
        test_incomparable_profiles_are_ambiguous,
        test_specificity_relations,
        test_disabled_handlers_do_not_resolve,
        test_deprecated_handler_remains_usable,
        test_task_is_not_mutated,
    ]

    print("=" * 70)
    print("HANDLER RESOLVER TESTS")
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
        print("HANDLER RESOLVER: PASS")
    else:
        print("HANDLER RESOLVER: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())