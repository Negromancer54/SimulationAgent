from __future__ import annotations

import pytest

from runtime.execution_plan import PlanStep
from runtime.v3_handlers import (
    FILE_WRITE_HANDLER_ID,
    file_write_handler,
    get_v3_handlers,
)


def make_step(
    parameters: dict,
) -> PlanStep:
    return PlanStep(
        step_id="file-write-test",
        handler_id=FILE_WRITE_HANDLER_ID,
        target_kind="PROJECT",
        target_identifier="simulation_zero",
        goal_identifier="file.write",
        goal_version=1,
        parameters=parameters,
    )


def test_file_write_handler_passes_parameters_to_write_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_write_file(
        relative_path: str,
        content: str,
    ) -> bool:
        captured["path"] = relative_path
        captured["content"] = content
        return True

    monkeypatch.setattr(
        "runtime.v3_handlers.write_file",
        fake_write_file,
    )

    file_write_handler(
        make_step(
            {
                "path": "src/example.cpp",
                "content": "hello",
            }
        )
    )

    assert captured == {
        "path": "src/example.cpp",
        "content": "hello",
    }


def test_file_write_handler_converts_false_to_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "runtime.v3_handlers.write_file",
        lambda relative_path, content: False,
    )

    with pytest.raises(RuntimeError):
        file_write_handler(
            make_step(
                {
                    "path": "src/example.cpp",
                    "content": "hello",
                }
            )
        )


def test_get_v3_handlers_contains_file_write_handler() -> None:
    handlers = get_v3_handlers()

    assert handlers[FILE_WRITE_HANDLER_ID] is file_write_handler