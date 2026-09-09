from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_task_v3 import TargetKind, TaskTarget


class TargetAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class TargetDirectoryError(ValueError):
    pass


@dataclass(frozen=True)
class TargetRecord:
    kind: TargetKind
    identifier: str
    scope: str
    availability: TargetAvailability = TargetAvailability.AVAILABLE


class TargetDirectory:
    """
    Minimal runtime directory for addressable targets.

    The directory answers only:
        "Does this exact target address exist?"

    It does not:
        - search arbitrary text;
        - parse source files;
        - inspect the filesystem;
        - resolve symbols dynamically;
        - execute targets.
    """

    def __init__(self) -> None:
        self._records: dict[tuple[TargetKind, str, str], TargetRecord] = {}

    @staticmethod
    def _key(
        kind: TargetKind,
        identifier: str,
        scope: str,
    ) -> tuple[TargetKind, str, str]:
        return (kind, identifier, scope)

    @staticmethod
    def _validate_record(record: TargetRecord) -> None:
        if not isinstance(record, TargetRecord):
            raise TargetDirectoryError(
                "TargetDirectory accepts only TargetRecord instances."
            )

        if not isinstance(record.kind, TargetKind):
            raise TargetDirectoryError(
                "TargetRecord.kind must be a TargetKind."
            )

        if (
            not isinstance(record.identifier, str)
            or not record.identifier.strip()
        ):
            raise TargetDirectoryError(
                "TargetRecord.identifier must be a non-empty string."
            )

        if (
            not isinstance(record.scope, str)
            or not record.scope.strip()
        ):
            raise TargetDirectoryError(
                "TargetRecord.scope must be a non-empty string."
            )

        if not isinstance(
            record.availability,
            TargetAvailability,
        ):
            raise TargetDirectoryError(
                "TargetRecord.availability must be a "
                "TargetAvailability."
            )

    def register(self, record: TargetRecord) -> None:
        self._validate_record(record)

        key = self._key(
            record.kind,
            record.identifier,
            record.scope,
        )

        if key in self._records:
            raise TargetDirectoryError(
                "TargetRecord is already registered: "
                f"{record.kind.value}:{record.identifier}"
                f"@{record.scope}"
            )

        self._records[key] = record

    def contains(self, target: TaskTarget) -> bool:
        key = self._key(
            target.kind,
            target.identifier,
            self._scope_value(target),
        )

        return key in self._records

    def resolve_candidates(
        self,
        target: TaskTarget,
    ) -> list[TargetRecord]:
        """
        Return all exact-address candidates.

        Multiple candidates are possible because a future directory
        implementation may contain more than one matching runtime
        representation.
        """
        candidates: list[TargetRecord] = []

        key = self._key(
            target.kind,
            target.identifier,
            self._scope_value(target),
        )

        record = self._records.get(key)

        if record is not None:
            candidates.append(record)

        return candidates

    @staticmethod
    def _scope_value(target: TaskTarget) -> str:
        scope = target.scope

        if target.kind is TargetKind.PROJECT:
            if scope.project is not None:
                return scope.project
            return "project"

        if target.kind is TargetKind.FILE:
            if scope.path is not None:
                return scope.path
            return "path"

        if target.kind in (
            TargetKind.SYMBOL,
            TargetKind.SUBSYSTEM,
            TargetKind.TEST,
        ):
            if scope.namespace is not None:
                return scope.namespace
            return "namespace"

        raise TargetDirectoryError(
            f"Unsupported TargetKind: {target.kind}"
        )

    def set_availability(
        self,
        kind: TargetKind,
        identifier: str,
        scope: str,
        availability: TargetAvailability,
    ) -> None:
        key = self._key(kind, identifier, scope)

        record = self._records.get(key)

        if record is None:
            raise KeyError(
                f"Unknown target: "
                f"{kind.value}:{identifier}@{scope}"
            )

        self._records[key] = TargetRecord(
            kind=record.kind,
            identifier=record.identifier,
            scope=record.scope,
            availability=availability,
        )