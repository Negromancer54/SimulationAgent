from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agent_task_v3 import (
    ChangeKind,
    ChangeRecordPath,
    ChangeSetExpectedParameters,
    ChangeSetMode,
    EvidenceRequirement,
    ExecutionPolicy,
    ExpectedCondition,
    ExpectedKind,
    FailureMode,
    FailurePolicy,
    GoalKind,
    ParallelismPolicy,
    Precondition,
    RenameChangeRecord,
    ResourcePolicy,
    RetryPolicy,
    RollbackMode,
    RollbackPolicy,
    StateExpectedParameters,
    StateOperator,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TaskV3,
    TargetKind,
    TestExpectedParameters,
    TestExpectedStatus,
    TimeoutPolicy,
    ValidationSpec,
    task_v3_from_dict,
    task_v3_to_dict,
)


def make_base_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="V3-MODEL-BASE",
        description="Base Task V3 model.",
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
                parameters={
                    "component_type": "DebugComponent",
                    "api_surface": "World",
                },
            ),
        ),
        preconditions=[],
        expected=[],
        validation=[],
        execution_policy=None,
    )


def test_basic_model_construction() -> None:
    task = make_base_task()

    assert task.schema_version == 3
    assert task.task_id == "V3-MODEL-BASE"
    assert task.intent.operation is TaskOperation.CHANGE
    assert task.intent.target.kind is TargetKind.SUBSYSTEM
    assert task.intent.target.identifier == "ComponentManager"
    assert task.intent.goal.kind is GoalKind.OUTCOME
    assert task.intent.goal.identifier == "component.add_generic_api"


def test_state_expected_parameters() -> None:
    parameters = StateExpectedParameters(
        property="symbol.exists",
        operator=StateOperator.EQUALS,
        expected_value=True,
    )

    assert parameters.property == "symbol.exists"
    assert parameters.operator is StateOperator.EQUALS
    assert parameters.expected_value is True


def test_test_expected_parameters() -> None:
    parameters = TestExpectedParameters(
        expected_status=TestExpectedStatus.PASSED,
    )

    assert parameters.expected_status is TestExpectedStatus.PASSED


def test_changeset_parameters() -> None:
    parameters = ChangeSetExpectedParameters(
        mode=ChangeSetMode.EXACT,
        required=[
            ChangeRecordPath(
                path="src/World.hpp",
                kind=ChangeKind.MODIFIED,
            ),
            RenameChangeRecord(
                old_path="src/OldWorld.cpp",
                new_path="src/World.cpp",
            ),
        ],
    )

    assert parameters.mode is ChangeSetMode.EXACT
    assert len(parameters.required) == 2
    assert parameters.required[0].kind is ChangeKind.MODIFIED
    assert parameters.required[1].kind is ChangeKind.RENAMED


def test_precondition() -> None:
    precondition = Precondition(
        id="repo_clean",
        kind=ExpectedKind.STATE,
        identifier="repository.clean",
        version=1,
        parameters={
            "property": "repository.clean",
            "operator": "EQUALS",
            "expected_value": True,
        },
    )

    assert precondition.id == "repo_clean"
    assert precondition.kind is ExpectedKind.STATE
    assert precondition.identifier == "repository.clean"


def test_validation() -> None:
    validation = ValidationSpec(
        id="fresh_test_result",
        identifier="test_result_freshness",
        version=1,
        applies_to=["regression"],
        evidence_requirements=[],
    )

    assert validation.id == "fresh_test_result"
    assert validation.identifier == "test_result_freshness"
    assert validation.applies_to == ["regression"]


def test_execution_policy() -> None:
    policy = {
        "timeout": TimeoutPolicy(total_seconds=300),
        "retry": RetryPolicy(max_attempts=1),
        "rollback": RollbackPolicy(mode=RollbackMode.REQUIRED),
    }

    assert policy["timeout"].total_seconds == 300
    assert policy["retry"].max_attempts == 1
    assert policy["rollback"].mode is RollbackMode.REQUIRED


def test_complete_task() -> None:
    task = make_base_task()

    task = TaskV3(
        schema_version=task.schema_version,
        task_id=task.task_id,
        description=task.description,
        intent=task.intent,
        preconditions=[
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
            )
        ],
        expected=[
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
                id="regression",
                kind=ExpectedKind.TEST,
                identifier="ZERO-CORE-11",
                version=1,
                parameters={
                    "expected_status": "PASSED",
                },
            ),
        ],
        validation=[
            ValidationSpec(
                id="fresh_test_result",
                identifier="test_result_freshness",
                version=1,
                applies_to=["regression"],
                evidence_requirements=[],
            )
        ],
    )

    assert len(task.preconditions) == 1
    assert len(task.expected) == 2
    assert len(task.validation) == 1


def test_enum_values_match_contract() -> None:
    assert {item.value for item in TaskOperation} == {
        "CHANGE",
        "VERIFY",
        "INSPECT",
        "MIGRATE",
    }

    assert {item.value for item in TargetKind} == {
        "PROJECT",
        "FILE",
        "SYMBOL",
        "SUBSYSTEM",
        "TEST",
    }

    assert {item.value for item in GoalKind} == {
        "OUTCOME",
        "STATE",
        "ASSERTION",
    }

    assert {item.value for item in ExpectedKind} == {
        "STATE",
        "ASSERTION",
        "TEST",
        "CHANGESET",
    }

def test_json_round_trip() -> None:
    task = make_base_task()

    task = TaskV3(
        schema_version=task.schema_version,
        task_id=task.task_id,
        description=task.description,
        intent=task.intent,
        preconditions=[
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
            )
        ],
        expected=[
            ExpectedCondition(
                id="symbol_exists",
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
                id="rename",
                kind=ExpectedKind.CHANGESET,
                identifier="project.changeset",
                version=1,
                parameters={
                    "mode": "EXACT",
                    "required": [
                        RenameChangeRecord(
                            old_path="src/OldWorld.hpp",
                            new_path="src/World.hpp",
                        )
                    ],
                    "allowed": [
                        RenameChangeRecord(
                            old_path="src/OldWorld.hpp",
                            new_path="src/World.hpp",
                        )
                    ],
                    "forbidden": [],
                },
            ),
        ],
        validation=[
            ValidationSpec(
                id="fresh_test_result",
                identifier="test_result_freshness",
                version=1,
                applies_to=["rename"],
                evidence_requirements=[
                    EvidenceRequirement(
                        source_kind="TEST_RESULT",
                        freshness="POST_EXECUTION",
                    )
                ],
            )
        ],
        execution_policy=ExecutionPolicy(
            timeout=TimeoutPolicy(total_seconds=300),
            retry=RetryPolicy(max_attempts=1),
            parallelism=ParallelismPolicy(max_workers=1),
            resources=ResourcePolicy(values={}),
            failure=FailurePolicy(mode=FailureMode.ABORT),
            rollback=RollbackPolicy(mode=RollbackMode.REQUIRED),
        ),
    )

    serialized = task_v3_to_dict(task)
    restored = task_v3_from_dict(serialized)
    restored_serialized = task_v3_to_dict(restored)

    assert serialized == restored_serialized
def main() -> None:
    tests = [
        test_basic_model_construction,
        test_state_expected_parameters,
        test_test_expected_parameters,
        test_changeset_parameters,
        test_precondition,
        test_validation,
        test_execution_policy,
        test_complete_task,
        test_enum_values_match_contract,
        test_json_round_trip,
    ]

    print("=" * 70)
    print("TASK V3 PYTHON MODEL TESTS")
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
        print("TASK V3 PYTHON MODEL: PASS")
    else:
        print("TASK V3 PYTHON MODEL: FAIL")

    print("=" * 70)

    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()