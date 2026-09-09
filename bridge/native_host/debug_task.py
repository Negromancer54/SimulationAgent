import contextlib
import io
import sys
from pathlib import Path

AGENT_ROOT = Path(r"C:\Users\Gycha\SimulationAgent")

if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import contextlib
import io

import agent
import agent


task = agent.Task(
    task_id="BRIDGE-TXN-DEBUG",
    description="Debug native host task execution.",
    edits=[
        {
            "type": "create",
            "path": "bridge_task_probe.txt",
            "content": "Bridge transactional test file.\n",
        }
    ],
    expected_paths=[
        "bridge_task_probe_expected.txt"
    ],
)

diagnostics = io.StringIO()

print("BEFORE run_task")

with contextlib.redirect_stdout(diagnostics):
    result = agent.run_task(task)

print("AFTER run_task")
print()
print("RESULT:")
print(result)
print()
print("DIAGNOSTICS:")
print(diagnostics.getvalue())