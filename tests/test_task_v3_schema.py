from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("ERROR: package 'jsonschema' is not installed.")
    print("Install it with:")
    print("    py -m pip install jsonschema")
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "task_v3.schema.json"


def load_schema() -> dict:
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(
            f"Schema not found:\n{SCHEMA_PATH}"
        )

    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema_definition(schema: dict) -> None:
    Draft202012Validator.check_schema(schema)


def make_base_task() -> dict:
    return {
        "schema_version": 3,
        "task_id": "V3-TEST-BASE",
        "description": "Base Task V3 schema validation task.",
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
        "expected": [
            {
                "id": "api_exists",
                "kind": "STATE",
                "identifier": "symbol.state",
                "version": 1,
                "parameters": {
                    "property": "symbol.exists",
                    "operator": "EQUALS",
                    "expected_value": True,
                },
            }
        ],
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


VALID_CASES: dict[str, dict] = {}


def register_valid(name: str, task: dict) -> None:
    VALID_CASES[name] = task


# ----------------------------------------------------------------------
# VALID CASES
# ----------------------------------------------------------------------

register_valid(
    "V3-EX-01 CHANGE + OUTCOME",
    make_base_task(),
)


task = make_base_task()
task["task_id"] = "V3-EX-02"
task["intent"]["goal"]["kind"] = "STATE"
task["intent"]["goal"]["identifier"] = "repository.clean"
register_valid(
    "V3-EX-02 CHANGE + STATE",
    task,
)


task = make_base_task()
task["task_id"] = "V3-EX-03"
task["intent"]["goal"]["kind"] = "ASSERTION"
task["intent"]["goal"]["identifier"] = "entity_identity_preserved"
task["intent"]["goal"]["parameters"] = {
    "scope": "migration_batch"
}
register_valid(
    "V3-EX-03 CHANGE + ASSERTION",
    task,
)


task = make_base_task()
task["task_id"] = "V3-EX-04"
task["intent"]["operation"] = "VERIFY"
task["intent"]["goal"]["kind"] = "STATE"
task["intent"]["goal"]["identifier"] = "repository.clean"
task["intent"]["goal"]["parameters"] = {}
register_valid(
    "V3-EX-04 VERIFY + STATE",
    task,
)


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
register_valid(
    "V3-EX-05 CHANGE + TEST",
    task,
)


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
register_valid(
    "V3-EX-06 CHANGESET",
    task,
)


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
register_valid(
    "V3-EX-07 PRECONDITIONS + POLICY",
    task,
)


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
register_valid(
    "V3-EX-08 MULTIPLE EXPECTED + VALIDATION",
    task,
)

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
register_valid(
    "V3-EX-09 CHANGESET RENAME",
    task,
)
# ----------------------------------------------------------------------
# INVALID CASES
# ----------------------------------------------------------------------

INVALID_CASES: dict[str, dict] = {}


def register_invalid(name: str, task: dict) -> None:
    INVALID_CASES[name] = task


# 01. Unknown operation.
task = make_base_task()
task["intent"]["operation"] = "INVALID_OPERATION"
register_invalid(
    "invalid operation",
    task,
)


# 02. Empty goal identifier.
task = make_base_task()
task["intent"]["goal"]["identifier"] = ""
register_invalid(
    "empty goal identifier",
    task,
)


# 03. Invalid target kind.
task = make_base_task()
task["intent"]["target"]["kind"] = "INVALID_TARGET_KIND"
register_invalid(
    "invalid target kind",
    task,
)


# 04. Invalid Expected kind.
task = make_base_task()
task["expected"][0]["kind"] = "INVALID_EXPECTED_KIND"
register_invalid(
    "invalid expected kind",
    task,
)


# 05. Invalid retry count.
task = make_base_task()
task["execution_policy"]["retry"]["max_attempts"] = 0
register_invalid(
    "invalid retry attempts",
    task,
)


# 06. Empty Expected condition ID.
task = make_base_task()
task["expected"][0]["id"] = ""
register_invalid(
    "empty expected condition id",
    task,
)


# 07. Unknown root-level property.
task = make_base_task()
task["unexpected_root_field"] = True
register_invalid(
    "unknown root property",
    task,
)


# 08. Missing required task_id.
task = make_base_task()
del task["task_id"]
register_invalid(
    "missing task_id",
    task,
)


# 09. Wrong type for description.
task = make_base_task()
task["description"] = 12345
register_invalid(
    "description wrong type",
    task,
)


# 10. Invalid schema version.
task = make_base_task()
task["schema_version"] = 2
register_invalid(
    "invalid schema version",
    task,
)


# 11. Invalid State operator.
task = make_base_task()
task["expected"][0]["parameters"]["operator"] = "INVALID_OPERATOR"
register_invalid(
    "invalid state operator",
    task,
)


# 12. Missing State property.
task = make_base_task()
del task["expected"][0]["parameters"]["property"]
register_invalid(
    "state missing property",
    task,
)


# 13. Invalid Test status.
task = make_base_task()
task["expected"] = [
    {
        "id": "test_zero_core_11",
        "kind": "TEST",
        "identifier": "ZERO-CORE-11",
        "version": 1,
        "parameters": {
            "expected_status": "NOT_A_TEST_STATUS"
        },
    }
]
register_invalid(
    "invalid test status",
    task,
)


# 14. Invalid CHANGESET mode.
task = make_base_task()
task["expected"] = [
    {
        "id": "changeset",
        "kind": "CHANGESET",
        "identifier": "project.changeset",
        "version": 1,
        "parameters": {
            "mode": "INVALID_MODE",
            "required": [],
            "allowed": [],
            "forbidden": [],
        },
    }
]
register_invalid(
    "invalid changeset mode",
    task,
)


# 15. Invalid CHANGESET change kind.
task = make_base_task()
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
                    "kind": "INVALID_CHANGE_KIND",
                }
            ],
            "allowed": [],
            "forbidden": [],
        },
    }
]
register_invalid(
    "invalid changeset change kind",
    task,
)


# 16. Validation missing applies_to.
task = make_base_task()
task["validation"] = [
    {
        "id": "validation_01",
        "identifier": "test_result_freshness",
        "version": 1,
        "evidence_requirements": [
            {
                "source_kind": "TEST_RESULT",
                "freshness": "POST_EXECUTION",
            }
        ],
    }
]
register_invalid(
    "validation missing applies_to",
    task,
)


# 17. Validation missing evidence_requirements.
task = make_base_task()
task["validation"] = [
    {
        "id": "validation_01",
        "identifier": "test_result_freshness",
        "version": 1,
        "applies_to": [
            "regression"
        ],
    }
]
register_invalid(
    "validation missing evidence requirements",
    task,
)


# 18. Wrong type for execution policy.
task = make_base_task()
task["execution_policy"]["retry"] = "invalid"
register_invalid(
    "execution policy retry wrong type",
    task,
)


# 19. Invalid failure mode.
task = make_base_task()
task["execution_policy"]["failure"]["mode"] = "INVALID_FAILURE_MODE"
register_invalid(
    "invalid failure mode",
    task,
)


# 20. Invalid rollback mode.
task = make_base_task()
task["execution_policy"]["rollback"]["mode"] = "INVALID_ROLLBACK_MODE"
register_invalid(
    "invalid rollback mode",
    task,
)
task = make_base_task()
task["task_id"] = "V3-INVALID-21"
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
                    "path": "src/World.hpp",
                    "kind": "RENAMED",
                }
            ],
            "allowed": [],
            "forbidden": [],
        },
    }
]
register_invalid(
    "renamed change missing old/new paths",
    task,
)


task = make_base_task()
task["task_id"] = "V3-INVALID-22"
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
                    "kind": "RENAMED",
                }
            ],
            "allowed": [],
            "forbidden": [],
        },
    }
]
register_invalid(
    "renamed change missing new_path",
    task,
)


task = make_base_task()
task["task_id"] = "V3-INVALID-23"
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
                    "old_path": "src/OldWorld.hpp",
                    "new_path": "src/World.hpp",
                    "kind": "MODIFIED",
                }
            ],
            "allowed": [],
            "forbidden": [],
        },
    }
]
register_invalid(
    "non-rename change with rename fields",
    task,
)

def validate_instance(
    validator: Draft202012Validator,
    instance: dict,
) -> list[str]:
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: list(error.path),
    )

    return [
        f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in errors
    ]


def run() -> int:
    print("=" * 70)
    print("TASK V3 JSON SCHEMA DEEP VALIDATION")
    print("=" * 70)
    print(f"Schema: {SCHEMA_PATH}")
    print()

    try:
        schema = load_schema()
    except Exception as exc:
        print("SCHEMA LOAD: FAIL")
        print(f"  {exc}")
        return 1

    try:
        validate_schema_definition(schema)
    except Exception as exc:
        print("SCHEMA DEFINITION: FAIL")
        print(f"  {exc}")
        return 1

    print("SCHEMA DEFINITION: PASS")
    print()

    validator = Draft202012Validator(schema)

    valid_passed = 0
    valid_total = len(VALID_CASES)

    print("-" * 70)
    print("VALID CASES")
    print("-" * 70)

    for name, task in VALID_CASES.items():
        errors = validate_instance(validator, task)

        if errors:
            print(f"[FAIL] {name}")
            for error in errors:
                print(f"       {error}")
        else:
            print(f"[PASS] {name}")
            valid_passed += 1

    print()
    print(f"Valid cases: {valid_passed}/{valid_total}")

    invalid_passed = 0
    invalid_total = len(INVALID_CASES)

    print()
    print("-" * 70)
    print("INVALID CASES")
    print("-" * 70)

    for name, task in INVALID_CASES.items():
        errors = validate_instance(validator, task)

        if errors:
            print(f"[PASS] correctly rejected: {name}")
            for error in errors:
                print(f"       {error}")
                break
            invalid_passed += 1
        else:
            print(f"[FAIL] incorrectly accepted: {name}")

    print()
    print(f"Invalid cases rejected: {invalid_passed}/{invalid_total}")

    print()
    print("=" * 70)

    overall_pass = (
        valid_passed == valid_total
        and invalid_passed == invalid_total
    )

    if overall_pass:
        print("DEEP SCHEMA VALIDATION: PASS")
        print("=" * 70)
        return 0

    print("DEEP SCHEMA VALIDATION: FAIL")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    raise SystemExit(run())