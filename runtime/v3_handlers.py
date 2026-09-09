from __future__ import annotations

from agent import write_file
from runtime.execution_plan import PlanStep


FILE_WRITE_HANDLER_ID = "file.write.handler"


def file_write_handler(step: PlanStep) -> None:
    """
    Production V3 handler for writing a UTF-8 text file.

    The project root and filesystem safety checks remain owned by
    the existing legacy write_file() primitive.
    """

    if not isinstance(step, PlanStep):
        raise TypeError(
            "file_write_handler requires a PlanStep."
        )

    parameters = step.parameters

    if not isinstance(parameters, dict):
        raise TypeError(
            "file.write requires object parameters."
        )

    path = parameters.get("path")
    content = parameters.get("content")

    if not isinstance(path, str) or not path.strip():
        raise ValueError(
            "file.write requires a non-empty string parameter 'path'."
        )

    if not isinstance(content, str):
        raise TypeError(
            "file.write requires a string parameter 'content'."
        )

    if not write_file(path, content):
        raise RuntimeError(
            f"file.write failed for '{path}'."
        )


def get_v3_handlers() -> dict[str, object]:
    """
    Return the production V3 runtime handler map.
    """

    return {
        FILE_WRITE_HANDLER_ID: file_write_handler,
    }