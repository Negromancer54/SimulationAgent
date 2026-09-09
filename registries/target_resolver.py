from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_task_v3 import TaskTarget
from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
    TargetAvailability,
)


class TargetResolverStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class TargetResolution:
    status: TargetResolverStatus
    target: TaskTarget
    record: TargetRecord | None = None
    candidates: tuple[TargetRecord, ...] = ()
    message: str = ""

    @property
    def resolved(self) -> bool:
        return self.status is TargetResolverStatus.RESOLVED


class TargetResolver:
    """
    Resolves an already-addressed TaskTarget against TargetDirectory.

    No fuzzy search or discovery is performed here.
    """

    def __init__(self, directory: TargetDirectory) -> None:
        self._directory = directory

    @staticmethod
    def _validate_target(target: TaskTarget) -> str | None:
        if not isinstance(target, TaskTarget):
            return (
                "TargetResolver accepts only TaskTarget instances."
            )

        if (
            not isinstance(target.identifier, str)
            or not target.identifier.strip()
        ):
            return (
                "TaskTarget.identifier must be a "
                "non-empty string."
            )

        if target.scope is None:
            return "TaskTarget.scope must be present."

        return None

    def resolve(
        self,
        target: TaskTarget,
    ) -> TargetResolution:
        validation_error = self._validate_target(target)

        if validation_error is not None:
            return TargetResolution(
                status=TargetResolverStatus.INVALID,
                target=target,
                message=validation_error,
            )

        candidates = self._directory.resolve_candidates(target)

        if not candidates:
            return TargetResolution(
                status=TargetResolverStatus.NOT_FOUND,
                target=target,
                message=(
                    f"Target '{target.identifier}' "
                    "was not found."
                ),
            )

        if len(candidates) > 1:
            return TargetResolution(
                status=TargetResolverStatus.AMBIGUOUS,
                target=target,
                candidates=tuple(candidates),
                message=(
                    f"Target '{target.identifier}' "
                    "resolved to multiple candidates."
                ),
            )

        record = candidates[0]

        if record.availability is TargetAvailability.UNAVAILABLE:
            return TargetResolution(
                status=TargetResolverStatus.UNAVAILABLE,
                target=target,
                record=record,
                candidates=(record,),
                message=(
                    f"Target '{target.identifier}' "
                    "exists but is unavailable."
                ),
            )

        return TargetResolution(
            status=TargetResolverStatus.RESOLVED,
            target=target,
            record=record,
            candidates=(record,),
            message="",
        )