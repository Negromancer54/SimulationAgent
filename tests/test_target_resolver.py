from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    TaskScope,
    TaskTarget,
    TargetKind,
)
from registries.target_directory import (
    TargetAvailability,
    TargetDirectory,
    TargetDirectoryError,
    TargetRecord,
)
from registries.target_resolver import (
    TargetResolution,
    TargetResolver,
    TargetResolverStatus,
)


def make_directory() -> TargetDirectory:
    directory = TargetDirectory()

    directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    directory.register(
        TargetRecord(
            kind=TargetKind.FILE,
            identifier="agent_task_v3.py",
            scope="runtime",
        )
    )

    directory.register(
        TargetRecord(
            kind=TargetKind.SYMBOL,
            identifier="TaskV3",
            scope="agent_task_v3",
        )
    )

    directory.register(
        TargetRecord(
            kind=TargetKind.SUBSYSTEM,
            identifier="task_runtime",
            scope="simulation_agent",
        )
    )

    directory.register(
        TargetRecord(
            kind=TargetKind.TEST,
            identifier="test_task_v3_model",
            scope="tests",
        )
    )

    return directory


def make_target(
    kind: TargetKind,
    identifier: str,
    scope: TaskScope,
) -> TaskTarget:
    return TaskTarget(
        kind=kind,
        identifier=identifier,
        scope=scope,
    )


def test_project_target_resolves() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.PROJECT,
        "simulation_zero",
        TaskScope(project="SimulationZero-Cpp"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.RESOLVED
    assert result.resolved
    assert result.record is not None
    assert result.record.kind is TargetKind.PROJECT


def test_file_target_resolves() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.FILE,
        "agent_task_v3.py",
        TaskScope(path="runtime"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.RESOLVED
    assert result.record is not None
    assert result.record.identifier == "agent_task_v3.py"


def test_symbol_target_resolves() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.SYMBOL,
        "TaskV3",
        TaskScope(namespace="agent_task_v3"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.RESOLVED
    assert result.record is not None


def test_subsystem_target_resolves() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.SUBSYSTEM,
        "task_runtime",
        TaskScope(namespace="simulation_agent"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.RESOLVED
    assert result.record is not None


def test_test_target_resolves() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.TEST,
        "test_task_v3_model",
        TaskScope(namespace="tests"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.RESOLVED
    assert result.record is not None


def test_unknown_target() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.FILE,
        "missing.py",
        TaskScope(path="runtime"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.NOT_FOUND
    assert not result.resolved
    assert result.record is None


def test_unavailable_target() -> None:
    directory = make_directory()

    directory.set_availability(
        TargetKind.FILE,
        "agent_task_v3.py",
        "runtime",
        TargetAvailability.UNAVAILABLE,
    )

    resolver = TargetResolver(directory)

    target = make_target(
        TargetKind.FILE,
        "agent_task_v3.py",
        TaskScope(path="runtime"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.UNAVAILABLE
    assert not result.resolved
    assert result.record is not None
    assert (
        result.record.availability
        is TargetAvailability.UNAVAILABLE
    )


def test_invalid_target_type() -> None:
    resolver = TargetResolver(make_directory())

    result = resolver.resolve(object())

    assert result.status is TargetResolverStatus.INVALID
    assert not result.resolved


def test_empty_identifier() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.PROJECT,
        "",
        TaskScope(project="SimulationZero-Cpp"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.INVALID
    assert not result.resolved
    assert "identifier" in result.message


def test_exact_address_is_required() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.FILE,
        "agent_task_v3.py",
        TaskScope(path="wrong_scope"),
    )

    result = resolver.resolve(target)

    assert result.status is TargetResolverStatus.NOT_FOUND
    assert not result.resolved


def test_target_is_not_mutated() -> None:
    resolver = TargetResolver(make_directory())

    target = make_target(
        TargetKind.SYMBOL,
        "TaskV3",
        TaskScope(namespace="agent_task_v3"),
    )

    before = target

    result = resolver.resolve(target)

    assert result.target is before


def main() -> int:
    tests = [
        test_project_target_resolves,
        test_file_target_resolves,
        test_symbol_target_resolves,
        test_subsystem_target_resolves,
        test_test_target_resolves,
        test_unknown_target,
        test_unavailable_target,
        test_invalid_target_type,
        test_empty_identifier,
        test_exact_address_is_required,
        test_target_is_not_mutated,
    ]

    print("=" * 70)
    print("TARGET RESOLVER TESTS")
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
        print("TARGET RESOLVER: PASS")
    else:
        print("TARGET RESOLVER: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())