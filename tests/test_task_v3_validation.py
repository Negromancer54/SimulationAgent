from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    ExpectedCondition,
    ExpectedKind,
    GoalKind,
    Precondition,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    TargetKind,
    validate_task_v3,
)


def make_valid_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="V3-VALIDATION-01",
        description="Semantic validation test.",
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=TaskTarget(
                kind=TargetKind.SUBSYSTEM,
                identifier="ComponentManager",
                scope=TaskScope(
                    project="SimulationZero",
                    path="src",
                    namespace="SimulationZero",
                ),
            ),
            goal=TaskGoal(
                kind=GoalKind.OUTCOME,
                identifier="component.add_generic_api",
                version=1,
                parameters={},
            ),
        ),
        preconditions=[],
        expected=[],
        validation=[],
        execution_policy=None,
    )


def test_valid_task() -> None:
    result = validate_task_v3(make_valid_task())

    assert result.valid is True
    assert result.issues == []


def test_invalid_schema_version() -> None:
    task = make_valid_task()
    task = TaskV3(
        schema_version=2,
        task_id=task.task_id,
        description=task.description,
        intent=task.intent,
    )

    result = validate_task_v3(task)

    assert result.valid is False
    assert any(
        issue.code.value == "INVALID_SCHEMA_VERSION"
        for issue in result.issues
    )


def test_empty_target_identifier() -> None:
    base = make_valid_task()

    task = TaskV3(
        schema_version=base.schema_version,
        task_id=base.task_id,
        description=base.description,
        intent=TaskIntent(
            operation=base.intent.operation,
            target=TaskTarget(
                kind=base.intent.target.kind,
                identifier="",
                scope=base.intent.target.scope,
            ),
            goal=base.intent.goal,
        ),
    )

    result = validate_task_v3(task)

    assert result.valid is False
    assert any(
        issue.code.value == "EMPTY_TARGET_IDENTIFIER"
        for issue in result.issues
    )


def test_duplicate_precondition_ids() -> None:
    base = make_valid_task()

    preconditions = [
        Precondition(
            id="repo_clean",
            kind=ExpectedKind.STATE,
            identifier="repository.clean",
            version=1,
            parameters={
                "property": "repository.clean",
                "operator": "EQUALS",
                "expected_value": True,
            },
        ),
        Precondition(
            id="repo_clean",
            kind=ExpectedKind.STATE,
            identifier="repository.clean",
            version=1,
            parameters={
                "property": "repository.clean",
                "operator": "EQUALS",
                "expected_value": True,
            },
        ),
    ]

    task = TaskV3(
        schema_version=base.schema_version,
        task_id=base.task_id,
        description=base.description,
        intent=base.intent,
        preconditions=preconditions,
    )

    result = validate_task_v3(task)

    assert result.valid is False
    assert any(
        issue.code.value == "DUPLICATE_PRECONDITION_ID"
        for issue in result.issues
    )


def test_duplicate_expected_ids() -> None:
    base = make_valid_task()

    expected = [
        ExpectedCondition(
            id="api_exists",
            kind=ExpectedKind.STATE,
            identifier="symbol.state",
            version=1,
            parameters={
                "property": "symbol.exists",
                "operator": "EQUALS",
                "expected_value": True,
            },
        ),
        ExpectedCondition(
            id="api_exists",
            kind=ExpectedKind.STATE,
            identifier="symbol.state",
            version=1,
            parameters={
                "property": "symbol.exists",
                "operator": "EQUALS",
                "expected_value": True,
            },
        ),
    ]

    task = TaskV3(
        schema_version=base.schema_version,
        task_id=base.task_id,
        description=base.description,
        intent=base.intent,
        expected=expected,
    )

    result = validate_task_v3(task)

    assert result.valid is False
    assert any(
        issue.code.value == "DUPLICATE_EXPECTED_ID"
        for issue in result.issues
    )


def test_changeset_precondition_rejected() -> None:
    base = make_valid_task()

    task = TaskV3(
        schema_version=base.schema_version,
        task_id=base.task_id,
        description=base.description,
        intent=base.intent,
        preconditions=[
            Precondition(
                id="changeset",
                kind=ExpectedKind.CHANGESET,
                identifier="project.changeset",
                version=1,
                parameters={
                    "mode": "EXACT",
                },
            )
        ],
    )

    result = validate_task_v3(task)

    assert result.valid is False
    assert any(
        issue.code.value == "INVALID_PRECONDITION_KIND"
        for issue in result.issues
    )


def test_invalid_goal_version() -> None:
    base = make_valid_task()

    task = TaskV3(
        schema_version=base.schema_version,
        task_id=base.task_id,
        description=base.description,
        intent=TaskIntent(
            operation=base.intent.operation,
            target=base.intent.target,
            goal=TaskGoal(
                kind=base.intent.goal.kind,
                identifier=base.intent.goal.identifier,
                version=0,
                parameters={},
            ),
        ),
    )

    result = validate_task_v3(task)

    assert result.valid is False
    assert any(
        issue.code.value == "INVALID_GOAL_VERSION"
        for issue in result.issues
    )


def main() -> int:
    tests = [
        test_valid_task,
        test_invalid_schema_version,
        test_empty_target_identifier,
        test_duplicate_precondition_ids,
        test_duplicate_expected_ids,
        test_changeset_precondition_rejected,
        test_invalid_goal_version,
    ]

    print("=" * 70)
    print("TASK V3 SEMANTIC VALIDATION TESTS")
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
        print("TASK V3 SEMANTIC VALIDATION: PASS")
    else:
        print("TASK V3 SEMANTIC VALIDATION: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())