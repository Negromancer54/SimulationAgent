from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from runtime.execution_plan import (
    ResourceRequirements,
)
from runtime.execution_policy import (
    ResourcePolicy,
)
from runtime.resource_admission import (
    ResourceAdmission,
    ResourceAdmissionStatus,
)


def make_admission():
    return ResourceAdmission()


def test_empty_requirements_are_allowed():
    result = make_admission().check(
        ResourceRequirements(),
        ResourcePolicy(
            values={}
        ),
    )

    assert result.status is ResourceAdmissionStatus.ALLOW
    assert result.allowed
    assert result.message == ""


def test_requirement_within_limit_is_allowed():
    result = make_admission().check(
        ResourceRequirements(
            resources={
                "memory_mb": 512,
            }
        ),
        ResourcePolicy(
            values={
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ResourceAdmissionStatus.ALLOW
    assert result.allowed


def test_requirement_equal_to_limit_is_allowed():
    result = make_admission().check(
        ResourceRequirements(
            resources={
                "memory_mb": 1024,
            }
        ),
        ResourcePolicy(
            values={
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ResourceAdmissionStatus.ALLOW
    assert result.allowed


def test_requirement_exceeding_limit_is_denied():
    result = make_admission().check(
        ResourceRequirements(
            resources={
                "memory_mb": 2048,
            }
        ),
        ResourcePolicy(
            values={
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ResourceAdmissionStatus.DENY
    assert result.denied


def test_missing_resource_is_denied():
    result = make_admission().check(
        ResourceRequirements(
            resources={
                "gpu_units": 1,
            }
        ),
        ResourcePolicy(
            values={
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ResourceAdmissionStatus.DENY
    assert result.denied


def test_multiple_resources_must_all_fit():
    result = make_admission().check(
        ResourceRequirements(
            resources={
                "memory_mb": 512,
                "cpu_threads": 2,
                "disk_mb": 4096,
            }
        ),
        ResourcePolicy(
            values={
                "memory_mb": 1024,
                "cpu_threads": 4,
                "disk_mb": 4096,
            }
        ),
    )

    assert result.status is ResourceAdmissionStatus.ALLOW


def test_one_excess_resource_denies_the_whole_step():
    result = make_admission().check(
        ResourceRequirements(
            resources={
                "memory_mb": 512,
                "cpu_threads": 8,
            }
        ),
        ResourcePolicy(
            values={
                "memory_mb": 1024,
                "cpu_threads": 4,
            }
        ),
    )

    assert result.status is ResourceAdmissionStatus.DENY


def test_capabilities_do_not_participate_in_resource_admission():
    result = make_admission().check(
        ResourceRequirements(
            capabilities=(
                "filesystem.write",
            ),
            resources={
                "memory_mb": 512,
            },
        ),
        ResourcePolicy(
            values={
                "memory_mb": 1024,
            }
        ),
    )

    assert result.status is ResourceAdmissionStatus.ALLOW


def test_resource_admission_does_not_modify_requirements():
    requirements = ResourceRequirements(
        resources={
            "memory_mb": 512,
        }
    )

    make_admission().check(
        requirements,
        ResourcePolicy(
            values={
                "memory_mb": 1024,
            }
        ),
    )

    assert requirements.resources == {
        "memory_mb": 512,
    }


def test_resource_admission_does_not_modify_policy():
    policy = ResourcePolicy(
        values={
            "memory_mb": 1024,
        }
    )

    make_admission().check(
        ResourceRequirements(
            resources={
                "memory_mb": 512,
            }
        ),
        policy,
    )

    assert policy.values == {
        "memory_mb": 1024,
    }


def test_invalid_requirements_type_is_rejected():
    try:
        make_admission().check(
            {},
            ResourcePolicy(
                values={}
            ),
        )
    except TypeError:
        return

    raise AssertionError(
        "Invalid requirements type must be rejected."
    )


def test_invalid_policy_type_is_rejected():
    try:
        make_admission().check(
            ResourceRequirements(),
            {},
        )
    except TypeError:
        return

    raise AssertionError(
        "Invalid policy type must be rejected."
    )


TESTS = [
    test_empty_requirements_are_allowed,
    test_requirement_within_limit_is_allowed,
    test_requirement_equal_to_limit_is_allowed,
    test_requirement_exceeding_limit_is_denied,
    test_missing_resource_is_denied,
    test_multiple_resources_must_all_fit,
    test_one_excess_resource_denies_the_whole_step,
    test_capabilities_do_not_participate_in_resource_admission,
    test_resource_admission_does_not_modify_requirements,
    test_resource_admission_does_not_modify_policy,
    test_invalid_requirements_type_is_rejected,
    test_invalid_policy_type_is_rejected,
]


def main():
    print("=" * 70)
    print("RESOURCE ADMISSION TESTS")
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
            "RESOURCE ADMISSION: PASS"
        )
    else:
        print(
            "RESOURCE ADMISSION: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())