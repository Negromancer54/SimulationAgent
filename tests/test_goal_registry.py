from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import GoalKind
from registries.goal_registry import (
    GoalRegistrationError,
    GoalRegistry,
    GoalResolutionStatus,
    GoalSpec,
    GoalSpecStatus,
)


def make_registry() -> GoalRegistry:
    registry = GoalRegistry()

    registry.register(
        GoalSpec(
            identifier="component.add_generic_api",
            kind=GoalKind.OUTCOME,
            version=1,
            semantic_contract="Add the generic component API.",
            owner="PROJECT",
        )
    )

    return registry


def test_register_and_resolve() -> None:
    registry = make_registry()

    result = registry.resolve(
        "component.add_generic_api",
        1,
    )

    assert result.status is GoalResolutionStatus.FOUND
    assert result.spec is not None
    assert result.spec.identifier == "component.add_generic_api"
    assert result.spec.version == 1
    assert result.spec.kind is GoalKind.OUTCOME


def test_contains() -> None:
    registry = make_registry()

    assert registry.contains(
        "component.add_generic_api",
        1,
    )

    assert not registry.contains(
        "component.add_generic_api",
        2,
    )


def test_unknown_goal() -> None:
    registry = make_registry()

    result = registry.resolve(
        "unknown.goal",
        1,
    )

    assert result.status is GoalResolutionStatus.NOT_FOUND
    assert result.spec is None


def test_missing_version() -> None:
    registry = make_registry()

    result = registry.resolve(
        "component.add_generic_api",
        2,
    )

    assert result.status is GoalResolutionStatus.VERSION_UNAVAILABLE
    assert result.spec is None
    assert "version 2" in result.message
    assert "1" in result.message


def test_duplicate_registration_rejected() -> None:
    registry = make_registry()

    try:
        registry.register(
            GoalSpec(
                identifier="component.add_generic_api",
                kind=GoalKind.OUTCOME,
                version=1,
            )
        )
    except GoalRegistrationError:
        return

    raise AssertionError(
        "Duplicate GoalSpec registration was accepted."
    )


def test_multiple_versions() -> None:
    registry = make_registry()

    registry.register(
        GoalSpec(
            identifier="component.add_generic_api",
            kind=GoalKind.OUTCOME,
            version=2,
            semantic_contract="Version 2 of the generic component API.",
        )
    )

    assert registry.list_versions(
        "component.add_generic_api"
    ) == [1, 2]

    result_v1 = registry.resolve(
        "component.add_generic_api",
        1,
    )
    result_v2 = registry.resolve(
        "component.add_generic_api",
        2,
    )

    assert result_v1.status is GoalResolutionStatus.FOUND
    assert result_v2.status is GoalResolutionStatus.FOUND


def test_disabled_goal() -> None:
    registry = make_registry()

    registry.disable(
        "component.add_generic_api",
        1,
    )

    result = registry.resolve(
        "component.add_generic_api",
        1,
    )

    assert result.status is GoalResolutionStatus.DISABLED
    assert result.spec is not None
    assert result.spec.status is GoalSpecStatus.DISABLED


def test_deprecated_goal_still_resolves() -> None:
    registry = make_registry()

    registry.deprecate(
        "component.add_generic_api",
        1,
    )

    result = registry.resolve(
        "component.add_generic_api",
        1,
    )

    assert result.status is GoalResolutionStatus.FOUND
    assert result.spec is not None
    assert result.spec.status is GoalSpecStatus.DEPRECATED


def test_invalid_identifier_rejected() -> None:
    registry = GoalRegistry()

    try:
        registry.register(
            GoalSpec(
                identifier="",
                kind=GoalKind.OUTCOME,
                version=1,
            )
        )
    except GoalRegistrationError:
        return

    raise AssertionError(
        "Empty GoalSpec identifier was accepted."
    )


def test_invalid_version_rejected() -> None:
    registry = GoalRegistry()

    try:
        registry.register(
            GoalSpec(
                identifier="invalid.version",
                kind=GoalKind.OUTCOME,
                version=0,
            )
        )
    except GoalRegistrationError:
        return

    raise AssertionError(
        "Non-positive GoalSpec version was accepted."
    )


def main() -> int:
    tests = [
        test_register_and_resolve,
        test_contains,
        test_unknown_goal,
        test_missing_version,
        test_duplicate_registration_rejected,
        test_multiple_versions,
        test_disabled_goal,
        test_deprecated_goal_still_resolves,
        test_invalid_identifier_rejected,
        test_invalid_version_rejected,
    ]

    print("=" * 70)
    print("GOAL REGISTRY TESTS")
    print("=" * 70)

    passed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test.__name__}")
            print(f"       {type(exc).__name__}: {exc}")

    print()
    print(f"Tests: {passed}/{len(tests)}")

    if passed == len(tests):
        print("GOAL REGISTRY: PASS")
    else:
        print("GOAL REGISTRY: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())