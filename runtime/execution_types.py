from __future__ import annotations

from enum import Enum


class ExecutionStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"