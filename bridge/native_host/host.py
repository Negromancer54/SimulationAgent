import contextlib
import io
import json
import struct
import sys
from pathlib import Path


AGENT_ROOT = Path(r"C:\Users\Gycha\SimulationAgent")
LOG_FILE = Path(
    r"C:\Users\Gycha\SimulationAgent\bridge\native_host\host_debug.log"
)


def debug_log(message):
    with LOG_FILE.open(
        "a",
        encoding="utf-8"
    ) as log:
        log.write(message + "\n")
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import agent


def read_message():
    raw_length = sys.stdin.buffer.read(4)

    if len(raw_length) != 4:
        return None

    message_length = struct.unpack("<I", raw_length)[0]

    raw_message = sys.stdin.buffer.read(message_length)

    if len(raw_message) != message_length:
        return None

    return json.loads(raw_message.decode("utf-8"))


def send_message(message):
    encoded = json.dumps(
        message,
        ensure_ascii=False
    ).encode("utf-8")

    sys.stdout.buffer.write(
        struct.pack("<I", len(encoded))
    )

    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def handle_agent_test():
    return {
        "type": "agent_test_response",
        "success": True,
        "message": "SimulationAgent imported successfully"
    }


def handle_task(message):
    debug_log("handle_task: ENTER")

    task_data = message.get("task")

    debug_log(
        f"handle_task: task_data type={type(task_data).__name__}"
    )

    if not isinstance(task_data, dict):
        return {
            "type": "task_result",
            "success": False,
            "failure_code": "INVALID_TASK_MESSAGE",
            "failure_message": "Missing or invalid task object."
        }

    try:
        task = agent.Task(
            task_id=task_data.get("task_id", ""),
            description=task_data.get("description", ""),
            edits=task_data.get("edits", []),
            expected_paths=task_data.get("expected_paths", [])
        )

        diagnostics = io.StringIO()

        debug_log("handle_task: BEFORE run_task")

        with contextlib.redirect_stdout(diagnostics):
            result = agent.run_task(task)

        debug_log(
            f"handle_task: AFTER run_task "
            f"success={result.success} "
            f"stage={result.stage}"
        )

        debug_log("handle_task: BEFORE task_result_to_dict")

        result_data = agent.task_result_to_dict(result)

        debug_log("handle_task: AFTER task_result_to_dict")

        result_data["diagnostics_stdout"] = (
            result_data.get("diagnostics_stdout", "")
            + diagnostics.getvalue()
        )
        debug_log("handle_task: RETURN task_result")

        return {
            "type": "task_result",
            "task_id": task.task_id,
            "result": result_data
        }

    except Exception as exc:
        return {
            "type": "task_result",
            "success": False,
            "failure_code": "HOST_AGENT_EXCEPTION",
            "failure_message": str(exc)
        }


def main():
    while True:
        message = read_message()

        if message is None:
            break

        message_type = message.get("type")
        debug_log(
            f"main: RECEIVED message_type={message_type}"
        )
        if message_type == "ping":
            send_message({
                "type": "pong",
                "message": "SimulationAgent Bridge native host is alive"
            })

        elif message_type == "agent_test":
            send_message(handle_agent_test())

        elif message_type == "task":
            send_message(handle_task(message))

        else:
            send_message({
                "type": "error",
                "message": "Unknown message type"
            })


if __name__ == "__main__":
    main()