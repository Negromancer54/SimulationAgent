from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_task_v3 import (
    ChangeKind,
    ChangeRecordPath,
    ChangeSetExpectedParameters,
    ChangeSetMode,
    ExpectedCondition,
    ExpectedKind,
    RenameChangeRecord,
)
from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceStatus,
    EvidenceStore,
)


class ChangeSetEvaluationStatus(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ChangeRecord:
    """
    Runtime representation of one observed project change.

    Non-rename:
        path is set.

    Rename:
        old_path and new_path are set.
    """

    kind: ChangeKind
    path: str | None = None
    old_path: str | None = None
    new_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ChangeKind):
            raise ValueError(
                "ChangeRecord.kind must be a ChangeKind."
            )

        if self.kind is ChangeKind.RENAMED:
            if (
                not isinstance(self.old_path, str)
                or not self.old_path.strip()
            ):
                raise ValueError(
                    "RENAMED ChangeRecord requires old_path."
                )

            if (
                not isinstance(self.new_path, str)
                or not self.new_path.strip()
            ):
                raise ValueError(
                    "RENAMED ChangeRecord requires new_path."
                )

            if self.path is not None:
                raise ValueError(
                    "RENAMED ChangeRecord must not contain path."
                )

        else:
            if (
                not isinstance(self.path, str)
                or not self.path.strip()
            ):
                raise ValueError(
                    "Non-RENAMED ChangeRecord requires path."
                )

            if self.old_path is not None:
                raise ValueError(
                    "Non-RENAMED ChangeRecord must not contain old_path."
                )

            if self.new_path is not None:
                raise ValueError(
                    "Non-RENAMED ChangeRecord must not contain new_path."
                )


@dataclass(frozen=True)
class ChangeSetEvaluation:
    expected_id: str
    status: ChangeSetEvaluationStatus
    evidence_ids: tuple[str, ...] = ()
    actual_changes: tuple[ChangeRecord, ...] = ()
    message: str = ""

    @property
    def satisfied(self) -> bool:
        return self.status is ChangeSetEvaluationStatus.SATISFIED


class ChangeSetEvaluator:
    """
    Evaluates ExpectedKind.CHANGESET against CHANGESET evidence.

    The evaluator is read-only.

    It does not:
        - create evidence;
        - modify evidence;
        - modify the task;
        - compute a raw diff;
        - inspect the filesystem.
    """

    @staticmethod
    def _parse_change(record: object) -> ChangeRecord:
        if not isinstance(record, dict):
            raise ValueError(
                "A CHANGESET evidence record must be an object."
            )

        kind_value = record.get("kind")

        try:
            kind = ChangeKind(kind_value)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Unknown change kind: {kind_value}"
            ) from exc

        if kind is ChangeKind.RENAMED:
            old_path = record.get("old_path")
            new_path = record.get("new_path")

            return ChangeRecord(
                kind=kind,
                old_path=old_path,
                new_path=new_path,
            )

        return ChangeRecord(
            kind=kind,
            path=record.get("path"),
        )

    @classmethod
    def _changes_from_evidence(
        cls,
        evidence: Evidence,
    ) -> tuple[ChangeRecord, ...]:
        value = evidence.value

        if isinstance(value, dict):
            changes = value.get("changes")

            if changes is None:
                raise ValueError(
                    "CHANGESET evidence must contain 'changes'."
                )

        elif isinstance(value, list):
            changes = value

        elif isinstance(value, tuple):
            changes = list(value)

        else:
            raise ValueError(
                "CHANGESET evidence value must be a list or object "
                "containing 'changes'."
            )

        return tuple(
            cls._parse_change(record)
            for record in changes
        )

    @staticmethod
    def _change_key(
        change: ChangeRecord,
    ) -> tuple:
        if change.kind is ChangeKind.RENAMED:
            return (
                change.kind.value,
                change.old_path,
                change.new_path,
            )

        return (
            change.kind.value,
            change.path,
        )

    @classmethod
    def _record_to_key(
        cls,
        record: ChangeRecordPath | RenameChangeRecord,
    ) -> tuple:
        if isinstance(record, RenameChangeRecord):
            return (
                ChangeKind.RENAMED.value,
                record.old_path,
                record.new_path,
            )

        if isinstance(record, ChangeRecordPath):
            return (
                record.kind.value,
                record.path,
            )

        raise ValueError(
            "Unsupported expected change record type."
        )

    @classmethod
    def _expected_to_keys(
        cls,
        records: list[
            ChangeRecordPath | RenameChangeRecord
        ],
    ) -> set[tuple]:
        return {
            cls._record_to_key(record)
            for record in records
        }

    @staticmethod
    def _expected_parameters(
        expected: ExpectedCondition,
    ) -> ChangeSetExpectedParameters:
        parameters = expected.parameters

        if not isinstance(parameters, dict):
            raise ValueError(
                "CHANGESET ExpectedCondition.parameters must be a dictionary."
            )

        if "mode" not in parameters:
            raise ValueError(
                "CHANGESET parameter 'mode' is required."
            )

        mode_raw = parameters["mode"]

        try:
            mode = ChangeSetMode(mode_raw)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Unsupported CHANGESET mode: {mode_raw}"
            ) from exc

        required_raw = parameters.get("required", [])
        allowed_raw = parameters.get("allowed", [])
        forbidden_raw = parameters.get("forbidden", [])

        if not isinstance(required_raw, list):
            raise ValueError(
                "CHANGESET 'required' must be a list."
            )

        if not isinstance(allowed_raw, list):
            raise ValueError(
                "CHANGESET 'allowed' must be a list."
            )

        if not isinstance(forbidden_raw, list):
            raise ValueError(
                "CHANGESET 'forbidden' must be a list."
            )

        required = [
            ChangeSetEvaluator._parse_expected_record(item)
            for item in required_raw
        ]

        allowed = [
            ChangeSetEvaluator._parse_expected_record(item)
            for item in allowed_raw
        ]

        forbidden = [
            ChangeSetEvaluator._parse_expected_record(item)
            for item in forbidden_raw
        ]

        return ChangeSetExpectedParameters(
            mode=mode,
            required=required,
            allowed=allowed,
            forbidden=forbidden,
        )

    @staticmethod
    def _parse_expected_record(
        record: object,
    ) -> ChangeRecordPath | RenameChangeRecord:
        if not isinstance(record, dict):
            raise ValueError(
                "Expected CHANGESET record must be an object."
            )

        kind_value = record.get("kind")

        try:
            kind = ChangeKind(kind_value)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Unknown expected change kind: {kind_value}"
            ) from exc

        if kind is ChangeKind.RENAMED:
            return RenameChangeRecord(
                old_path=record.get("old_path"),
                new_path=record.get("new_path"),
                kind=kind,
            )

        return ChangeRecordPath(
            path=record.get("path"),
            kind=kind,
        )

    @classmethod
    def _find_changeset_evidence(
        cls,
        evidence_store: EvidenceStore,
    ) -> list[Evidence]:
        return [
            evidence
            for evidence in evidence_store.list()
            if (
                evidence.kind is EvidenceKind.CHANGESET
                and evidence.status is EvidenceStatus.VALID
            )
        ]

    @classmethod
    def _evaluate_constrained(
        cls,
        expected: ExpectedCondition,
        parameters: ChangeSetExpectedParameters,
        actual: tuple[ChangeRecord, ...],
        evidence_ids: tuple[str, ...],
    ) -> ChangeSetEvaluation:
        actual_keys = {
            cls._change_key(change)
            for change in actual
        }

        required_keys = cls._expected_to_keys(
            parameters.required
        )

        forbidden_keys = cls._expected_to_keys(
            parameters.forbidden
        )

        allowed_keys = cls._expected_to_keys(
            parameters.allowed
        )

        missing = required_keys - actual_keys

        if missing:
            return ChangeSetEvaluation(
                expected_id=expected.id,
                status=ChangeSetEvaluationStatus.NOT_SATISFIED,
                evidence_ids=evidence_ids,
                actual_changes=actual,
                message=(
                    "Required changes are missing."
                ),
            )

        forbidden_present = actual_keys & forbidden_keys

        if forbidden_present:
            return ChangeSetEvaluation(
                expected_id=expected.id,
                status=ChangeSetEvaluationStatus.NOT_SATISFIED,
                evidence_ids=evidence_ids,
                actual_changes=actual,
                message=(
                    "Forbidden changes are present."
                ),
            )

        if allowed_keys:
            outside_allowed = actual_keys - allowed_keys

            if outside_allowed:
                return ChangeSetEvaluation(
                    expected_id=expected.id,
                    status=ChangeSetEvaluationStatus.NOT_SATISFIED,
                    evidence_ids=evidence_ids,
                    actual_changes=actual,
                    message=(
                        "Observed changes contain records "
                        "outside the allowed set."
                    ),
                )

        return ChangeSetEvaluation(
            expected_id=expected.id,
            status=ChangeSetEvaluationStatus.SATISFIED,
            evidence_ids=evidence_ids,
            actual_changes=actual,
        )

    @classmethod
    def _evaluate_exact(
        cls,
        expected: ExpectedCondition,
        parameters: ChangeSetExpectedParameters,
        actual: tuple[ChangeRecord, ...],
        evidence_ids: tuple[str, ...],
    ) -> ChangeSetEvaluation:
        actual_keys = {
            cls._change_key(change)
            for change in actual
        }

        required_keys = cls._expected_to_keys(
            parameters.required
        )

        if actual_keys != required_keys:
            return ChangeSetEvaluation(
                expected_id=expected.id,
                status=ChangeSetEvaluationStatus.NOT_SATISFIED,
                evidence_ids=evidence_ids,
                actual_changes=actual,
                message=(
                    "Actual CHANGESET does not exactly match "
                    "the required set."
                ),
            )

        return ChangeSetEvaluation(
            expected_id=expected.id,
            status=ChangeSetEvaluationStatus.SATISFIED,
            evidence_ids=evidence_ids,
            actual_changes=actual,
        )

    @classmethod
    def evaluate(
        cls,
        expected: ExpectedCondition,
        evidence_store: EvidenceStore,
    ) -> ChangeSetEvaluation:
        if not isinstance(expected, ExpectedCondition):
            raise TypeError(
                "ChangeSetEvaluator accepts only ExpectedCondition."
            )

        if expected.kind is not ExpectedKind.CHANGESET:
            raise ValueError(
                "ChangeSetEvaluator requires ExpectedKind.CHANGESET."
            )

        if not isinstance(evidence_store, EvidenceStore):
            raise TypeError(
                "ChangeSetEvaluator requires an EvidenceStore."
            )

        try:
            parameters = cls._expected_parameters(
                expected
            )
        except Exception as exc:
            return ChangeSetEvaluation(
                expected_id=expected.id,
                status=ChangeSetEvaluationStatus.ERROR,
                message=(
                    f"CHANGESET expectation could not be parsed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        evidence = cls._find_changeset_evidence(
            evidence_store
        )

        if not evidence:
            return ChangeSetEvaluation(
                expected_id=expected.id,
                status=ChangeSetEvaluationStatus.UNAVAILABLE,
                message=(
                    "No valid CHANGESET evidence was found."
                ),
            )

        try:
            parsed_sets = [
                (
                    cls._changes_from_evidence(item),
                    item.evidence_id,
                )
                for item in evidence
            ]

            # Current semantics use the first valid CHANGESET observation.
            # Multiple independent observations are a later aggregation concern.
            actual, first_id = parsed_sets[0]

            evidence_ids = tuple(
                evidence_id
                for _, evidence_id in parsed_sets
            )

            if parameters.mode is ChangeSetMode.CONSTRAINED:
                return cls._evaluate_constrained(
                    expected,
                    parameters,
                    actual,
                    evidence_ids,
                )

            if parameters.mode is ChangeSetMode.EXACT:
                return cls._evaluate_exact(
                    expected,
                    parameters,
                    actual,
                    evidence_ids,
                )

            return ChangeSetEvaluation(
                expected_id=expected.id,
                status=ChangeSetEvaluationStatus.ERROR,
                evidence_ids=evidence_ids,
                actual_changes=actual,
                message=(
                    f"Unsupported CHANGESET mode: "
                    f"{parameters.mode}"
                ),
            )

        except Exception as exc:
            return ChangeSetEvaluation(
                expected_id=expected.id,
                status=ChangeSetEvaluationStatus.ERROR,
                message=(
                    f"CHANGESET evidence could not be evaluated: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )