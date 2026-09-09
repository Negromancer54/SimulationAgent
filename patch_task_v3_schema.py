from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schemas" / "task_v3.schema.json"


def main() -> int:
    if not SCHEMA_PATH.is_file():
        print(f"ERROR: schema not found: {SCHEMA_PATH}")
        return 1

    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    defs = schema["$defs"]

    # ------------------------------------------------------------------
    # STATE parameters
    # ------------------------------------------------------------------

    defs["stateParameters"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "property",
            "operator",
            "expected_value",
        ],
        "properties": {
            "property": {
                "type": "string",
                "minLength": 1,
            },
            "operator": {
                "type": "string",
                "enum": [
                    "EQUALS",
                    "NOT_EQUALS",
                    "GREATER",
                    "GREATER_OR_EQUAL",
                    "LESS",
                    "LESS_OR_EQUAL",
                    "IN",
                    "CONTAINS",
                ],
            },
            "expected_value": {},
        },
    }

    # ------------------------------------------------------------------
    # ASSERTION parameters
    # ------------------------------------------------------------------

    defs["assertionParameters"] = {
        "type": "object",
    }

    # ------------------------------------------------------------------
    # TEST parameters
    # ------------------------------------------------------------------

    defs["testParameters"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "expected_status",
        ],
        "properties": {
            "expected_status": {
                "type": "string",
                "enum": [
                    "PASSED",
                    "FAILED",
                    "SKIPPED",
                    "BLOCKED",
                ],
            },
        },
    }

    # ------------------------------------------------------------------
    # CHANGESET
    #
    # ADDED / MODIFIED / DELETED:
    #     path + kind
    #
    # RENAMED:
    #     old_path + new_path + kind
    # ------------------------------------------------------------------

    defs["changeRecord"] = {
        "oneOf": [
            {
                "title": "Added change record",
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "path",
                    "kind",
                ],
                "properties": {
                    "path": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "kind": {
                        "const": "ADDED",
                    },
                },
            },
            {
                "title": "Modified change record",
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "path",
                    "kind",
                ],
                "properties": {
                    "path": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "kind": {
                        "const": "MODIFIED",
                    },
                },
            },
            {
                "title": "Deleted change record",
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "path",
                    "kind",
                ],
                "properties": {
                    "path": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "kind": {
                        "const": "DELETED",
                    },
                },
            },
            {
                "title": "Renamed change record",
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "old_path",
                    "new_path",
                    "kind",
                ],
                "properties": {
                    "old_path": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "new_path": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "kind": {
                        "const": "RENAMED",
                    },
                },
            },
        ]
    }

    defs["changesetParameters"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "mode",
        ],
        "properties": {
            "mode": {
                "type": "string",
                "enum": [
                    "CONSTRAINED",
                    "EXACT",
                ],
            },
            "required": {
                "type": "array",
                "items": {
                    "$ref": "#/$defs/changeRecord",
                },
            },
            "allowed": {
                "type": "array",
                "items": {
                    "$ref": "#/$defs/changeRecord",
                },
            },
            "forbidden": {
                "type": "array",
                "items": {
                    "$ref": "#/$defs/changeRecord",
                },
            },
        },
    }

    # ------------------------------------------------------------------
    # ExpectedCondition
    # ------------------------------------------------------------------

    expected_condition = defs["expectedCondition"]

    expected_condition["allOf"] = [
        {
            "if": {
                "properties": {
                    "kind": {
                        "const": "STATE",
                    }
                },
                "required": ["kind"],
            },
            "then": {
                "properties": {
                    "parameters": {
                        "$ref": "#/$defs/stateParameters",
                    }
                }
            },
        },
        {
            "if": {
                "properties": {
                    "kind": {
                        "const": "ASSERTION",
                    }
                },
                "required": ["kind"],
            },
            "then": {
                "properties": {
                    "parameters": {
                        "$ref": "#/$defs/assertionParameters",
                    }
                }
            },
        },
        {
            "if": {
                "properties": {
                    "kind": {
                        "const": "TEST",
                    }
                },
                "required": ["kind"],
            },
            "then": {
                "properties": {
                    "parameters": {
                        "$ref": "#/$defs/testParameters",
                    }
                }
            },
        },
        {
            "if": {
                "properties": {
                    "kind": {
                        "const": "CHANGESET",
                    }
                },
                "required": ["kind"],
            },
            "then": {
                "properties": {
                    "parameters": {
                        "$ref": "#/$defs/changesetParameters",
                    }
                }
            },
        },
    ]

    # ------------------------------------------------------------------
    # Preconditions
    # ------------------------------------------------------------------

    precondition = defs["precondition"]

    precondition["allOf"] = [
        {
            "if": {
                "properties": {
                    "kind": {
                        "const": "STATE",
                    }
                },
                "required": ["kind"],
            },
            "then": {
                "properties": {
                    "parameters": {
                        "$ref": "#/$defs/stateParameters",
                    }
                }
            },
        },
        {
            "if": {
                "properties": {
                    "kind": {
                        "const": "ASSERTION",
                    }
                },
                "required": ["kind"],
            },
            "then": {
                "properties": {
                    "parameters": {
                        "$ref": "#/$defs/assertionParameters",
                    }
                }
            },
        },
        {
            "if": {
                "properties": {
                    "kind": {
                        "const": "TEST",
                    }
                },
                "required": ["kind"],
            },
            "then": {
                "properties": {
                    "parameters": {
                        "$ref": "#/$defs/testParameters",
                    }
                }
            },
        },
    ]

    with SCHEMA_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("TASK V3 SCHEMA PATCH: PASS")
    print(f"Updated: {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())