from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ============================================================================
# Basic enums
# ============================================================================


class TaskOperation(str, Enum):
    CHANGE = "CHANGE"
    VERIFY = "VERIFY"
    INSPECT = "INSPECT"
    MIGRATE = "MIGRATE"


class TargetKind(str, Enum):
    PROJECT = "PROJECT"
    FILE = "FILE"
    SYMBOL = "SYMBOL"
    SUBSYSTEM = "SUBSYSTEM"
    TEST = "TEST"


class GoalKind(str, Enum):
    OUTCOME = "OUTCOME"
    STATE = "STATE"
    ASSERTION = "ASSERTION"


class ExpectedKind(str, Enum):
    STATE = "STATE"
    ASSERTION = "ASSERTION"
    TEST = "TEST"
    CHANGESET = "CHANGESET"


class StateOperator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER = "GREATER"
    GREATER_OR_EQUAL = "GREATER_OR_EQUAL"
    LESS = "LESS"
    LESS_OR_EQUAL = "LESS_OR_EQUAL"
    IN = "IN"
    CONTAINS = "CONTAINS"


class TestExpectedStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"


class ChangeSetMode(str, Enum):
    CONSTRAINED = "CONSTRAINED"
    EXACT = "EXACT"


class ChangeKind(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"


class FailureMode(str, Enum):
    ABORT = "ABORT"
    ROLLBACK = "ROLLBACK"
    CONTINUE = "CONTINUE"


class RollbackMode(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# ============================================================================
# Target
# ============================================================================


@dataclass(frozen=True)
class TaskScope:
    project: str | None = None
    path: str | None = None
    namespace: str | None = None


@dataclass(frozen=True)
class TaskTarget:
    kind: TargetKind
    identifier: str
    scope: TaskScope = field(default_factory=TaskScope)


# ============================================================================
# Goal
# ============================================================================


@dataclass(frozen=True)
class TaskGoal:
    kind: GoalKind
    identifier: str
    version: int
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskIntent:
    operation: TaskOperation
    target: TaskTarget
    goal: TaskGoal


# ============================================================================
# Expected: STATE
# ============================================================================


@dataclass(frozen=True)
class StateExpectedParameters:
    property: str
    operator: StateOperator
    expected_value: Any


# ============================================================================
# Expected: TEST
# ============================================================================


@dataclass(frozen=True)
class TestExpectedParameters:
    expected_status: TestExpectedStatus


# ============================================================================
# Expected: CHANGESET
# ============================================================================


@dataclass(frozen=True)
class ChangeRecordPath:
    path: str
    kind: ChangeKind


@dataclass(frozen=True)
class RenameChangeRecord:
    old_path: str
    new_path: str
    kind: ChangeKind = ChangeKind.RENAMED


@dataclass(frozen=True)
class ChangeSetExpectedParameters:
    mode: ChangeSetMode
    required: list[ChangeRecordPath | RenameChangeRecord] = field(
        default_factory=list
    )
    allowed: list[ChangeRecordPath | RenameChangeRecord] = field(
        default_factory=list
    )
    forbidden: list[ChangeRecordPath | RenameChangeRecord] = field(
        default_factory=list
    )


# ============================================================================
# Expected condition
# ============================================================================


@dataclass(frozen=True)
class ExpectedCondition:
    id: str
    kind: ExpectedKind
    identifier: str
    version: int
    parameters: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Preconditions
# ============================================================================


@dataclass(frozen=True)
class Precondition:
    id: str
    kind: ExpectedKind
    identifier: str
    version: int
    parameters: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Validation
# ============================================================================


@dataclass(frozen=True)
class EvidenceRequirement:
    source_kind: str
    freshness: str


@dataclass(frozen=True)
class ValidationSpec:
    id: str
    identifier: str
    version: int
    applies_to: list[str]
    evidence_requirements: list[EvidenceRequirement] = field(
        default_factory=list
    )


# ============================================================================
# Execution policy
# ============================================================================


@dataclass(frozen=True)
class TimeoutPolicy:
    total_seconds: int


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1


@dataclass(frozen=True)
class ParallelismPolicy:
    max_workers: int = 1


@dataclass(frozen=True)
class ResourcePolicy:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FailurePolicy:
    mode: FailureMode = FailureMode.ABORT


@dataclass(frozen=True)
class RollbackPolicy:
    mode: RollbackMode = RollbackMode.REQUIRED


@dataclass(frozen=True)
class ExecutionPolicy:
    timeout: TimeoutPolicy
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    parallelism: ParallelismPolicy = field(
        default_factory=ParallelismPolicy
    )
    resources: ResourcePolicy = field(default_factory=ResourcePolicy)
    failure: FailurePolicy = field(default_factory=FailurePolicy)
    rollback: RollbackPolicy = field(default_factory=RollbackPolicy)


# ============================================================================
# Task V3
# ============================================================================


@dataclass(frozen=True)
class TaskV3:
    schema_version: int
    task_id: str
    description: str
    intent: TaskIntent

    preconditions: list[Precondition] = field(default_factory=list)
    expected: list[ExpectedCondition] = field(default_factory=list)
    validation: list[ValidationSpec] = field(default_factory=list)

    execution_policy: ExecutionPolicy | None = None
# ============================================================================
# JSON serialization / deserialization
# ============================================================================


def task_v3_from_dict(data: dict[str, Any]) -> TaskV3:
    if not isinstance(data, dict):
        raise TypeError("Task V3 must be represented by a dictionary.")

    intent_data = data["intent"]
    target_data = intent_data["target"]
    scope_data = target_data.get("scope", {})
    goal_data = intent_data["goal"]

    target = TaskTarget(
        kind=TargetKind(target_data["kind"]),
        identifier=target_data["identifier"],
        scope=TaskScope(
            project=scope_data.get("project"),
            path=scope_data.get("path"),
            namespace=scope_data.get("namespace"),
        ),
    )

    goal = TaskGoal(
        kind=GoalKind(goal_data["kind"]),
        identifier=goal_data["identifier"],
        version=goal_data["version"],
        parameters=dict(goal_data.get("parameters", {})),
    )

    intent = TaskIntent(
        operation=TaskOperation(intent_data["operation"]),
        target=target,
        goal=goal,
    )

    preconditions = [
        Precondition(
            id=item["id"],
            kind=ExpectedKind(item["kind"]),
            identifier=item["identifier"],
            version=item["version"],
            parameters=dict(item.get("parameters", {})),
        )
        for item in data.get("preconditions", [])
    ]

    expected = [
        ExpectedCondition(
            id=item["id"],
            kind=ExpectedKind(item["kind"]),
            identifier=item["identifier"],
            version=item["version"],
            parameters=dict(item.get("parameters", {})),
        )
        for item in data.get("expected", [])
    ]

    validation = [
        ValidationSpec(
            id=item["id"],
            identifier=item["identifier"],
            version=item["version"],
            applies_to=list(item["applies_to"]),
            evidence_requirements=[
                EvidenceRequirement(
                    source_kind=requirement["source_kind"],
                    freshness=requirement["freshness"],
                )
                for requirement in item["evidence_requirements"]
            ],
        )
        for item in data.get("validation", [])
    ]

    execution_policy_data = data.get("execution_policy")

    execution_policy = None

    if execution_policy_data is not None:
        timeout_data = execution_policy_data["timeout"]
        retry_data = execution_policy_data.get("retry", {})
        parallelism_data = execution_policy_data.get("parallelism", {})
        resources_data = execution_policy_data.get("resources", {})
        failure_data = execution_policy_data.get("failure", {})
        rollback_data = execution_policy_data.get("rollback", {})

        execution_policy = ExecutionPolicy(
            timeout=TimeoutPolicy(
                total_seconds=timeout_data["total_seconds"]
            ),
            retry=RetryPolicy(
                max_attempts=retry_data.get("max_attempts", 1)
            ),
            parallelism=ParallelismPolicy(
                max_workers=parallelism_data.get("max_workers", 1)
            ),
            resources=ResourcePolicy(
                values=dict(resources_data)
            ),
            failure=FailurePolicy(
                mode=FailureMode(
                    failure_data.get("mode", FailureMode.ABORT.value)
                )
            ),
            rollback=RollbackPolicy(
                mode=RollbackMode(
                    rollback_data.get(
                        "mode",
                        RollbackMode.REQUIRED.value,
                    )
                )
            ),
        )

    return TaskV3(
        schema_version=data["schema_version"],
        task_id=data["task_id"],
        description=data["description"],
        intent=intent,
        preconditions=preconditions,
        expected=expected,
        validation=validation,
        execution_policy=execution_policy,
    )


def _change_record_to_dict(
    record: ChangeRecordPath | RenameChangeRecord,
) -> dict[str, Any]:
    if isinstance(record, RenameChangeRecord):
        return {
            "old_path": record.old_path,
            "new_path": record.new_path,
            "kind": record.kind.value,
        }

    return {
        "path": record.path,
        "kind": record.kind.value,
    }


def _change_record_from_dict(
    data: dict[str, Any],
) -> ChangeRecordPath | RenameChangeRecord:
    kind = ChangeKind(data["kind"])

    if kind is ChangeKind.RENAMED:
        return RenameChangeRecord(
            old_path=data["old_path"],
            new_path=data["new_path"],
        )

    return ChangeRecordPath(
        path=data["path"],
        kind=kind,
    )


def task_v3_to_dict(task: TaskV3) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": task.schema_version,
        "task_id": task.task_id,
        "description": task.description,
        "intent": {
            "operation": task.intent.operation.value,
            "target": {
                "kind": task.intent.target.kind.value,
                "identifier": task.intent.target.identifier,
                "scope": {
                    "project": task.intent.target.scope.project,
                    "path": task.intent.target.scope.path,
                    "namespace": task.intent.target.scope.namespace,
                },
            },
            "goal": {
                "kind": task.intent.goal.kind.value,
                "identifier": task.intent.goal.identifier,
                "version": task.intent.goal.version,
                "parameters": dict(task.intent.goal.parameters),
            },
        },
        "preconditions": [
            {
                "id": item.id,
                "kind": item.kind.value,
                "identifier": item.identifier,
                "version": item.version,
                "parameters": dict(item.parameters),
            }
            for item in task.preconditions
        ],
        "expected": [],
        "validation": [
            {
                "id": item.id,
                "identifier": item.identifier,
                "version": item.version,
                "applies_to": list(item.applies_to),
                "evidence_requirements": [
                    {
                        "source_kind": requirement.source_kind,
                        "freshness": requirement.freshness,
                    }
                    for requirement in item.evidence_requirements
                ],
            }
            for item in task.validation
        ],
        "execution_policy": None,
    }

    for item in task.expected:
        expected_item: dict[str, Any] = {
            "id": item.id,
            "kind": item.kind.value,
            "identifier": item.identifier,
            "version": item.version,
            "parameters": dict(item.parameters),
        }

        if item.kind is ExpectedKind.CHANGESET:
            parameters = item.parameters

            normalized_parameters = dict(parameters)

            for key in ("required", "allowed", "forbidden"):
                if key in normalized_parameters:
                    normalized_parameters[key] = [
                        _change_record_to_dict(record)
                        if isinstance(
                            record,
                            (ChangeRecordPath, RenameChangeRecord),
                        )
                        else dict(record)
                        for record in normalized_parameters[key]
                    ]

            expected_item["parameters"] = normalized_parameters

        result["expected"].append(expected_item)

    if task.execution_policy is not None:
        policy = task.execution_policy

        result["execution_policy"] = {
            "timeout": {
                "total_seconds": policy.timeout.total_seconds,
            },
            "retry": {
                "max_attempts": policy.retry.max_attempts,
            },
            "parallelism": {
                "max_workers": policy.parallelism.max_workers,
            },
            "resources": dict(policy.resources.values),
            "failure": {
                "mode": policy.failure.mode.value,
            },
            "rollback": {
                "mode": policy.rollback.mode.value,
            },
        }

    return result
# ============================================================================
# Semantic validation
# ============================================================================


class TaskValidationCode(str, Enum):
    INVALID_SCHEMA_VERSION = "INVALID_SCHEMA_VERSION"
    EMPTY_TASK_ID = "EMPTY_TASK_ID"
    EMPTY_DESCRIPTION = "EMPTY_DESCRIPTION"

    EMPTY_TARGET_IDENTIFIER = "EMPTY_TARGET_IDENTIFIER"
    EMPTY_SCOPE_PROJECT = "EMPTY_SCOPE_PROJECT"
    EMPTY_SCOPE_PATH = "EMPTY_SCOPE_PATH"
    EMPTY_SCOPE_NAMESPACE = "EMPTY_SCOPE_NAMESPACE"

    EMPTY_GOAL_IDENTIFIER = "EMPTY_GOAL_IDENTIFIER"
    INVALID_GOAL_VERSION = "INVALID_GOAL_VERSION"

    DUPLICATE_PRECONDITION_ID = "DUPLICATE_PRECONDITION_ID"
    DUPLICATE_EXPECTED_ID = "DUPLICATE_EXPECTED_ID"
    DUPLICATE_VALIDATION_ID = "DUPLICATE_VALIDATION_ID"

    INVALID_PRECONDITION_KIND = "INVALID_PRECONDITION_KIND"

    EMPTY_PRECONDITION_IDENTIFIER = "EMPTY_PRECONDITION_IDENTIFIER"
    INVALID_PRECONDITION_VERSION = "INVALID_PRECONDITION_VERSION"

    EMPTY_EXPECTED_IDENTIFIER = "EMPTY_EXPECTED_IDENTIFIER"
    INVALID_EXPECTED_VERSION = "INVALID_EXPECTED_VERSION"

    EMPTY_VALIDATION_IDENTIFIER = "EMPTY_VALIDATION_IDENTIFIER"
    INVALID_VALIDATION_VERSION = "INVALID_VALIDATION_VERSION"


@dataclass(frozen=True)
class TaskValidationIssue:
    code: TaskValidationCode
    message: str
    path: str


@dataclass(frozen=True)
class TaskValidationResult:
    valid: bool
    issues: list[TaskValidationIssue] = field(
        default_factory=list
    )


def _is_positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_task_v3(task: TaskV3) -> TaskValidationResult:
    """
    Validate semantic invariants of an already constructed TaskV3.

    This function deliberately does NOT resolve:
        - GoalRegistry
        - TargetResolver
        - HandlerRegistry
        - StatePropertyRegistry
        - ExpectedRegistry
        - TestRegistry
        - runtime capabilities
        - runtime environment

    Those checks belong to later runtime layers.
    """

    issues: list[TaskValidationIssue] = []

    def add(
        code: TaskValidationCode,
        message: str,
        path: str,
    ) -> None:
        issues.append(
            TaskValidationIssue(
                code=code,
                message=message,
                path=path,
            )
        )

    # ------------------------------------------------------------------
    # Task identity
    # ------------------------------------------------------------------

    if task.schema_version != 3:
        add(
            TaskValidationCode.INVALID_SCHEMA_VERSION,
            "Task V3 schema_version must be 3.",
            "schema_version",
        )

    if not _is_non_empty_string(task.task_id):
        add(
            TaskValidationCode.EMPTY_TASK_ID,
            "task_id must be a non-empty string.",
            "task_id",
        )

    if not _is_non_empty_string(task.description):
        add(
            TaskValidationCode.EMPTY_DESCRIPTION,
            "description must be a non-empty string.",
            "description",
        )

    # ------------------------------------------------------------------
    # Target
    #
    # Scope fields are optional, but if present they must not be empty.
    # ------------------------------------------------------------------

    if not _is_non_empty_string(task.intent.target.identifier):
        add(
            TaskValidationCode.EMPTY_TARGET_IDENTIFIER,
            "target.identifier must be a non-empty string.",
            "intent.target.identifier",
        )

    scope = task.intent.target.scope

    if scope.project is not None and not _is_non_empty_string(scope.project):
        add(
            TaskValidationCode.EMPTY_SCOPE_PROJECT,
            "target.scope.project must be non-empty when provided.",
            "intent.target.scope.project",
        )

    if scope.path is not None and not _is_non_empty_string(scope.path):
        add(
            TaskValidationCode.EMPTY_SCOPE_PATH,
            "target.scope.path must be non-empty when provided.",
            "intent.target.scope.path",
        )

    if (
        scope.namespace is not None
        and not _is_non_empty_string(scope.namespace)
    ):
        add(
            TaskValidationCode.EMPTY_SCOPE_NAMESPACE,
            "target.scope.namespace must be non-empty when provided.",
            "intent.target.scope.namespace",
        )

    # ------------------------------------------------------------------
    # Goal
    # ------------------------------------------------------------------

    goal = task.intent.goal

    if not _is_non_empty_string(goal.identifier):
        add(
            TaskValidationCode.EMPTY_GOAL_IDENTIFIER,
            "goal.identifier must be a non-empty string.",
            "intent.goal.identifier",
        )

    if not _is_positive_integer(goal.version):
        add(
            TaskValidationCode.INVALID_GOAL_VERSION,
            "goal.version must be a positive integer.",
            "intent.goal.version",
        )

    # ------------------------------------------------------------------
    # Preconditions
    # ------------------------------------------------------------------

    precondition_ids: set[str] = set()

    allowed_precondition_kinds = {
        ExpectedKind.STATE,
        ExpectedKind.ASSERTION,
        ExpectedKind.TEST,
    }

    for index, precondition in enumerate(task.preconditions):
        path = f"preconditions[{index}]"

        if precondition.id in precondition_ids:
            add(
                TaskValidationCode.DUPLICATE_PRECONDITION_ID,
                f"Duplicate precondition id: {precondition.id}.",
                f"{path}.id",
            )
        else:
            precondition_ids.add(precondition.id)

        if precondition.kind not in allowed_precondition_kinds:
            add(
                TaskValidationCode.INVALID_PRECONDITION_KIND,
                (
                    "Precondition kind must be STATE, ASSERTION, "
                    "or TEST."
                ),
                f"{path}.kind",
            )

        if not _is_non_empty_string(precondition.identifier):
            add(
                TaskValidationCode.EMPTY_PRECONDITION_IDENTIFIER,
                "Precondition identifier must be non-empty.",
                f"{path}.identifier",
            )

        if not _is_positive_integer(precondition.version):
            add(
                TaskValidationCode.INVALID_PRECONDITION_VERSION,
                "Precondition version must be a positive integer.",
                f"{path}.version",
            )

    # ------------------------------------------------------------------
    # Expected
    # ------------------------------------------------------------------

    expected_ids: set[str] = set()

    for index, condition in enumerate(task.expected):
        path = f"expected[{index}]"

        if condition.id in expected_ids:
            add(
                TaskValidationCode.DUPLICATE_EXPECTED_ID,
                f"Duplicate expected condition id: {condition.id}.",
                f"{path}.id",
            )
        else:
            expected_ids.add(condition.id)

        if not _is_non_empty_string(condition.identifier):
            add(
                TaskValidationCode.EMPTY_EXPECTED_IDENTIFIER,
                "Expected identifier must be non-empty.",
                f"{path}.identifier",
            )

        if not _is_positive_integer(condition.version):
            add(
                TaskValidationCode.INVALID_EXPECTED_VERSION,
                "Expected version must be a positive integer.",
                f"{path}.version",
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    validation_ids: set[str] = set()

    for index, validation in enumerate(task.validation):
        path = f"validation[{index}]"

        if validation.id in validation_ids:
            add(
                TaskValidationCode.DUPLICATE_VALIDATION_ID,
                f"Duplicate validation id: {validation.id}.",
                f"{path}.id",
            )
        else:
            validation_ids.add(validation.id)

        if not _is_non_empty_string(validation.identifier):
            add(
                TaskValidationCode.EMPTY_VALIDATION_IDENTIFIER,
                "Validation identifier must be non-empty.",
                f"{path}.identifier",
            )

        if not _is_positive_integer(validation.version):
            add(
                TaskValidationCode.INVALID_VALIDATION_VERSION,
                "Validation version must be a positive integer.",
                f"{path}.version",
            )

    return TaskValidationResult(
        valid=not issues,
        issues=issues,
    )