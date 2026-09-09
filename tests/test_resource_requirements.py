from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from runtime.execution_plan import (
    ResourceRequirements,
)


def test_empty_requirements():
    requirements = ResourceRequirements()

    assert requirements.capabilities == ()
    assert requirements.resources == {}


def test_capabilities_are_preserved():
    requirements = ResourceRequirements(
        capabilities=(
            "filesystem.write",
            "network.connect",
        ),
    )

    assert requirements.capabilities == (
        "filesystem.write",
        "network.connect",
    )
    assert requirements.resources == {}


def test_single_resource_requirement():
    requirements = ResourceRequirements(
        resources={
            "memory_mb": 512,
        },
    )

    assert requirements.resources == {
        "memory_mb": 512,
    }


def test_multiple_resource_requirements():
    requirements = ResourceRequirements(
        resources={
            "memory_mb": 512,
            "cpu_threads": 2,
            "disk_mb": 4096,
        },
    )

    assert requirements.resources == {
        "memory_mb": 512,
        "cpu_threads": 2,
        "disk_mb": 4096,
    }


def test_capabilities_and_resources_are_independent():
    requirements = ResourceRequirements(
        capabilities=(
            "filesystem.write",
        ),
        resources={
            "memory_mb": 512,
        },
    )

    assert requirements.capabilities == (
        "filesystem.write",
    )

    assert requirements.resources == {
        "memory_mb": 512,
    }


def test_resource_dictionary_is_copied():
    values = {
        "memory_mb": 512,
    }

    requirements = ResourceRequirements(
        resources=values,
    )

    values["memory_mb"] = 4096

    assert requirements.resources == {
        "memory_mb": 512,
    }


def test_invalid_resource_identifier_is_rejected():
    try:
        ResourceRequirements(
            resources={
                "": 512,
            },
        )
    except ValueError:
        return

    raise AssertionError(
        "Empty resource identifier must be rejected."
    )


def test_invalid_resource_value_is_rejected():
    try:
        ResourceRequirements(
            resources={
                "memory_mb": 0,
            },
        )
    except ValueError:
        return

    raise AssertionError(
        "Non-positive resource requirement must be rejected."
    )


def test_boolean_resource_value_is_rejected():
    try:
        ResourceRequirements(
            resources={
                "memory_mb": True,
            },
        )
    except ValueError:
        return

    raise AssertionError(
        "Boolean resource requirement must be rejected."
    )


def test_non_string_resource_identifier_is_rejected():
    try:
        ResourceRequirements(
            resources={
                123: 512,
            },
        )
    except TypeError:
        return

    raise AssertionError(
        "Non-string resource identifiers must be rejected."
    )


TESTS = [
    test_empty_requirements,
    test_capabilities_are_preserved,
    test_single_resource_requirement,
    test_multiple_resource_requirements,
    test_capabilities_and_resources_are_independent,
    test_resource_dictionary_is_copied,
    test_invalid_resource_identifier_is_rejected,
    test_invalid_resource_value_is_rejected,
    test_boolean_resource_value_is_rejected,
    test_non_string_resource_identifier_is_rejected,
]


def main():
    print("=" * 70)
    print("RESOURCE REQUIREMENTS TESTS")
    print("=" * 70)

    passed = 0

    for test in TESTS:
        try:
            test()
            print(
                f"[PASS] {test.__name__}"
            )
            passed += 1
        except Exception as exc:
            print(
                f"[FAIL] {test.__name__}"
            )
            print(
                f"       {type(exc).__name__}: {exc}"
            )

    print()
    print(
        f"Tests: {passed}/{len(TESTS)}"
    )

    if passed == len(TESTS):
        print(
            "RESOURCE REQUIREMENTS: PASS"
        )
    else:
        print(
            "RESOURCE REQUIREMENTS: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())