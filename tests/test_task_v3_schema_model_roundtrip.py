from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_task_v3 import task_v3_from_dict, task_v3_to_dict


SCHEMA_PATH = ROOT / "schemas" / "task_v3.schema.json"


def load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def make_base_task() -> dict:
    return {
        "schema_version": 3,
        "task_id": "V3-ROUNDTRIP-BASE",
        "description": "Schema to Python model round-trip test.",
        "intent": {
            "operation": "CHANGE",
            "target": {
                "kind": "SUBSYSTEM",
                "identifier": "ComponentManager",
                "scope": {
                    "project": "SimulationZero",
                    "path": "src",
                    "namespace": "SimulationZero",
                },
            },
            "goal": {
                "kind": "OUTCOME",
                "identifier": "component.add_generic_api",
                "version": 1,
                "parameters": {
                    "component_type": "DebugComponent",
                    "api_surface": "World",
                },
            },
        },
        "preconditions": [],
        "expected": [],
        "validation": [],
        "execution_policy": {
            "timeout": {
                "total_seconds": 300
            },
            "retry": {
                "max_attempts": 1
            },
            "parallelism": {
                "max_workers": 1
            },
            "resources": {},
            "failure": {
                "mode": "ABORT"
            },
            "rollback": {
                "mode": "REQUIRED"
            },
        },
    }


def make_valid_cases() -> dict[str, dict]:
    cases: dict[str, dict] = {}

    task = make_base_task()
    cases["V3-EX-01 CHANGE + OUTCOME"] = task

    task = make_base_task()
    task["task_id"] = "V3-EX-02"
    task["intent"]["goal"]["kind"] = "STATE"
    task["intent"]["goal"]["identifier"] = "repository.clean"
    cases["V3-EX-02 CHANGE + STATE"] = task

    task = make_base_task()
    task["task_id"] = "V3-EX-03"
    task["intent"]["goal"]["kind"] = "ASSERTION"
    task["intent"]["goal"]["identifier"] = "entity_identity_preserved"
    task["intent"]["goal"]["parameters"] = {
        "scope": "migration_batch"
    }
    cases["V3-EX-03 CHANGE + ASSERTION"] = task

    task = make_base_task()
    task["task_id"] = "V3-EX-04"
    task["intent"]["operation"] = "VERIFY"
    task["intent"]["goal"]["kind"] = "STATE"
    task["intent"]["goal"]["identifier"] = "repository.clean"
    task["intent"]["goal"]["parameters"] = {}
    cases["V3-EX-04 VERIFY + STATE"] = task

    task = make_base_task()
    task["task_id"] = "V3-EX-05"
    task["expected"] = [
        {
            "id": "test_zero_core_11",
            "kind": "TEST",
            "identifier": "ZERO-CORE-11",
            "version": 1,
            "parameters": {
                "expected_status": "PASSED"
            },
        }
    ]
    cases["V3-EX-05 CHANGE + TEST"] = task

    task = make_base_task()
    task["task_id"] = "V3-EX-06"
    task["expected"] = [
        {
            "id": "changeset",
            "kind": "CHANGESET",
            "identifier": "project.changeset",
            "version": 1,
            "parameters": {
                "mode": "EXACT",
                "required": [
                    {
                        "path": "src/World.hpp",
                        "kind": "MODIFIED",
                    },
                    {
                        "path": "src/World.cpp",
                        "kind": "MODIFIED",
                    },
                ],
                "allowed": [
                    {
                        "path": "src/World.hpp",
                        "kind": "MODIFIED",
                    },
                    {
                        "path": "src/World.cpp",
                        "kind": "MODIFIED",
                    },
                ],
                "forbidden": [],
            },
        }
    ]
    cases["V3-EX-06 CHANGESET"] = task

    task = make_base_task()
    task["task_id"] = "V3-EX-07"
    task["preconditions"] = [
        {
            "id": "repo_clean",
            "kind": "STATE",
            "identifier": "repository.clean",
            "version": 1,
            "parameters": {
                "property": "repository.clean",
                "operator": "EQUALS",
                "expected_value": True,
            },
        },
        {
            "id": "workspace_unlocked",
            "kind": "STATE",
            "identifier": "workspace.unlocked",
            "version": 1,
            "parameters": {
                "property": "workspace.locked",
                "operator": "EQUALS",
                "expected_value": False,
            },
        },
    ]
    cases["V3-EX-07 PRECONDITIONS + POLICY"] = task

    task = make_base_task()
    task["task_id"] = "V3-EX-08"
    task["expected"] = [
        {
            "id": "symbol_exists",
            "kind": "STATE",
            "identifier": "symbol.state",
            "version": 1,
            "parameters": {
                "property": "symbol.exists",
                "operator": "EQUALS",
                "expected_value": True,
            },
        },
        {
            "id": "regression",
            "kind": "TEST",
            "identifier": "ZERO-CORE-11",
            "version": 1,
            "parameters": {
                "expected_status": "PASSED"
            },
        },
    ]
    task["validation"] = [
        {
            "id": "fresh_test_result",
            "identifier": "test_result_freshness",
            "version": 1,
            "applies_to": [
                "regression"
            ],
            "evidence_requirements": [
                {
                    "source_kind": "TEST_RESULT",
                    "freshness": "POST_EXECUTION",
                }
            ],
        }
    ]
    cases["V3-EX-08 MULTIPLE EXPECTED + VALIDATION"] = task

    task = make_base_task()
    task["task_id"] = "V3-EX-09"
    task["expected"] = [
        {
            "id": "rename",
            "kind": "CHANGESET",
            "identifier": "project.changeset",
            "version": 1,
            "parameters": {
                "mode": "EXACT",
                "required": [
                    {
                        "old_path": "src/OldWorld.hpp",
                        "new_path": "src/World.hpp",
                        "kind": "RENAMED",
                    }
                ],
                "allowed": [
                    {
                        "old_path": "src/OldWorld.hpp",
                        "new_path": "src/World.hpp",
                        "kind": "RENAMED",
                    }
                ],
                "forbidden": [],
            },
        }
    ]
    cases["V3-EX-09 CHANGESET RENAME"] = task

    return cases


def test_schema_accepts_original(instance: dict, validator: Draft202012Validator) -> None:
    errors = list(validator.iter_errors(instance))

    if errors:
        messages = "\n".join(
            f"  {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise AssertionError(
            "Original JSON instance is not accepted by schema:\n"
            + messages
        )


def test_round_trip(case_name: str, instance: dict, validator: Draft202012Validator) -> None:
    test_schema_accepts_original(instance, validator)

    model = task_v3_from_dict(copy.deepcopy(instance))
    serialized = task_v3_to_dict(model)

    if serialized != instance:
        raise AssertionError(
            f"{case_name}: JSON changed during round-trip.\n"
            f"Original:\n{json.dumps(instance, ensure_ascii=False, indent=2, sort_keys=True)}\n"
            f"Serialized:\n{json.dumps(serialized, ensure_ascii=False, indent=2, sort_keys=True)}"
        )

    test_schema_accepts_original(serialized, validator)


def main() -> int:
    print("=" * 70)
    print("TASK V3 SCHEMA <-> PYTHON MODEL ROUND-TRIP")
    print("=" * 70)
    print(f"Schema: {SCHEMA_PATH}")
    print()

    if not SCHEMA_PATH.is_file():
        print("SCHEMA LOAD: FAIL")
        print(f"  File not found: {SCHEMA_PATH}")
        return 1

    try:
        schema = load_schema()
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        print("SCHEMA DEFINITION: FAIL")
        print(f"  {exc}")
        return 1

    print("SCHEMA DEFINITION: PASS")
    print()

    validator = Draft202012Validator(schema)
    cases = make_valid_cases()

    passed = 0

    print("-" * 70)
    print("ROUND-TRIP CASES")
    print("-" * 70)

    for case_name, instance in cases.items():
        try:
            test_round_trip(case_name, instance, validator)
            print(f"[PASS] {case_name}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {case_name}")
            print(f"       {type(exc).__name__}: {exc}")

    print()
    print(f"Round-trip cases: {passed}/{len(cases)}")
    print()

    if passed == len(cases):
        print("=" * 70)
        print("SCHEMA <-> PYTHON MODEL ROUND-TRIP: PASS")
        print("=" * 70)
        return 0

    print("=" * 70)
    print("SCHEMA <-> PYTHON MODEL ROUND-TRIP: FAIL")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())