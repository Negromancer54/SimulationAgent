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
from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
    PreconditionScope,
    PreconditionStatus,
    require_preconditions_satisfied,
)


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
        identifier="component.add_generic_api",
        kind=GoalKind.OUTCOME,
        version=1,
        parameters={},
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id="precondition-test",
        description="Evaluate preconditions.",
        intent=intent,
        preconditions=preconditions,
    )


def make_precondition(
    identifier: str,
    version: int = 1,
) -> Precondition:
    return Precondition(
        id=f"pc.{identifier}",
        kind="STATE",
        identifier=identifier,
        version=version,
        parameters={},
    )


def test_no_preconditions_are_satisfied() -> None:
    registry = PreconditionRegistry()
    evaluator = PreconditionEvaluator(registry)

    result = evaluator.evaluate(
        make_task()
    )

    assert result.evaluations == ()
    assert result.satisfied
    assert not result.has_failed
    assert not result.has_unavailable
    assert not result.has_error


def test_satisfied_task_precondition() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "project.exists",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    task = make_task(
        (
            make_precondition("project.exists"),
        )
    )

    result = PreconditionEvaluator(registry).evaluate(task)

    assert result.satisfied
    assert not result.has_failed
    assert not result.has_unavailable
    assert not result.has_error

    assert len(result.evaluations) == 1
    assert (
        result.evaluations[0].scope
        is PreconditionScope.TASK
    )


def test_failed_precondition_blocks_execution() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "project.clean",
        1,
        lambda precondition, context:
            PreconditionStatus.FAILED,
    )

    task = make_task(
        (
            make_precondition("project.clean"),
        )
    )

    result = PreconditionEvaluator(registry).evaluate(task)

    assert not result.satisfied
    assert result.has_failed

    try:
        require_preconditions_satisfied(result)
    except RuntimeError as exc:
        assert "FAILED" in str(exc)
        return

    raise AssertionError(
        "Execution was not blocked by a FAILED precondition."
    )


def test_unavailable_precondition_is_distinct() -> None:
    registry = PreconditionRegistry()

    task = make_task(
        (
            make_precondition("missing.check"),
        )
    )

    result = PreconditionEvaluator(registry).evaluate(task)

    assert not result.satisfied
    assert result.has_unavailable
    assert not result.has_failed

    try:
        require_preconditions_satisfied(result)
    except RuntimeError as exc:
        assert "UNAVAILABLE" in str(exc)
        return

    raise AssertionError(
        "Execution was not blocked by an UNAVAILABLE precondition."
    )


def test_error_precondition_is_distinct() -> None:
    registry = PreconditionRegistry()

    def failing_evaluator(precondition, context):
        raise RuntimeError("boom")

    registry.register(
        "runtime.check",
        1,
        failing_evaluator,
    )

    task = make_task(
        (
            make_precondition("runtime.check"),
        )
    )

    result = PreconditionEvaluator(registry).evaluate(task)

    assert not result.satisfied
    assert result.has_error
    assert not result.has_failed
    assert not result.has_unavailable

    try:
        require_preconditions_satisfied(result)
    except RuntimeError as exc:
        assert "ERROR" in str(exc)
        return

    raise AssertionError(
        "Execution was not blocked by an ERROR precondition."
    )


def test_goal_preconditions_are_evaluated() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "goal.ready",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    result = PreconditionEvaluator(registry).evaluate(
        make_task(),
        goal_preconditions=(
            make_precondition("goal.ready"),
        ),
    )

    assert result.satisfied
    assert (
        result.evaluations[0].scope
        is PreconditionScope.GOAL
    )


def test_runtime_safety_preconditions_are_evaluated() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "runtime.safe",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    result = PreconditionEvaluator(registry).evaluate(
        make_task(),
        runtime_safety_preconditions=(
            make_precondition("runtime.safe"),
        ),
    )

    assert result.satisfied
    assert (
        result.evaluations[0].scope
        is PreconditionScope.RUNTIME_SAFETY
    )


def test_effective_preconditions_use_and_semantics() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "task.ready",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    registry.register(
        "goal.ready",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    registry.register(
        "runtime.safe",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    task = make_task(
        (
            make_precondition("task.ready"),
        )
    )

    result = PreconditionEvaluator(registry).evaluate(
        task,
        goal_preconditions=(
            make_precondition("goal.ready"),
        ),
        runtime_safety_preconditions=(
            make_precondition("runtime.safe"),
        ),
    )

    assert result.satisfied
    assert len(result.evaluations) == 3


def test_one_failed_group_fails_effective_result() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "task.ready",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    registry.register(
        "goal.ready",
        1,
        lambda precondition, context:
            PreconditionStatus.FAILED,
    )

    registry.register(
        "runtime.safe",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    task = make_task(
        (
            make_precondition("task.ready"),
        )
    )

    result = PreconditionEvaluator(registry).evaluate(
        task,
        goal_preconditions=(
            make_precondition("goal.ready"),
        ),
        runtime_safety_preconditions=(
            make_precondition("runtime.safe"),
        ),
    )

    assert not result.satisfied
    assert result.has_failed
    assert len(result.evaluations) == 3


def test_duplicate_registry_registration_is_rejected() -> None:
    registry = PreconditionRegistry()

    evaluator = (
        lambda precondition, context:
        PreconditionStatus.SATISFIED
    )

    registry.register(
        "project.exists",
        1,
        evaluator,
    )

    try:
        registry.register(
            "project.exists",
            1,
            evaluator,
        )
    except ValueError:
        return

    raise AssertionError(
        "Duplicate precondition registration was accepted."
    )


def test_unknown_precondition_version_is_unavailable() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "project.exists",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    task = make_task(
        (
            make_precondition(
                "project.exists",
                version=2,
            ),
        )
    )

    result = PreconditionEvaluator(registry).evaluate(task)

    assert not result.satisfied
    assert result.has_unavailable


def test_original_task_is_not_modified() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "project.exists",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    task = make_task(
        (
            make_precondition("project.exists"),
        )
    )

    before = task

    result = PreconditionEvaluator(registry).evaluate(task)

    assert result.satisfied
    assert task is before
    assert result.evaluations[0].precondition_id == (
        "pc.project.exists"
    )


def test_all_evaluations_are_preserved() -> None:
    registry = PreconditionRegistry()

    registry.register(
        "one",
        1,
        lambda precondition, context:
            PreconditionStatus.SATISFIED,
    )

    registry.register(
        "two",
        1,
        lambda precondition, context:
            PreconditionStatus.FAILED,
    )

    registry.register(
        "three",
        1,
        lambda precondition, context:
            PreconditionStatus.UNAVAILABLE,
    )

    task = make_task(
        (
            make_precondition("one"),
            make_precondition("two"),
        )
    )

    result = PreconditionEvaluator(registry).evaluate(
        task,
        runtime_safety_preconditions=(
            make_precondition("three"),
        ),
    )

    assert len(result.evaluations) == 3
    assert result.has_failed
    assert result.has_unavailable


def main() -> int:
    tests = [
        test_no_preconditions_are_satisfied,
        test_satisfied_task_precondition,
        test_failed_precondition_blocks_execution,
        test_unavailable_precondition_is_distinct,
        test_error_precondition_is_distinct,
        test_goal_preconditions_are_evaluated,
        test_runtime_safety_preconditions_are_evaluated,
        test_effective_preconditions_use_and_semantics,
        test_one_failed_group_fails_effective_result,
        test_duplicate_registry_registration_is_rejected,
        test_unknown_precondition_version_is_unavailable,
        test_original_task_is_not_modified,
        test_all_evaluations_are_preserved,
    ]

    print("=" * 70)
    print("PRECONDITION TESTS")
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
        print("PRECONDITION RUNTIME: PASS")
    else:
        print("PRECONDITION RUNTIME: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())