from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import GoalKind, TaskGoal
from registries.goal_registry import (
    GoalRegistry,
    GoalSpec,
)
from registries.goal_resolver import (
    GoalResolver,
    GoalResolverStatus,
)


def make_registry() -> GoalRegistry:
    registry = GoalRegistry()

    registry.register(
        GoalSpec(
            identifier="component.add_generic_api",
            kind=GoalKind.OUTCOME,
            version=1,
            semantic_contract=(
                "Add the generic component API."
            ),
            owner="PROJECT",
        )
    )

    registry.register(
        GoalSpec(
            identifier="component.add_generic_api",
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
            identifier="component.verify_storage",
            kind=GoalKind.ASSERTION,
            version=1,
            semantic_contract=(
                "Verify component storage invariants."
            ),
            owner="CORE",
        )
    )

    return registry


def make_resolver() -> GoalResolver:
    return GoalResolver(make_registry())


def test_resolve_existing_goal() -> None:
    resolver = make_resolver()

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=1,
        parameters={},
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.RESOLVED
    assert result.resolved
    assert result.spec is not None
    assert result.spec.identifier == "component.add_generic_api"
    assert result.spec.version == 1


def test_exact_version_is_resolved() -> None:
    resolver = make_resolver()

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=2,
        parameters={},
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.RESOLVED
    assert result.spec is not None
    assert result.spec.version == 2


def test_unknown_goal() -> None:
    resolver = make_resolver()

    goal = TaskGoal(
        identifier="unknown.goal",
        kind=GoalKind.OUTCOME,
        version=1,
        parameters={},
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.NOT_FOUND
    assert not result.resolved
    assert result.spec is None
    assert "not registered" in result.message


def test_existing_goal_missing_version() -> None:
    resolver = make_resolver()

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=3,
        parameters={},
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.VERSION_UNAVAILABLE
    assert not result.resolved
    assert result.spec is None
    assert "version 3" in result.message


def test_disabled_goal() -> None:
    registry = make_registry()

    registry.disable(
        "component.add_generic_api",
        1,
    )

    resolver = GoalResolver(registry)

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=1,
        parameters={},
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.DISABLED
    assert not result.resolved
    assert result.spec is not None


def test_invalid_goal_type() -> None:
    resolver = make_resolver()

    result = resolver.resolve(object())

    assert result.status == GoalResolverStatus.INVALID
    assert not result.resolved
    assert result.spec is None


def test_empty_identifier() -> None:
    resolver = make_resolver()

    goal = TaskGoal(
        identifier="",
        kind=GoalKind.OUTCOME,
        version=1,
        parameters={},
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.INVALID
    assert not result.resolved
    assert "identifier" in result.message


def test_invalid_version() -> None:
    resolver = make_resolver()

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=0,
        parameters={},
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.INVALID
    assert not result.resolved
    assert "version" in result.message


def test_goal_parameters_are_preserved() -> None:
    resolver = make_resolver()

    parameters = {
        "component": "DebugComponent",
        "replace_existing": False,
    }

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=1,
        parameters=parameters,
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.RESOLVED
    assert result.goal.parameters == parameters


def test_goal_kind_does_not_replace_registry_identity() -> None:
    resolver = make_resolver()

    goal = TaskGoal(
        identifier="component.add_generic_api",
        kind=GoalKind.STATE,
        version=1,
        parameters={},
    )

    result = resolver.resolve(goal)

    assert result.status == GoalResolverStatus.RESOLVED
    assert result.spec is not None
    assert result.spec.kind is GoalKind.OUTCOME


def main() -> int:
    tests = [
        test_resolve_existing_goal,
        test_exact_version_is_resolved,
        test_unknown_goal,
        test_existing_goal_missing_version,
        test_disabled_goal,
        test_invalid_goal_type,
        test_empty_identifier,
        test_invalid_version,
        test_goal_parameters_are_preserved,
        test_goal_kind_does_not_replace_registry_identity,
    ]

    print("=" * 70)
    print("GOAL RESOLVER TESTS")
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
        print("GOAL RESOLVER: PASS")
    else:
        print("GOAL RESOLVER: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())