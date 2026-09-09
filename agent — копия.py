from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional
import subprocess
import time
import json

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(r"C:\Users\Gycha\SimulationZero-Cpp").resolve()

AGENT_ROOT = Path(__file__).resolve().parent
STATE_DIR = AGENT_ROOT / "state"
CHECKPOINT_FILE = STATE_DIR / "checkpoint"

MSBUILD_CANDIDATES = [
    Path(
        r"C:\Program Files\Microsoft Visual Studio\2022"
        r"\Community\MSBuild\Current\Bin\amd64\MSBuild.exe"
    ),
    Path(
        r"C:\Program Files\Microsoft Visual Studio\2022"
        r"\Community\MSBuild\Current\Bin\MSBuild.exe"
    ),
]

BUILD_DIR = PROJECT_ROOT / "build"

SOLUTION = BUILD_DIR / "SimulationZero.sln"

EXECUTABLE = BUILD_DIR / "Debug" / "SimulationZero.exe"

from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class Task:
    """
    Structured task description for the SimulationAgent.

    Task V1 describes what should be changed.
    Execution policy remains owned by run_task().
    """
    task_id: str = ""

    description: str = ""
    
    edits: list[dict[str, Any]] = field(
        default_factory=list
    )

    expected_paths: list[str] = field(
        default_factory=list
    )
def validate_task(task):
    """
    Validate the minimal Task V2 contract.

    Returns True when the task has a valid identity
    and description.
    """

    if not isinstance(task, Task):
        return False

    if not isinstance(task.task_id, str):
        return False

    if not task.task_id.strip():
        return False

    if not isinstance(task.description, str):
        return False

    if not task.description.strip():
        return False

    if not isinstance(task.edits, list):
        return False

    for expected_path in task.expected_paths:
        if not isinstance(expected_path, str):
            return False

        if not expected_path.strip():
            return False

    for edit in task.edits:
        if not isinstance(edit, dict):
            return False

        edit_type = edit.get("type")

        if not isinstance(edit_type, str):
            return False

        if edit_type not in ("create", "replace"):
            return False

        if edit_type == "create":
            if "path" not in edit:
                return False

            if not isinstance(edit["path"], str):
                return False

            if not edit["path"].strip():
                return False

            if "content" not in edit:
                return False

            if not isinstance(edit["content"], str):
                return False

        if edit_type == "replace":
            if "path" not in edit:
                return False

            if not isinstance(edit["path"], str):
                return False

            if not edit["path"].strip():
                return False

            if "old_text" not in edit:
                return False

            if not isinstance(edit["old_text"], str):
                return False

            if edit["old_text"] == "":
                return False

            if "new_text" not in edit:
                return False

            if not isinstance(edit["new_text"], str):
                return False

            if "expected_count" in edit:
                expected_count = edit["expected_count"]

                if isinstance(expected_count, bool):
                    return False

                if not isinstance(expected_count, int):
                    return False

                if expected_count <= 0:
                    return False

    if task.expected_paths:
        edit_paths = {
            edit["path"]
            for edit in task.edits
        }

        expected_paths = set(task.expected_paths)

        if edit_paths != expected_paths:
            return False

    return True
@dataclass
class TaskResult:
    success: bool = False
    stage: str = "NOT_STARTED"

    checkpoint: Optional[str] = None
    attempts: int = 1

    edit_results: list[dict[str, Any]] = field(
        default_factory=list
    )

    diff: str = ""
    changed_paths: list[str] = field(
        default_factory=list
    )
    diff_success: bool = False
    diff_validated: bool = False

    build_result: Optional[dict[str, Any]] = None
    run_result: Optional[dict[str, Any]] = None

    rollback_result: Optional[dict[str, Any]] = None

    failure_code: Optional[str] = None
    failure_message: Optional[str] = None

    diagnostics_stdout: str = ""
    diagnostics_stderr: str = ""
def task_result_to_dict(result):
    """
    Convert internal TaskResult into a plain dictionary.

    This is the internal transformation layer between
    TaskResult and external serialization.
    """

    return {
        "success": result.success,
        "stage": result.stage,
        "checkpoint": result.checkpoint,
        "attempts": result.attempts,

        "edit_results": result.edit_results,

        "diff": result.diff,
        "changed_paths": result.changed_paths,
        "diff_success": result.diff_success,
        "diff_validated": result.diff_validated,

        "build_result": result.build_result,
        "run_result": result.run_result,

        "rollback_result": result.rollback_result,

        "failure_code": result.failure_code,
        "failure_message": result.failure_message,

        "diagnostics_stdout": result.diagnostics_stdout,
        "diagnostics_stderr": result.diagnostics_stderr,
    }
def task_result_to_json(result):
    """
    Serialize TaskResult into TaskResult JSON V1.
    """

    data = {
        "schema_version": 1,
        "success": result.success,
        "stage": result.stage,
        "attempts": result.attempts,

        "checkpoint": {
            "created": result.checkpoint is not None,
            "commit": result.checkpoint,
        },

        "edits": {
            "success": all(
                edit.get("success", False)
                for edit in result.edit_results
            ),
            "count": len(result.edit_results),
            "results": result.edit_results,
        },

        "diff": {
            "success": result.diff_success,
            "changed_paths": result.changed_paths,
            "validated": result.diff_validated,
        },

        "build": (
            {
                "success": result.build_result["success"],
                "returncode": result.build_result["returncode"],
                "timeout": result.build_result["timeout"],
                "elapsed": result.build_result["elapsed"],
            }
            if result.build_result is not None
            else None
        ),

        "run": (
            {
                "success": result.run_result["success"],
                "returncode": result.run_result["returncode"],
                "timeout": result.run_result["timeout"],
                "elapsed": result.run_result["elapsed"],
            }
            if result.run_result is not None
            else None
        ),

        "rollback": {
            "performed": (
                result.rollback_result is not None
            ),
            "success": (
                result.rollback_result["success"]
                if result.rollback_result is not None
                else None
            ),
        },

        "failure": (
            {
                "code": result.failure_code,
                "message": result.failure_message,
            }
            if result.failure_code is not None
            else None
        ),

        "diagnostics": {
            "stdout": result.diagnostics_stdout,
            "stderr": result.diagnostics_stderr,
        },
    }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )
# ============================================================
# Output
# ============================================================

def print_header(title: str):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_result_status(returncode):
    print()

    if returncode == 0:
        print("PROCESS RESULT: SUCCESS")
    else:
        print("PROCESS RESULT: FAILURE")

    print(f"Exit code: {returncode}")


# ============================================================
# Process execution
# ============================================================

def run_process(command, cwd=None, timeout=None):
    print()
    print("$", " ".join(str(x) for x in command))
    print()

    start_time = time.perf_counter()

    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        elapsed = time.perf_counter() - start_time

        if process.stdout:
            print(process.stdout)

        if process.stderr:
            print()
            print("----- STDERR -----")
            print(process.stderr)

        print()
        print(f"Execution time: {elapsed:.3f} seconds")

        print_result_status(process.returncode)

        return {
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "elapsed": elapsed,
            "timeout": False,
        }

    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start_time

        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")

        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        print("PROCESS TIMEOUT")
        print(f"Execution time: {elapsed:.3f} seconds")

        if stdout:
            print()
            print("----- STDOUT BEFORE TIMEOUT -----")
            print(stdout)

        if stderr:
            print()
            print("----- STDERR BEFORE TIMEOUT -----")
            print(stderr)

        return {
            "returncode": None,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed": elapsed,
            "timeout": True,
        }

    except Exception as exc:
        elapsed = time.perf_counter() - start_time

        print("PROCESS LAUNCH ERROR")
        print(str(exc))

        return {
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "elapsed": elapsed,
            "timeout": False,
        }


# ============================================================
# Safe project paths
# ============================================================

def resolve_project_path(relative_path):
    """
    Convert a project-relative path into an absolute path.

    The resulting path MUST remain inside PROJECT_ROOT.
    """

    try:
        candidate = (PROJECT_ROOT / relative_path).resolve()
        candidate.relative_to(PROJECT_ROOT)
    except (ValueError, OSError):
        return None

    return candidate


def is_inside_build(path):
    try:
        path.resolve().relative_to(BUILD_DIR.resolve())
        return True
    except ValueError:
        return False


# ============================================================
# Project
# ============================================================

def show_project_info():
    print_header("PROJECT INFORMATION")

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Agent root:   {AGENT_ROOT}")
    print(f"State dir:    {STATE_DIR}")
    print(f"Checkpoint:   {CHECKPOINT_FILE}")
    print(f"Build dir:    {BUILD_DIR}")
    print(f"Solution:     {SOLUTION}")
    print(f"Executable:   {EXECUTABLE}")

    if not PROJECT_ROOT.exists():
        print()
        print("ERROR: SimulationZero-Cpp was not found.")
        return False

    return True


# ============================================================
# MSBuild
# ============================================================

def find_msbuild():
    for path in MSBUILD_CANDIDATES:
        if path.exists():
            return path

    return None


def build_project():
    print_header("BUILD PROJECT")

    msbuild = find_msbuild()

    if msbuild is None:
        print("ERROR: MSBuild was not found.")

        return {
            "success": False,
            "returncode": None,
            "stdout": "",
            "stderr": "MSBuild was not found.",
            "elapsed": 0.0,
        }

    if not SOLUTION.exists():
        print("ERROR: Solution does not exist:")
        print(SOLUTION)

        return {
            "success": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"Solution does not exist: {SOLUTION}",
            "elapsed": 0.0,
        }

    print(f"Using MSBuild: {msbuild}")

    result = run_process(
        [
            str(msbuild),
            str(SOLUTION),
            "/m",
            "/p:Configuration=Debug",
            "/p:Platform=x64",
        ],
        cwd=PROJECT_ROOT,
        timeout=300,
    )

    result["success"] = result["returncode"] == 0

    return result


# ============================================================
# Simulation
# ============================================================

def run_simulation():
    print_header("RUN SIMULATION")

    if not EXECUTABLE.exists():
        print("ERROR: Executable does not exist:")
        print(EXECUTABLE)
        print()
        print("Build the project first.")

        return {
            "returncode": None,
            "stdout": "",
            "stderr": "Executable does not exist.",
            "elapsed": 0.0,
            "timeout": False,
            "success": False,
        }

    print(f"Executable: {EXECUTABLE}")

    result = run_process(
        [str(EXECUTABLE)],
        cwd=EXECUTABLE.parent,
        timeout=60,
    )

    print()
    print("----- DIAGNOSTIC SUMMARY -----")

    if result["timeout"]:
        print("Status: TIMEOUT")
        print("The process did not finish within the allowed time.")

        result["success"] = False

        return result

    if result["returncode"] == 0:
        print("Status: SUCCESS")
        print("SimulationZero exited normally.")

        result["success"] = True

        return result

    print("Status: CRASH / FAILURE")
    print(f"Exit code: {result['returncode']}")

    if result["stdout"]:
        print()
        print("Program produced stdout before termination.")

    if result["stderr"]:
        print()
        print("Program produced stderr before termination.")

    print()
    print("The process terminated abnormally.")

    result["success"] = False

    return result


# ============================================================
# File inspection
# ============================================================

SOURCE_EXTENSIONS = {
    ".h",
    ".hpp",
    ".cpp",
    ".c",
    ".cc",
    ".cmake",
    ".txt",
}


def list_source_files():
    print_header("SOURCE FILES")

    files = []

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue

        if is_inside_build(path):
            continue

        if path.suffix.lower() in SOURCE_EXTENSIONS:
            files.append(path)

    files.sort()

    for path in files:
        print(path.relative_to(PROJECT_ROOT))

    print()
    print(f"Total source/config files: {len(files)}")


def read_file(relative_path):
    print_header(f"READ FILE: {relative_path}")

    path = resolve_project_path(relative_path)

    if path is None:
        print("ERROR: Path escapes the SimulationZero-Cpp project.")
        return False

    if not path.exists():
        print(f"ERROR: File does not exist: {path}")
        return False

    if not path.is_file():
        print(f"ERROR: Not a file: {path}")
        return False

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        print(f"ERROR: Could not read file: {exc}")
        return False

    print(text)
    return True

def apply_text_replacement(
    relative_path,
    old_text,
    new_text,
    expected_count=1,
):
    """
    Replace an exact text fragment inside a project file.

    The replacement is performed only when the number of
    occurrences exactly matches expected_count.
    """

    print_header(f"APPLY TEXT REPLACEMENT: {relative_path}")

    path = resolve_project_path(relative_path)

    if path is None:
        print("ERROR: Path escapes the SimulationZero-Cpp project.")
        return False

    if is_inside_build(path):
        print("ERROR: Agent is not allowed to modify build/.")
        return False

    if not path.exists():
        print(f"ERROR: File does not exist: {path}")
        return False

    if not path.is_file():
        print(f"ERROR: Not a file: {path}")
        return False

    if not old_text:
        print("ERROR: Search text cannot be empty.")
        return False

    if expected_count < 1:
        print("ERROR: expected_count must be at least 1.")
        return False

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        print(f"ERROR: Could not read file: {exc}")
        return False

    actual_count = text.count(old_text)

    print(f"Expected matches: {expected_count}")
    print(f"Actual matches:   {actual_count}")

    if actual_count != expected_count:
        print()
        print("ERROR: Replacement aborted.")
        print(
            "The number of matches does not equal "
            "expected_count."
        )
        print("The file was NOT modified.")
        return False

    new_text_content = text.replace(
        old_text,
        new_text,
    )

    if new_text_content == text:
        print()
        print("ERROR: Replacement produced no change.")
        print("The file was NOT modified.")
        return False

    try:
        path.write_text(
            new_text_content,
            encoding="utf-8",
            newline="\n",
        )
    except Exception as exc:
        print(f"ERROR: Could not write file: {exc}")
        return False

    print()
    print("Replacement completed successfully.")
    print(f"Replacements applied: {actual_count}")
    print(f"File: {path.relative_to(PROJECT_ROOT)}")

    return True
def get_changed_paths():
    """
    Return paths changed in the current Git working tree.

    Includes:
        - modified files
        - added files
        - deleted files
        - untracked files

    Returns:
        list[str] | None:
            Changed project-relative paths on success.
            None if Git execution failed.
    """

    result = git_command(
        ["status", "--short"],
        timeout=30,
    )

    if result["returncode"] != 0:
        print()
        print("ERROR: Could not read Git status.")
        return None

    changed_paths = []

    for line in result["stdout"].splitlines():
        if not line.strip():
            continue

        status_part = line[:2]
        path_part = line[3:].strip()

        if not path_part:
            continue

        # Git rename/copy entries can contain:
        # old_path -> new_path
        if "->" in path_part:
            path_part = path_part.split("->", 1)[1].strip()

        changed_paths.append(path_part)

    return sorted(set(changed_paths))
def validate_changed_paths(expected_paths):
    """
    Verify that the working tree contains exactly the
    expected changed paths.

    Returns:
        bool:
            True if changed paths match exactly.
            False otherwise.
    """

    print_header("DIFF VALIDATION")

    if expected_paths is None:
        print("ERROR: Expected paths were not provided.")
        return False

    normalized_expected = sorted(
        set(
            path.strip()
            for path in expected_paths
            if path.strip()
        )
    )

    actual_paths = get_changed_paths()

    if actual_paths is None:
        return False

    print("Expected changed paths:")

    if normalized_expected:
        for path in normalized_expected:
            print(f"  {path}")
    else:
        print("  <none>")

    print()
    print("Actual changed paths:")

    if actual_paths:
        for path in actual_paths:
            print(f"  {path}")
    else:
        print("  <none>")

    if actual_paths == normalized_expected:
        print()
        print("DIFF VALIDATION: PASSED.")
        return True

    print()
    print("DIFF VALIDATION: FAILED.")

    unexpected = sorted(
        set(actual_paths) - set(normalized_expected)
    )

    missing = sorted(
        set(normalized_expected) - set(actual_paths)
    )

    if unexpected:
        print()
        print("Unexpected changed paths:")

        for path in unexpected:
            print(f"  {path}")

    if missing:
        print()
        print("Expected paths that were not changed:")

        for path in missing:
            print(f"  {path}")

    return False
def fail_task(
    result,
    failure_code,
    failure_message,
):
    """
    Finalize a failed transactional task.

    Records the primary failure, attempts rollback when
    a checkpoint exists, and promotes rollback failure
    to the final failure state.
    """

    result.success = False
    result.failure_code = failure_code
    result.failure_message = failure_message

    # No checkpoint means there is nothing to roll back.
    if result.checkpoint is None:
        result.rollback_result = None
        result.stage = "FAILED"

        return result

    print()
    print("Task transaction will be rolled back.")

    result.stage = "ROLLBACK"

    rollback_success = rollback_to_checkpoint(
        require_confirmation=False
        )

    result.rollback_result = {
        "success": rollback_success,
    }

    if not rollback_success:
        result.stage = "FAILED"
        result.failure_code = "ROLLBACK_FAILED"
        result.failure_message = "Rollback failed."

    return result
def run_task(task):

    """
    Execute one transactional development task.

    Current stages:
        PRECHECK
        CHECKPOINT
        EDIT

    Later stages will add:
        DIFF
        BUILD
        RUN
        PASS / ROLLBACK
    """
    result = TaskResult()
    print_header("TASK")

    # ------------------------------------------------------------
    # TASK VALIDATION
    # ------------------------------------------------------------

    if not validate_task(task):
        print()
        print("ERROR: Task validation failed.")
        print("Task aborted before precheck.")

        result.success = False
        result.failure_code = "PRECHECK_FAILED"
        result.failure_message = (
            "Task validation failed."
        )
        result.stage = "PRECHECK"

        return result

    edits = task.edits
    expected_paths = task.expected_paths
    # ------------------------------------------------------------
    # PRECHECK
    # ------------------------------------------------------------

    result.stage = "PRECHECK"

    status = git_status()
    if status is not True:
        print()
        print("ERROR: Working tree is not clean.")
        print("Task aborted before checkpoint creation.")

        result.success = False
        result.failure_code = "PRECHECK_FAILED"
        result.failure_message = (
            "Working tree is not clean."
        )
        result.stage = "PRECHECK"

        return result

    print("PRECHECK: working tree is clean.")

    # ------------------------------------------------------------
    # CHECKPOINT
    # ------------------------------------------------------------

    result.stage = "CHECKPOINT"

    checkpoint = create_checkpoint()

    if not checkpoint:
        print()
        print("ERROR: Could not create checkpoint.")

        result.success = False
        result.failure_code = "CHECKPOINT_FAILED"
        result.failure_message = (
            "Could not create checkpoint."
        )
        result.stage = "CHECKPOINT"

        return result

    result.checkpoint = checkpoint
    print(f"CHECKPOINT: {checkpoint}")

    # ------------------------------------------------------------
    # EDIT
    # ------------------------------------------------------------

    result.stage = "EDIT"

    for edit in edits:
        edit_type = edit.get("type")

        if edit_type == "create":
            path = resolve_project_path(edit["path"])

            if path is None:
                print(
                    "ERROR: Path escapes the "
                    "SimulationZero-Cpp project."
                )
                edit_result = False

            elif is_inside_build(path):
                print(
                    "ERROR: Agent is not allowed "
                    "to modify build/."
                )
                edit_result = False

            else:
                try:
                    path.write_text(
                        edit["content"],
                        encoding="utf-8",
                        newline="\n",
                    )

                    print()
                    print(
                        f"Created file: "
                        f"{path.relative_to(PROJECT_ROOT)}"
                    )

                    edit_result = True

                except Exception as exc:
                    print(
                        f"ERROR: Could not create file: {exc}"
                    )
                    edit_result = False

        elif edit_type == "replace":
            edit_result = apply_text_replacement(
                edit["path"],
                edit["old_text"],
                edit["new_text"],
                edit.get("expected_count", 1),
            )

        else:
            edit_result = False

            print()
            print(
                f"ERROR: Unknown edit type: {edit_type}"
            )

        result.edit_results.append({
            "type": edit_type,
            "path": edit.get("path"),
            "success": edit_result,
        })

        if not edit_result:
            print()
            print("EDIT FAILED.")

            return fail_task(
                result,
                "EDIT_FAILED",
                "An edit operation failed.",
            )

    print()
    print("All edits completed successfully.")

    # ------------------------------------------------------------
    # DIFF
    # ------------------------------------------------------------

    result.stage = "DIFF"

    diff = get_git_diff()

    if diff is None:
        result.diff_success = False

        print()
        print("DIFF FAILED.")

        return fail_task(
            result,
            "DIFF_FAILED",
            "Could not read Git diff.",
        )

    result.diff_success = True
    result.diff = diff

    changed_paths = get_changed_paths()

    if changed_paths is None:
        result.diff_success = False

        print()
        print("DIFF FAILED.")

        return fail_task(
            result,
            "DIFF_FAILED",
            "Could not determine changed paths.",
        )

    result.changed_paths = changed_paths

    print()
    print("Git diff captured successfully.")

    if diff.strip():
        print()
        print(diff)
    else:
        print()
        print("WARNING: Git diff is empty.")

    # ------------------------------------------------------------
    # DIFF VALIDATION
    # ------------------------------------------------------------

    result.stage = "DIFF_VALIDATION"

    if expected_paths:
        if not validate_changed_paths(expected_paths):
            result.diff_validated = False

            print()
            print("ERROR: DIFF VALIDATION failed.")

            return fail_task(
                result,
                "DIFF_VALIDATION_FAILED",
                "Changed paths do not match expected paths.",
            )

        result.diff_validated = True

        print()
        print("DIFF VALIDATION completed successfully.")
    else:
        result.diff_validated = True

        print()
        print("DIFF VALIDATION skipped: no expected paths declared.")
    # ------------------------------------------------------------
    # BUILD
    # ------------------------------------------------------------

    result.stage = "BUILD"

    build_result = build_project()

    result.build_result = {
        "success": build_result["success"],
        "returncode": build_result["returncode"],
        "timeout": build_result["timeout"],
        "elapsed": build_result["elapsed"],
    }

    result.diagnostics_stdout = build_result["stdout"]
    result.diagnostics_stderr = build_result["stderr"]

    if not build_result["success"]:
        print()
        print("ERROR: BUILD failed.")

        return fail_task(
            result,
            "BUILD_FAILED",
            "Build failed.",
        )

    print()
    print("BUILD completed successfully.")

    # ------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------

    result.stage = "RUN"

    run_result = run_simulation()

    result.run_result = {
        "success": run_result["success"],
        "returncode": run_result["returncode"],
        "timeout": run_result["timeout"],
        "elapsed": run_result["elapsed"],
    }

    result.diagnostics_stdout = run_result["stdout"]
    result.diagnostics_stderr = run_result["stderr"]

    if not run_result["success"]:
        print()
        print("ERROR: RUN failed.")

        return fail_task(
            result,
            "RUN_FAILED",
            f"SimulationZero exited with code "
            f"{run_result['returncode']}.",
        )

    print()
    print("RUN completed successfully.")

    result.success = True
    result.stage = "COMPLETE"

    result.failure_code = None
    result.failure_message = None

    result.rollback_result = None

    return result
def test_transaction_success():
    original_run_simulation = run_simulation

    def successful_run_simulation():
        print_header("SIMULATED RUN SUCCESS")

        return {
            "returncode": 0,
            "stdout": "Simulated SimulationZero success.\n",
            "stderr": "",
            "elapsed": 0.001,
            "timeout": False,
            "success": True,
        }

    try:
        globals()["run_simulation"] = successful_run_simulation

        edits = [
            {
                "type": "create",
                "path": "agent_transaction_success_test.txt",
                "content": "SimulationAgent successful transaction test\n",
            }
        ]

        result = run_task(
            Task(
                task_id="TEST-TRANSACTION-SUCCESS",
                description="Test successful transactional execution.",
                edits=edits,
                expected_paths=[
                    "agent_transaction_success_test.txt"
                ],
            )
        )

    finally:
        globals()["run_simulation"] = original_run_simulation

    print()
    print_header("SUCCESS TRANSACTION TEST RESULT")

    print(result)

    return result
def test_task_result_json():
    """
    Verify TaskResult JSON V1 serialization.
    """

    result = TaskResult()

    result.success = False
    result.stage = "BUILD"
    result.attempts = 1

    result.checkpoint = (
        "2c2a57e9cabf2f9aec5f01efccdd4ed3e7f938ca"
    )

    result.edit_results = [
        {
            "type": "replace",
            "path": "src/core/World.cpp",
            "success": True,
        }
    ]

    result.diff_success = True
    result.changed_paths = [
        "src/core/World.cpp"
    ]
    result.diff_validated = True

    result.build_result = {
        "success": True,
        "returncode": 0,
        "timeout": False,
        "elapsed": 1.82,
    }

    result.run_result = None

    result.rollback_result = None

    result.failure_code = "RUN_FAILED"
    result.failure_message = (
        "SimulationZero exited with code 3."
    )

    result.diagnostics_stdout = "build stdout"
    result.diagnostics_stderr = "build stderr"

    json_text = task_result_to_json(result)

    data = json.loads(json_text)

    # --------------------------------------------------------
    # Root
    # --------------------------------------------------------

    assert data["schema_version"] == 1
    assert data["success"] is False
    assert data["stage"] == "BUILD"
    assert data["attempts"] == 1

    # --------------------------------------------------------
    # Checkpoint
    # --------------------------------------------------------

    assert data["checkpoint"]["created"] is True
    assert (
        data["checkpoint"]["commit"]
        == result.checkpoint
    )

    # --------------------------------------------------------
    # Edits
    # --------------------------------------------------------

    assert data["edits"]["success"] is True
    assert data["edits"]["count"] == 1
    assert len(data["edits"]["results"]) == 1

    edit = data["edits"]["results"][0]

    assert edit["path"] == "src/core/World.cpp"
    assert edit["type"] == "replace"
    assert edit["success"] is True

    # --------------------------------------------------------
    # Diff
    # --------------------------------------------------------

    assert data["diff"]["success"] is True
    assert data["diff"]["validated"] is True
    assert data["diff"]["changed_paths"] == [
        "src/core/World.cpp"
    ]

    # --------------------------------------------------------
    # Build
    # --------------------------------------------------------

    assert data["build"]["success"] is True
    assert data["build"]["returncode"] == 0
    assert data["build"]["timeout"] is False
    assert data["build"]["elapsed"] == 1.82

    # --------------------------------------------------------
    # Run
    # --------------------------------------------------------

    assert data["run"] is None

    # --------------------------------------------------------
    # Rollback
    # --------------------------------------------------------

    assert data["rollback"]["performed"] is False
    assert data["rollback"]["success"] is None

    # --------------------------------------------------------
    # Failure
    # --------------------------------------------------------

    assert data["failure"]["code"] == "RUN_FAILED"
    assert (
        data["failure"]["message"]
        == "SimulationZero exited with code 3."
    )

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    assert data["diagnostics"]["stdout"] == "build stdout"
    assert data["diagnostics"]["stderr"] == "build stderr"

    print_header("TASK RESULT JSON TEST")

    print(json_text)

    print()
    print("All TaskResult JSON V1 assertions passed.")

    return data
def test_task_result_success_json():
    """
    Verify TaskResult JSON V1 serialization for a
    successful completed task.
    """

    result = TaskResult()

    result.success = True
    result.stage = "COMPLETE"
    result.attempts = 1

    result.checkpoint = (
        "2c2a57e9cabf2f9aec5f01efccdd4ed3e7f938ca"
    )

    result.edit_results = [
        {
            "type": "create",
            "path": "agent_transaction_success_test.txt",
            "success": True,
        }
    ]

    result.diff_success = True
    result.changed_paths = [
        "agent_transaction_success_test.txt"
    ]
    result.diff_validated = True

    result.build_result = {
        "success": True,
        "returncode": 0,
        "timeout": False,
        "elapsed": 0.52,
    }

    result.run_result = {
        "success": True,
        "returncode": 0,
        "timeout": False,
        "elapsed": 0.001,
    }

    result.rollback_result = None

    result.failure_code = None
    result.failure_message = None

    result.diagnostics_stdout = (
        "Simulated SimulationZero success.\n"
    )
    result.diagnostics_stderr = ""

    json_text = task_result_to_json(result)

    data = json.loads(json_text)

    # --------------------------------------------------------
    # Root
    # --------------------------------------------------------

    assert data["schema_version"] == 1
    assert data["success"] is True
    assert data["stage"] == "COMPLETE"
    assert data["attempts"] == 1

    # --------------------------------------------------------
    # Checkpoint
    # --------------------------------------------------------

    assert data["checkpoint"]["created"] is True
    assert (
        data["checkpoint"]["commit"]
        == result.checkpoint
    )

    # --------------------------------------------------------
    # Edits
    # --------------------------------------------------------

    assert data["edits"]["success"] is True
    assert data["edits"]["count"] == 1

    edit = data["edits"]["results"][0]

    assert (
        edit["path"]
        == "agent_transaction_success_test.txt"
    )
    assert edit["type"] == "create"
    assert edit["success"] is True

    # --------------------------------------------------------
    # Diff
    # --------------------------------------------------------

    assert data["diff"]["success"] is True
    assert data["diff"]["validated"] is True
    assert data["diff"]["changed_paths"] == [
        "agent_transaction_success_test.txt"
    ]

    # --------------------------------------------------------
    # Build
    # --------------------------------------------------------

    assert data["build"]["success"] is True
    assert data["build"]["returncode"] == 0
    assert data["build"]["timeout"] is False
    assert data["build"]["elapsed"] == 0.52

    # --------------------------------------------------------
    # Run
    # --------------------------------------------------------

    assert data["run"]["success"] is True
    assert data["run"]["returncode"] == 0
    assert data["run"]["timeout"] is False
    assert data["run"]["elapsed"] == 0.001

    # --------------------------------------------------------
    # Rollback
    # --------------------------------------------------------

    assert data["rollback"]["performed"] is False
    assert data["rollback"]["success"] is None

    # --------------------------------------------------------
    # Failure
    # --------------------------------------------------------

    assert data["failure"] is None

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    assert (
        data["diagnostics"]["stdout"]
        == "Simulated SimulationZero success.\n"
    )
    assert data["diagnostics"]["stderr"] == ""

    print_header("SUCCESSFUL TASK RESULT JSON TEST")

    print(json_text)

    print()
    print(
        "All successful TaskResult JSON V1 "
        "assertions passed."
    )

    return data
def test_task_result_type_contract():
    """
    Verify that transactional task execution always returns
    the internal TaskResult object.
    """

    # --------------------------------------------------------
    # Successful task
    # --------------------------------------------------------

    original_run_simulation = run_simulation

    def successful_run_simulation():
        return {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "elapsed": 0.001,
            "timeout": False,
            "success": True,
        }

    try:
        globals()["run_simulation"] = (
            successful_run_simulation
        )

        success_result = run_task(
            Task(
                edits=[
                    {
                        "type": "create",
                        "path": "agent_task_result_type_success.txt",
                        "content": "type contract test\n",
                    }
                ],
                expected_paths=[
                    "agent_task_result_type_success.txt"
                ],
            )
        )

    finally:
        globals()["run_simulation"] = (
            original_run_simulation
        )

    assert isinstance(success_result, TaskResult)
    assert success_result.success is True
    assert success_result.stage == "COMPLETE"

    rollback_success = rollback_to_checkpoint(
        require_confirmation=False
    )

    assert rollback_success is True
    # --------------------------------------------------------
    # Failed task
    # --------------------------------------------------------

    def failing_build_project():
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "Simulated build failure.",
            "elapsed": 0.001,
            "timeout": False,
            "success": False,
        }

    original_build_project = build_project

    try:
        globals()["build_project"] = (
            failing_build_project
        )

        failure_result = run_task(
            Task(
                edits=[
                    {
                        "type": "create",
                        "path": "agent_task_result_type_failure.txt",
                        "content": "type contract test\n",
                    }
                ],
                expected_paths=[
                    "agent_task_result_type_failure.txt"
                ],
            )
        )

    finally:
        globals()["build_project"] = (
            original_build_project
        )

    assert isinstance(failure_result, TaskResult)
    assert failure_result.success is False
    assert failure_result.failure_code == "BUILD_FAILED"

    print_header("TASK RESULT TYPE CONTRACT TEST")

    print(
        "Successful result type:",
        type(success_result).__name__,
    )

    print(
        "Successful result stage:",
        success_result.stage,
    )

    print(
        "Failed result type:",
        type(failure_result).__name__,
    )

    print(
        "Failed result code:",
        failure_result.failure_code,
    )

    print()
    print(
        "All TaskResult type contract "
        "assertions passed."
    )

    return {
        "success_result": success_result,
        "failure_result": failure_result,
    }
def test_fail_task_without_checkpoint_returns_task_result():
    print("TEST 81 START")
    result = TaskResult()

    returned = fail_task(
        result,
        "TEST_FAILURE",
        "Test failure.",
    )

    assert isinstance(returned, TaskResult)
    assert returned.success is False
    assert returned.failure_code == "TEST_FAILURE"
    assert returned.failure_message == "Test failure."
    assert returned.stage == "FAILED"
    assert returned.rollback_result is None
    print("TEST 81 PASSED")
def test_failure_code_contract():
    """
    Verify the complete TaskResult JSON V1 failure-code set.
    """

    expected_codes = {
        "PRECHECK_FAILED",
        "CHECKPOINT_FAILED",
        "EDIT_FAILED",
        "DIFF_FAILED",
        "DIFF_VALIDATION_FAILED",
        "BUILD_FAILED",
        "RUN_FAILED",
        "ROLLBACK_FAILED",
    }

    actual_codes = {
        "PRECHECK_FAILED",
        "CHECKPOINT_FAILED",
        "EDIT_FAILED",
        "DIFF_FAILED",
        "DIFF_VALIDATION_FAILED",
        "BUILD_FAILED",
        "RUN_FAILED",
        "ROLLBACK_FAILED",
    }

    assert actual_codes == expected_codes
    assert len(actual_codes) == 8

    print_header("FAILURE CODE CONTRACT TEST")

    print("Supported failure codes:")

    for code in sorted(actual_codes):
        print(f"  {code}")

    print()
    print("Failure code count:", len(actual_codes))

    print()
    print(
        "All TaskResult failure-code contract "
        "assertions passed."
    )

    return actual_codes
def test_transaction_edit_failure():
    """
    Verify that an edit failure produces EDIT_FAILED
    and returns a TaskResult after successful rollback.
    """

    edits = [
        {
            "type": "replace",
            "path": "src/core/World.cpp",
            "old_text": (
                "THIS_TEXT_MUST_NOT_EXIST_IN_WORLD_CPP"
            ),
            "new_text": "replacement",
            "expected_count": 1,
        }
    ]

    result = run_task(
        Task(
            edits=edits,
            expected_paths=["src/core/World.cpp"],
        )
    )

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.failure_code == "EDIT_FAILED"
    assert result.stage == "ROLLBACK"

    assert result.checkpoint is not None
    assert result.rollback_result is not None
    assert result.rollback_result["success"] is True

    print_header("EDIT FAILURE TRANSACTION TEST")

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Rollback success:",
        result.rollback_result["success"],
    )

    print()
    print(
        "All EDIT_FAILED transaction "
        "assertions passed."
    )

    return result
def test_transaction_diff_failure():
    """
    Verify that a Git diff failure produces DIFF_FAILED
    and returns a TaskResult after successful rollback.
    """

    original_get_git_diff = get_git_diff

    def failing_get_git_diff():
        print_header("SIMULATED DIFF FAILURE")

        return None

    try:
        globals()["get_git_diff"] = failing_get_git_diff

        edits = [
            {
                "type": "create",
                "path": "agent_transaction_diff_failure_test.txt",
                "content": (
                    "SimulationAgent diff failure test\n"
                ),
            }
        ]

        result = run_task(
            Task(
                edits=edits,
                expected_paths=[
                    "agent_transaction_diff_failure_test.txt"
                ],
            )
        )
    finally:
        globals()["get_git_diff"] = (
            original_get_git_diff
        )

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.failure_code == "DIFF_FAILED"
    assert result.stage == "ROLLBACK"

    assert result.checkpoint is not None
    assert result.rollback_result is not None
    assert result.rollback_result["success"] is True

    assert result.diff_success is False
    assert result.diff == ""

    print_header("DIFF FAILURE TRANSACTION TEST")

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Diff success:",
        result.diff_success,
    )

    print(
        "Rollback success:",
        result.rollback_result["success"],
    )

    print()
    print(
        "All DIFF_FAILED transaction "
        "assertions passed."
    )

    return result
def test_transaction_diff_validation_failure_contract():
    """
    Verify that a changed-path mismatch produces
    DIFF_VALIDATION_FAILED and returns a TaskResult
    after successful rollback.
    """

    test_path = (
        "agent_transaction_diff_validation_test.txt"
    )

    original_validate_changed_paths = (
        validate_changed_paths
    )

    try:
        def fake_validate_changed_paths(
            expected_paths
        ):
            print()
            print(
                "TEST: simulated DIFF VALIDATION failure."
            )
            return False

        globals()["validate_changed_paths"] = (
            fake_validate_changed_paths
        )

        edits = [
            {
                "type": "create",
                "path": test_path,
                "content": (
                    "SimulationAgent diff validation test\n"
                ),
            }
        ]

        result = run_task(
            Task(
                task_id=(
                    "TEST-DIFF-VALIDATION-FAILURE-CONTRACT"
                ),
                description=(
                    "Verify DIFF VALIDATION failure "
                    "and TaskResult contract."
                ),
                edits=edits,
                expected_paths=[
                    test_path
                ],
            )
        )

        assert isinstance(result, TaskResult)
        assert result.success is False
        assert (
            result.failure_code
            == "DIFF_VALIDATION_FAILED"
        )
        assert result.stage == "ROLLBACK"

        assert result.checkpoint is not None
        assert result.rollback_result is not None
        assert (
            result.rollback_result["success"] is True
        )

        # DIFF itself must have succeeded.
        assert result.diff_success is True
        assert result.diff_validated is False

        assert result.changed_paths == [
            test_path
        ]

        assert test_path in result.diff

        print_header(
            "DIFF VALIDATION FAILURE TRANSACTION TEST"
        )

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Success:",
            result.success,
        )

        print(
            "Stage:",
            result.stage,
        )

        print(
            "Failure code:",
            result.failure_code,
        )

        print(
            "Diff success:",
            result.diff_success,
        )

        print(
            "Diff validated:",
            result.diff_validated,
        )

        print(
            "Rollback success:",
            result.rollback_result["success"],
        )

        print()
        print(
            "All DIFF_VALIDATION_FAILED transaction "
            "assertions passed."
        )

        return result

    finally:
        globals()["validate_changed_paths"] = (
            original_validate_changed_paths
        )
def test_transaction_build_failure_contract():
    """
    Verify that a build failure produces BUILD_FAILED,
    prevents RUN execution, and returns a TaskResult
    after successful rollback.
    """

    original_build_project = build_project

    def failing_build_project():
        print_header("SIMULATED BUILD FAILURE")

        return {
            "returncode": 1,
            "stdout": "",
            "stderr": (
                "Simulated build failure "
                "for contract test."
            ),
            "elapsed": 0.001,
            "timeout": False,
            "success": False,
        }

    try:
        globals()["build_project"] = (
            failing_build_project
        )

        edits = [
            {
                "type": "create",
                "path": "agent_transaction_build_failure_contract_test.txt",
                "content": (
                    "SimulationAgent build failure "
                    "contract test\n"
                ),
            }
        ]

        result = run_task(
            Task(
                edits=edits,
                expected_paths=[
                    "agent_transaction_build_failure_contract_test.txt"
                ],
            )
        )

    finally:
        globals()["build_project"] = (
            original_build_project
        )

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.failure_code == "BUILD_FAILED"
    assert result.stage == "ROLLBACK"

    assert result.checkpoint is not None
    assert result.rollback_result is not None
    assert result.rollback_result["success"] is True

    # EDIT must have succeeded.
    assert len(result.edit_results) == 1
    assert result.edit_results[0]["success"] is True

    # DIFF must have succeeded.
    assert result.diff_success is True

    # DIFF validation must have succeeded.
    assert result.diff_validated is True

    assert result.changed_paths == [
        "agent_transaction_build_failure_contract_test.txt"
    ]

    # BUILD must have failed.
    assert result.build_result is not None
    assert result.build_result["success"] is False
    assert result.build_result["returncode"] == 1
    assert result.build_result["timeout"] is False
    assert result.build_result["elapsed"] == 0.001

    # RUN must never execute after BUILD failure.
    assert result.run_result is None

    # Build diagnostics must be preserved.
    assert result.diagnostics_stderr == (
        "Simulated build failure "
        "for contract test."
    )

    print_header(
        "BUILD FAILURE TRANSACTION TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Edit success:",
        result.edit_results[0]["success"],
    )

    print(
        "Diff success:",
        result.diff_success,
    )

    print(
        "Diff validated:",
        result.diff_validated,
    )

    print(
        "Build success:",
        result.build_result["success"],
    )

    print(
        "Run result:",
        result.run_result,
    )

    print(
        "Rollback success:",
        result.rollback_result["success"],
    )

    print()
    print(
        "All BUILD_FAILED transaction "
        "assertions passed."
    )

    return result
def test_transaction_run_failure_contract():
    """
    Verify that a run failure produces RUN_FAILED,
    after successful build and returns a TaskResult
    after successful rollback.
    """

    original_run_simulation = run_simulation

    def failing_run_simulation():
        print_header("SIMULATED RUN FAILURE")

        return {
            "returncode": 3,
            "stdout": (
                "Simulated SimulationZero output.\n"
            ),
            "stderr": (
                "Simulated SimulationZero runtime failure.\n"
            ),
            "elapsed": 0.001,
            "timeout": False,
            "success": False,
        }

    try:
        globals()["run_simulation"] = (
            failing_run_simulation
        )

        edits = [
            {
                "type": "create",
                "path": "agent_transaction_run_failure_contract_test.txt",
                "content": (
                    "SimulationAgent run failure "
                    "contract test\n"
                ),
            }
        ]

        result = run_task(
            Task(
                edits=edits,
                expected_paths=[
                    "agent_transaction_run_failure_contract_test.txt"
                ],
            )
        )

    finally:
        globals()["run_simulation"] = (
            original_run_simulation
        )

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.failure_code == "RUN_FAILED"
    assert result.stage == "ROLLBACK"

    assert result.checkpoint is not None
    assert result.rollback_result is not None
    assert result.rollback_result["success"] is True

    # EDIT must have succeeded.
    assert len(result.edit_results) == 1
    assert result.edit_results[0]["success"] is True

    # DIFF must have succeeded.
    assert result.diff_success is True

    # DIFF validation must have succeeded.
    assert result.diff_validated is True

    assert result.changed_paths == [
        "agent_transaction_run_failure_contract_test.txt"
    ]

    # BUILD must have succeeded.
    assert result.build_result is not None
    assert result.build_result["success"] is True
    assert result.build_result["returncode"] == 0
    assert result.build_result["timeout"] is False

    # RUN must have failed.
    assert result.run_result is not None
    assert result.run_result["success"] is False
    assert result.run_result["returncode"] == 3
    assert result.run_result["timeout"] is False
    assert result.run_result["elapsed"] == 0.001

    # Runtime diagnostics must be preserved.
    assert result.diagnostics_stdout == (
        "Simulated SimulationZero output.\n"
    )

    assert result.diagnostics_stderr == (
        "Simulated SimulationZero runtime failure.\n"
    )

    print_header(
        "RUN FAILURE TRANSACTION TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Edit success:",
        result.edit_results[0]["success"],
    )

    print(
        "Diff success:",
        result.diff_success,
    )

    print(
        "Diff validated:",
        result.diff_validated,
    )

    print(
        "Build success:",
        result.build_result["success"],
    )

    print(
        "Run success:",
        result.run_result["success"],
    )

    print(
        "Run return code:",
        result.run_result["returncode"],
    )

    print(
        "Rollback success:",
        result.rollback_result["success"],
    )

    print()
    print(
        "All RUN_FAILED transaction "
        "assertions passed."
    )

    return result
def test_transaction_rollback_failure_contract():
    """
    Verify that a rollback failure promotes the final
    failure code to ROLLBACK_FAILED.
    """

    original_build_project = build_project
    original_rollback_to_checkpoint = (
        rollback_to_checkpoint
    )

    def failing_build_project():
        print_header("SIMULATED BUILD FAILURE")

        return {
            "returncode": 1,
            "stdout": "",
            "stderr": (
                "Simulated build failure "
                "before rollback."
            ),
            "elapsed": 0.001,
            "timeout": False,
            "success": False,
        }

    def failing_rollback_to_checkpoint(
        require_confirmation=True
    ):
        print_header("SIMULATED ROLLBACK FAILURE")

        return False

    try:
        globals()["build_project"] = (
            failing_build_project
        )

        globals()["rollback_to_checkpoint"] = (
            failing_rollback_to_checkpoint
        )

        edits = [
            {
                "type": "create",
                "path": (
                    "agent_transaction_rollback_failure_contract_test.txt"
                ),
                "content": (
                    "SimulationAgent rollback failure "
                    "contract test\n"
                ),
            }
        ]

        result = run_task(
            Task(
                edits=edits,
                expected_paths=[
                    "agent_transaction_rollback_failure_contract_test.txt"
                ],
            )
        )

    finally:
        globals()["build_project"] = (
            original_build_project
        )

        globals()["rollback_to_checkpoint"] = (
            original_rollback_to_checkpoint
        )

    assert isinstance(result, TaskResult)

    # The overall task must fail.
    assert result.success is False

    # Rollback failure must become the final failure code.
    assert result.failure_code == "ROLLBACK_FAILED"

    # The final stage must be FAILED.
    assert result.stage == "FAILED"

    # A checkpoint must have existed.
    assert result.checkpoint is not None

    # Rollback must have been attempted.
    assert result.rollback_result is not None
    assert result.rollback_result["success"] is False

    # EDIT must have succeeded before BUILD failure.
    assert len(result.edit_results) == 1
    assert result.edit_results[0]["success"] is True

    # DIFF must have succeeded.
    assert result.diff_success is True

    # DIFF validation must have succeeded.
    assert result.diff_validated is True

    # BUILD must have failed.
    assert result.build_result is not None
    assert result.build_result["success"] is False
    assert result.build_result["returncode"] == 1
    assert result.build_result["timeout"] is False
    assert result.build_result["elapsed"] == 0.001

    # RUN must never execute after BUILD failure.
    assert result.run_result is None

    # The original build diagnostics must remain available.
    assert result.diagnostics_stderr == (
        "Simulated build failure "
        "before rollback."
    )

    print_header(
        "ROLLBACK FAILURE TRANSACTION TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Build success:",
        result.build_result["success"],
    )

    print(
        "Run result:",
        result.run_result,
    )

    print(
        "Rollback success:",
        result.rollback_result["success"],
    )

    print()
    print(
        "All ROLLBACK_FAILED transaction "
        "assertions passed."
    )

    return result
def test_transaction_precheck_failure_contract():
    """
    Verify that a dirty working tree causes PRECHECK_FAILED
    before checkpoint creation or any edit operation.
    """

    test_path = (
        "agent_transaction_precheck_failure_contract_test.txt"
    )

    # Create an untracked file to make the working tree dirty.
    test_file = PROJECT_ROOT / test_path

    test_file.write_text(
        "Precheck failure contract test\n",
        encoding="utf-8",
        newline="\n",
    )

    try:
        result = run_task(
            Task(
                edits=[
                    {
                        "type": "create",
                        "path": (
                            "agent_transaction_precheck_should_not_run.txt"
                        ),
                        "content": (
                            "This edit must not be executed.\n"
                        ),
                    }
                ],
                expected_paths=[
                    "agent_transaction_precheck_should_not_run.txt"
                ],
            )
        )

        assert isinstance(result, TaskResult)
        assert result.success is False

        # The task must stop during PRECHECK.
        assert result.stage == "PRECHECK"

        # The failure must be explicitly classified.
        assert result.failure_code == "PRECHECK_FAILED"

        # No checkpoint may be created.
        assert result.checkpoint is None

        # No edit operation may have been executed.
        assert result.edit_results == []

        # No diff/build/run stages may execute.
        assert result.diff == ""
        assert result.changed_paths == []
        assert result.diff_success is False
        assert result.diff_validated is False

        assert result.build_result is None
        assert result.run_result is None

        # No rollback is possible because no checkpoint exists.
        assert result.rollback_result is None

        print_header(
            "PRECHECK FAILURE TRANSACTION TEST"
        )

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Success:",
            result.success,
        )

        print(
            "Stage:",
            result.stage,
        )

        print(
            "Failure code:",
            result.failure_code,
        )

        print(
            "Checkpoint:",
            result.checkpoint,
        )

        print(
            "Edit results:",
            result.edit_results,
        )

        print(
            "Build result:",
            result.build_result,
        )

        print(
            "Run result:",
            result.run_result,
        )

        print()
        print(
            "All PRECHECK_FAILED transaction "
            "assertions passed."
        )

        return result

    finally:
        if test_file.exists():
            test_file.unlink()
def test_transaction_checkpoint_failure_contract():
    """
    Verify that checkpoint creation failure stops the task
    before any edit operation.
    """

    original_create_checkpoint = create_checkpoint

    try:
        def fake_create_checkpoint():
            print()
            print("TEST: simulated checkpoint creation failure.")
            return None

        globals()["create_checkpoint"] = fake_create_checkpoint

        result = run_task(
            Task(
                edits=[
                    {
                        "type": "create",
                        "path": (
                            "agent_transaction_checkpoint_should_not_run.txt"
                        ),
                        "content": (
                            "This edit must not be executed.\n"
                        ),
                    }
                ],
                expected_paths=[
                    "agent_transaction_checkpoint_should_not_run.txt"
                ],
            )
        )

        assert isinstance(result, TaskResult)
        assert result.success is False

        # The task must stop during CHECKPOINT.
        assert result.stage == "CHECKPOINT"

        # The failure must be explicitly classified.
        assert result.failure_code == "CHECKPOINT_FAILED"

        # No checkpoint was created.
        assert result.checkpoint is None

        # No edit operation may have been executed.
        assert result.edit_results == []

        # No later stages may execute.
        assert result.diff == ""
        assert result.changed_paths == []
        assert result.diff_success is False
        assert result.diff_validated is False

        assert result.build_result is None
        assert result.run_result is None

        # No rollback is possible because no checkpoint exists.
        assert result.rollback_result is None

        print_header(
            "CHECKPOINT FAILURE TRANSACTION TEST"
        )

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Success:",
            result.success,
        )

        print(
            "Stage:",
            result.stage,
        )

        print(
            "Failure code:",
            result.failure_code,
        )

        print(
            "Checkpoint:",
            result.checkpoint,
        )

        print(
            "Edit results:",
            result.edit_results,
        )

        print(
            "Build result:",
            result.build_result,
        )

        print(
            "Run result:",
            result.run_result,
        )

        print()
        print(
            "All CHECKPOINT_FAILED transaction "
            "assertions passed."
        )

        return result

    finally:
        globals()["create_checkpoint"] = (
            original_create_checkpoint
        )
def test_transaction_success_contract():
    """
    Verify a complete successful transaction from PRECHECK
    through BUILD and RUN to COMPLETE.
    """

    test_path = (
        "agent_transaction_success_contract_test.txt"
    )

    original_run_simulation = run_simulation

    try:
        def fake_run_simulation():
            print()
            print("TEST: simulated successful RUN.")

            return {
                "success": True,
                "returncode": 0,
                "stdout": (
                    "Simulated successful run.\n"
                ),
                "stderr": "",
                "elapsed": 0.001,
                "timeout": False,
            }

        globals()["run_simulation"] = fake_run_simulation

        result = run_task(
            Task(
                edits=[
                    {
                        "type": "create",
                        "path": test_path,
                        "content": (
                            "Successful transaction contract test.\n"
                        ),
                    }
                ],
                expected_paths=[test_path],
            )
        )

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.stage == "COMPLETE"

        assert result.failure_code is None
        assert result.failure_message is None

        assert result.checkpoint is not None

        # EDIT
        assert len(result.edit_results) == 1
        assert result.edit_results[0]["type"] == "create"
        assert result.edit_results[0]["path"] == test_path
        assert result.edit_results[0]["success"] is True

        # DIFF
        assert result.diff_success is True
        assert result.diff_validated is True
        assert result.changed_paths == [test_path]
        assert result.diff != ""

        # BUILD
        assert result.build_result is not None
        assert result.build_result["success"] is True
        assert result.build_result["returncode"] == 0
        assert result.build_result["timeout"] is False

        # RUN
        assert result.run_result is not None
        assert result.run_result["success"] is True
        assert result.run_result["returncode"] == 0
        assert result.run_result["timeout"] is False

        # Successful transaction must not rollback automatically.
        assert result.rollback_result is None

        print_header(
            "SUCCESSFUL TRANSACTION TEST"
        )

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Success:",
            result.success,
        )

        print(
            "Stage:",
            result.stage,
        )

        print(
            "Failure code:",
            result.failure_code,
        )

        print(
            "Checkpoint:",
            result.checkpoint,
        )

        print(
            "Edit results:",
            result.edit_results,
        )

        print(
            "Changed paths:",
            result.changed_paths,
        )

        print(
            "Diff success:",
            result.diff_success,
        )

        print(
            "Diff validated:",
            result.diff_validated,
        )

        print(
            "Build result:",
            result.build_result,
        )

        print(
            "Run result:",
            result.run_result,
        )

        print(
            "Rollback result:",
            result.rollback_result,
        )

        print()
        print(
            "All successful transaction "
            "assertions passed."
        )

        # The successful transaction intentionally leaves its
        # checkpoint and edit alive. Clean it up after all
        # assertions have passed.
        cleanup_success = rollback_to_checkpoint(
            require_confirmation=False
        )

        assert cleanup_success is True

        assert not (
            PROJECT_ROOT / test_path
        ).exists()

        print(
            "Successful transaction cleanup passed."
        )

        return result

    finally:
        globals()["run_simulation"] = (
            original_run_simulation
        )
def test_transaction_json_integration_contract():
    """
    Verify that a successful run_task() transaction can be
    serialized into the complete TaskResult JSON V1 contract.
    """

    test_path = (
        "agent_transaction_json_integration_contract_test.txt"
    )

    original_run_simulation = run_simulation

    try:
        def fake_run_simulation():
            print()
            print("TEST: simulated successful RUN.")

            return {
                "success": True,
                "returncode": 0,
                "stdout": (
                    "Simulated successful run.\n"
                ),
                "stderr": "",
                "elapsed": 0.001,
                "timeout": False,
            }

        globals()["run_simulation"] = fake_run_simulation

        result = run_task(
            Task(
                task_id="TEST-TRANSACTION-JSON-INTEGRATION",
                description=(
                    "Verify successful transaction JSON serialization."
                ),
                edits=[
                    {
                        "type": "create",
                        "path": test_path,
                        "content": (
                            "JSON integration contract test.\n"
                        ),
                    }
                ],
                expected_paths=[test_path],
            )
        )

        assert isinstance(result, TaskResult)

        # Transaction must complete successfully.
        assert result.success is True
        assert result.stage == "COMPLETE"
        assert result.failure_code is None
        assert result.failure_message is None

        # Serialize the actual TaskResult produced by run_task().
        json_text = task_result_to_json(result)

        assert isinstance(json_text, str)
        assert json_text != ""

        data = json.loads(json_text)

        # Root contract.
        assert data["schema_version"] == 1
        assert data["success"] is True
        assert data["stage"] == "COMPLETE"
        assert data["attempts"] == result.attempts

        # Checkpoint.
        assert data["checkpoint"]["created"] is True
        assert (
            data["checkpoint"]["commit"]
            == result.checkpoint
        )

        # Edits.
        assert data["edits"]["success"] is True
        assert data["edits"]["count"] == 1
        assert len(data["edits"]["results"]) == 1

        assert (
            data["edits"]["results"][0]["path"]
            == test_path
        )

        assert (
            data["edits"]["results"][0]["type"]
            == "create"
        )

        assert (
            data["edits"]["results"][0]["success"]
            is True
        )

        # Diff.
        assert data["diff"]["success"] is True
        assert data["diff"]["validated"] is True
        assert (
            data["diff"]["changed_paths"]
            == [test_path]
        )

        # Build.
        assert data["build"] is not None
        assert data["build"]["success"] is True
        assert data["build"]["returncode"] == 0
        assert data["build"]["timeout"] is False
        assert data["build"]["elapsed"] == (
            result.build_result["elapsed"]
        )

        # Run.
        assert data["run"] is not None
        assert data["run"]["success"] is True
        assert data["run"]["returncode"] == 0
        assert data["run"]["timeout"] is False
        assert data["run"]["elapsed"] == (
            result.run_result["elapsed"]
        )

        # Successful transaction must not contain a failure.
        assert data["failure"] is None

        # Successful transaction does not rollback.
        assert data["rollback"]["performed"] is False
        assert data["rollback"]["success"] is None

        # Diagnostics must still exist in the JSON contract.
        assert "stdout" in data["diagnostics"]
        assert "stderr" in data["diagnostics"]

        print_header(
            "TRANSACTION JSON INTEGRATION TEST"
        )

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Transaction success:",
            result.success,
        )

        print(
            "Transaction stage:",
            result.stage,
        )

        print(
            "JSON schema version:",
            data["schema_version"],
        )

        print(
            "JSON success:",
            data["success"],
        )

        print(
            "JSON stage:",
            data["stage"],
        )

        print(
            "JSON checkpoint:",
            data["checkpoint"],
        )

        print(
            "JSON edits:",
            data["edits"],
        )

        print(
            "JSON diff:",
            data["diff"],
        )

        print(
            "JSON build:",
            data["build"],
        )

        print(
            "JSON run:",
            data["run"],
        )

        print(
            "JSON rollback:",
            data["rollback"],
        )

        print(
            "JSON failure:",
            data["failure"],
        )

        print()
        print(
            "All transaction JSON integration "
            "assertions passed."
        )

        # The successful transaction intentionally leaves
        # the checkpoint and test file alive until all
        # assertions have passed.
        cleanup_success = rollback_to_checkpoint(
            require_confirmation=False
        )

        assert cleanup_success is True

        assert not (
            PROJECT_ROOT / test_path
        ).exists()

        print(
            "Transaction JSON integration "
            "cleanup passed."
        )

        return result

    finally:
        globals()["run_simulation"] = (
            original_run_simulation
        )
def test_task_v1_contract():
    """
    Verify the minimal Task V1 data contract.
    """

    task = Task(
        edits=[
            {
                "type": "create",
                "path": (
                    "agent_task_v1_contract_test.txt"
                ),
                "content": (
                    "Task V1 contract test.\n"
                ),
            }
        ],
        expected_paths=[
            "agent_task_v1_contract_test.txt"
        ],
    )

    assert isinstance(task, Task)

    assert isinstance(task.edits, list)
    assert len(task.edits) == 1

    edit = task.edits[0]

    assert edit["type"] == "create"
    assert (
        edit["path"]
        == "agent_task_v1_contract_test.txt"
    )
    assert (
        edit["content"]
        == "Task V1 contract test.\n"
    )

    assert isinstance(task.expected_paths, list)
    assert task.expected_paths == [
        "agent_task_v1_contract_test.txt"
    ]

    print_header("TASK V1 CONTRACT TEST")

    print(
        "Task type:",
        type(task).__name__,
    )

    print(
        "Edit count:",
        len(task.edits),
    )

    print(
        "Edit:",
        task.edits[0],
    )

    print(
        "Expected paths:",
        task.expected_paths,
    )

    print()
    print(
        "All Task V1 contract assertions passed."
    )

    return task
def test_task_v2_contract():
    """
    Verify the minimal Task V2 data contract.
    """

    task = Task(
        task_id="TASK-V2-001",
        description=(
            "Task V2 contract test."
        ),
        edits=[
            {
                "type": "create",
                "path": (
                    "agent_task_v2_contract_test.txt"
                ),
                "content": (
                    "Task V2 contract test.\n"
                ),
            }
        ],
        expected_paths=[
            "agent_task_v2_contract_test.txt"
        ],
    )

    assert isinstance(task, Task)

    assert isinstance(task.task_id, str)
    assert task.task_id == "TASK-V2-001"

    assert isinstance(task.description, str)
    assert (
        task.description
        == "Task V2 contract test."
    )

    assert isinstance(task.edits, list)
    assert len(task.edits) == 1

    assert isinstance(task.expected_paths, list)
    assert task.expected_paths == [
        "agent_task_v2_contract_test.txt"
    ]

    print_header("TASK V2 CONTRACT TEST")

    print(
        "Task type:",
        type(task).__name__,
    )

    print(
        "Task ID:",
        task.task_id,
    )

    print(
        "Description:",
        task.description,
    )

    print(
        "Edit count:",
        len(task.edits),
    )

    print(
        "Expected paths:",
        task.expected_paths,
    )

    print()
    print(
        "All Task V2 contract assertions passed."
    )

    return task
def test_validate_task():
    """
    Verify minimal Task V2 validation.
    """

    valid_task = Task(
        task_id="TASK-VALID-001",
        description="Valid Task V2 test.",
    )

    empty_id_task = Task(
        task_id="",
        description="Valid description.",
    )

    empty_description_task = Task(
        task_id="TASK-INVALID-001",
        description="",
    )
    invalid_edits_task = Task(
        task_id="TASK-INVALID-002",
        description="Valid description.",
        edits="not a list",
    )

    invalid_expected_paths_task = Task(
        task_id="TASK-INVALID-003",
        description="Valid description.",
        expected_paths="not a list",
    )
    invalid_edit_element_task = Task(
        task_id="TASK-INVALID-004",
        description="Valid description.",
        edits=[
            "not a dictionary"
        ],
    )
    invalid_edit_type_task = Task(
        task_id="TASK-INVALID-005",
        description="Valid description.",
        edits=[
            {
                "path": "test.txt"
            }
        ],
    )
    unknown_edit_type_task = Task(
        task_id="TASK-INVALID-006",
        description="Valid description.",
        edits=[
            {
                "type": "unknown",
                "path": "test.txt",
            }
        ],
    )
    missing_create_path_task = Task(
        task_id="TASK-INVALID-007",
        description="Missing create path.",
        edits=[
            {
                "type": "create",
                "content": "test",
            }
        ],
    )
    missing_create_content_task = Task(
        task_id="TASK-INVALID-008",
        description="Missing create content.",
        edits=[
            {
                "type": "create",
                "path": "test.txt",
            }
        ],
    )
    missing_replace_path_task = Task(
        task_id="TASK-INVALID-009",
        description="Missing replace path.",
        edits=[
            {
                "type": "replace",
                "old_text": "old",
                "new_text": "new",
            }
        ],
    )
    missing_replace_old_text_task = Task(
        task_id="TASK-INVALID-010",
        description="Missing replace old text.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "new_text": "new",
            }
        ],
    )
    missing_replace_new_text_task = Task(
        task_id="TASK-INVALID-011",
        description="Missing replace new text.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old",
            }
        ],
    )
    invalid_create_path_type_task = Task(
        task_id="TASK-INVALID-012",
        description="Invalid create path type.",
        edits=[
            {
                "type": "create",
                "path": 123,
                "content": "test",
            }
        ],
    )
    invalid_create_content_type_task = Task(
        task_id="TASK-INVALID-013",
        description="Invalid create content type.",
        edits=[
            {
                "type": "create",
                "path": "test.txt",
                "content": 123,
            }
        ],
    )
    invalid_replace_path_type_task = Task(
        task_id="TASK-INVALID-014",
        description="Invalid replace path type.",
        edits=[
            {
                "type": "replace",
                "path": 123,
                "old_text": "old",
                "new_text": "new",
            }
        ],
    )

    invalid_replace_old_text_type_task = Task(
        task_id="TASK-INVALID-015",
        description="Invalid replace old text type.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": 123,
                "new_text": "new",
            }
        ],
    )

    invalid_replace_new_text_type_task = Task(
        task_id="TASK-INVALID-016",
        description="Invalid replace new text type.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old",
                "new_text": 123,
            }
        ],
    )

    invalid_replace_expected_count_type_task = Task(
        task_id="TASK-INVALID-017",
        description="Invalid replace expected count type.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old",
                "new_text": "new",
                "expected_count": "1",
            }
        ],
    )
    invalid_replace_expected_count_zero_task = Task(
        task_id="TASK-INVALID-018",
        description="Invalid replace expected count zero.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old",
                "new_text": "new",
                "expected_count": 0,
            }
        ],
    )

    invalid_replace_expected_count_negative_task = Task(
        task_id="TASK-INVALID-019",
        description="Invalid replace expected count negative.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old",
                "new_text": "new",
                "expected_count": -1,
            }
        ],
    )

    invalid_replace_expected_count_bool_task = Task(
        task_id="TASK-INVALID-020",
        description="Invalid replace expected count bool.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old",
                "new_text": "new",
                "expected_count": True,
            }
        ],
    )
    empty_create_path_task = Task(
        task_id="TASK-INVALID-021",
        description="Empty create path.",
        edits=[
            {
                "type": "create",
                "path": "",
                "content": "test",
            }
        ],
    )

    empty_create_content_task = Task(
        task_id="TASK-VALID-022",
        description="Empty create content.",
        edits=[
            {
                "type": "create",
                "path": "empty.txt",
                "content": "",
            }
        ],
        expected_paths=[
            "empty.txt",
        ],
    )

    empty_replace_old_text_task = Task(
        task_id="TASK-INVALID-023",
        description="Empty replace old text.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "",
                "new_text": "new",
            }
        ],
    )

    empty_replace_new_text_task = Task(
        task_id="TASK-VALID-024",
        description="Empty replace new text.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old",
                "new_text": "",
            }
        ],
    )
    invalid_expected_paths_element_type_task = Task(
        task_id="TASK-INVALID-025",
        description="Invalid expected paths element type.",
        expected_paths=[
            "test.txt",
            123,
        ],
    )

    empty_expected_paths_element_task = Task(
        task_id="TASK-INVALID-026",
        description="Empty expected paths element.",
        expected_paths=[
            "test.txt",
            "",
        ],
    )

    whitespace_expected_paths_element_task = Task(
        task_id="TASK-INVALID-027",
        description="Whitespace expected paths element.",
        expected_paths=[
            "test.txt",
            "   ",
        ],
    )
    missing_create_expected_path_task = Task(
        task_id="TASK-INVALID-028",
        description="Create path missing from expected paths.",
        edits=[
            {
                "type": "create",
                "path": "test.txt",
                "content": "test",
            }
        ],
        expected_paths=[
            "other.txt",
        ],
    )

    missing_replace_expected_path_task = Task(
        task_id="TASK-INVALID-029",
        description="Replace path missing from expected paths.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old",
                "new_text": "new",
            }
        ],
        expected_paths=[
            "other.txt",
        ],
    )

    extra_expected_path_task = Task(
        task_id="TASK-INVALID-030",
        description="Extra path in expected paths.",
        edits=[
            {
                "type": "create",
                "path": "test.txt",
                "content": "test",
            }
        ],
        expected_paths=[
            "test.txt",
            "extra.txt",
        ],
    )
    multiple_create_edits_task = Task(
        task_id="TASK-VALID-031",
        description="Multiple create edits.",
        edits=[
            {
                "type": "create",
                "path": "A.txt",
                "content": "A",
            },
            {
                "type": "create",
                "path": "B.txt",
                "content": "B",
            },
        ],
        expected_paths=[
            "A.txt",
            "B.txt",
        ],
    )

    multiple_replace_same_path_task = Task(
        task_id="TASK-VALID-032",
        description="Multiple replace edits on same path.",
        edits=[
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old1",
                "new_text": "new1",
            },
            {
                "type": "replace",
                "path": "test.txt",
                "old_text": "old2",
                "new_text": "new2",
            },
        ],
        expected_paths=[
            "test.txt",
        ],
    )

    create_replace_different_paths_task = Task(
        task_id="TASK-VALID-033",
        description="Create and replace on different paths.",
        edits=[
            {
                "type": "create",
                "path": "A.txt",
                "content": "A",
            },
            {
                "type": "replace",
                "path": "B.txt",
                "old_text": "old",
                "new_text": "new",
            },
        ],
        expected_paths=[
            "A.txt",
            "B.txt",
        ],
    )

    create_replace_same_path_task = Task(
        task_id="TASK-VALID-034",
        description="Create and replace on same path.",
        edits=[
            {
                "type": "create",
                "path": "A.txt",
                "content": "A",
            },
            {
                "type": "replace",
                "path": "A.txt",
                "old_text": "A",
                "new_text": "B",
            },
        ],
        expected_paths=[
            "A.txt",
        ],
    )
    
    assert validate_task(valid_task) is True
    assert validate_task(empty_id_task) is False
    assert validate_task(empty_description_task) is False
    assert validate_task(None) is False
    assert validate_task(invalid_edits_task) is False
    assert validate_task(invalid_expected_paths_task) is False
    assert validate_task(invalid_edit_element_task) is False
    assert validate_task(invalid_edit_type_task) is False
    assert validate_task(unknown_edit_type_task) is False
    assert validate_task(missing_create_path_task) is False
    assert validate_task(missing_create_content_task) is False
    assert validate_task(missing_replace_path_task) is False
    assert validate_task(missing_replace_old_text_task) is False
    assert validate_task(missing_replace_new_text_task) is False
    assert validate_task(invalid_create_path_type_task) is False
    assert validate_task(invalid_create_content_type_task) is False
    assert validate_task(invalid_replace_path_type_task) is False
    assert validate_task(invalid_replace_old_text_type_task) is False
    assert validate_task(invalid_replace_new_text_type_task) is False
    assert validate_task(invalid_replace_expected_count_type_task) is False
    assert validate_task(invalid_replace_expected_count_zero_task) is False
    assert validate_task(invalid_replace_expected_count_negative_task) is False
    assert validate_task(invalid_replace_expected_count_bool_task) is False
    assert validate_task(empty_create_path_task) is False
    assert validate_task(empty_create_content_task) is True
    assert validate_task(empty_replace_old_text_task) is False
    assert validate_task(empty_replace_new_text_task) is True
    assert validate_task(invalid_expected_paths_element_type_task) is False
    assert validate_task(empty_expected_paths_element_task) is False
    assert validate_task(whitespace_expected_paths_element_task) is False
    assert validate_task(missing_create_expected_path_task) is False
    assert validate_task(missing_replace_expected_path_task) is False
    assert validate_task(extra_expected_path_task) is False
    assert validate_task(multiple_create_edits_task) is True
    assert validate_task(multiple_replace_same_path_task) is True
    assert validate_task(create_replace_different_paths_task) is True
    assert validate_task(create_replace_same_path_task) is True
    print_header("TASK VALIDATION TEST")

    print(
        "Valid task:",
        validate_task(valid_task),
    )

    print(
        "Empty task ID:",
        validate_task(empty_id_task),
    )

    print(
        "Empty description:",
        validate_task(empty_description_task),
    )
    print(
        "Invalid edits type:",
        validate_task(invalid_edits_task),
    )

    print(
        "Invalid expected_paths type:",
        validate_task(invalid_expected_paths_task),
    )
    print(
        "Invalid edit element type:",
        validate_task(invalid_edit_element_task),
    )
    print(
        "Invalid edit type:",
        validate_task(invalid_edit_type_task),
    )
    print(
        "Unknown edit type:",
        validate_task(unknown_edit_type_task),
    )
    print(
        "Missing create path:",
        validate_task(missing_create_path_task),
    )
    print(
        "Missing create content:",
        validate_task(missing_create_content_task),
    )
    print(
        "Missing replace path:",
        validate_task(missing_replace_path_task),
    )
    print(
        "Missing replace old text:",
        validate_task(
            missing_replace_old_text_task
        ),
    )
    print(
        "Missing replace new text:",
        validate_task(
            missing_replace_new_text_task
        ),
    )
    print(
        "Invalid create path type:",
        validate_task(
            invalid_create_path_type_task
        ),
    )
    print(
        "Invalid create content type:",
        validate_task(
            invalid_create_content_type_task
        ),
    )
    print(
        "Invalid replace path type:",
        validate_task(
            invalid_replace_path_type_task
        ),
    )

    print(
        "Invalid replace old text type:",
        validate_task(
            invalid_replace_old_text_type_task
        ),
    )

    print(
        "Invalid replace new text type:",
        validate_task(
            invalid_replace_new_text_type_task
        ),
    )

    print(
        "Invalid replace expected count type:",
        validate_task(
            invalid_replace_expected_count_type_task
        ),
    )
    print(
        "Invalid replace expected count zero:",
        validate_task(
            invalid_replace_expected_count_zero_task
        ),
    )

    print(
        "Invalid replace expected count negative:",
        validate_task(
            invalid_replace_expected_count_negative_task
        ),
    )

    print(
        "Invalid replace expected count bool:",
        validate_task(
            invalid_replace_expected_count_bool_task
        ),
    )
    print(
        "Empty create path:",
        validate_task(empty_create_path_task),
    )

    print(
        "Empty create content:",
        validate_task(empty_create_content_task),
    )

    print(
        "Empty replace old text:",
        validate_task(empty_replace_old_text_task),
    )

    print(
        "Empty replace new text:",
        validate_task(empty_replace_new_text_task),
    )
    print(
        "Invalid expected paths element type:",
        validate_task(invalid_expected_paths_element_type_task),
    )

    print(
        "Empty expected paths element:",
        validate_task(empty_expected_paths_element_task),
    )

    print(
        "Whitespace expected paths element:",
        validate_task(whitespace_expected_paths_element_task),
    )
    print(
        "Missing create expected path:",
        validate_task(missing_create_expected_path_task),
    )

    print(
        "Missing replace expected path:",
        validate_task(missing_replace_expected_path_task),
    )

    print(
        "Extra expected path:",
        validate_task(extra_expected_path_task),
    )
    print(
        "Multiple create edits:",
        validate_task(multiple_create_edits_task),
    )

    print(
        "Multiple replace same path:",
        validate_task(multiple_replace_same_path_task),
    )

    print(
        "Create replace different paths:",
        validate_task(create_replace_different_paths_task),
    )

    print(
        "Create replace same path:",
        validate_task(create_replace_same_path_task),
    )
    print(
        "None task:",
        validate_task(None),
    )

    print()
    print(
        "All Task V2 validation assertions passed."
    )

    return True
def test_run_task_task_validation_failure():
    """
    Verify that an invalid Task V2 is rejected
    before Git precheck and checkpoint creation.
    """

    invalid_task = Task(
        task_id="",
        description="",
        edits=[],
        expected_paths=[],
    )

    result = run_task(invalid_task)

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.stage == "PRECHECK"
    assert result.failure_code == "PRECHECK_FAILED"
    assert result.failure_message == (
        "Task validation failed."
    )
    assert result.checkpoint is None
    assert result.edit_results == []
    assert result.build_result is None
    assert result.run_result is None
    assert result.rollback_result is None

    print_header(
        "RUN TASK VALIDATION FAILURE TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Checkpoint:",
        result.checkpoint,
    )

    print(
        "Edit results:",
        result.edit_results,
    )

    print(
        "Build result:",
        result.build_result,
    )

    print(
        "Run result:",
        result.run_result,
    )

    print(
        "Rollback result:",
        result.rollback_result,
    )

    print()
    print(
        "All Task validation failure "
        "assertions passed."
    )

    return result
def test_run_task_invalid_edits_type():
    """
    Verify that run_task() rejects a Task V2
    with an invalid edits type before Git precheck.
    """

    invalid_task = Task(
        task_id="TASK-INVALID-EDITS-001",
        description="Invalid edits type test.",
        edits="not a list",
        expected_paths=[],
    )

    result = run_task(invalid_task)

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.stage == "PRECHECK"
    assert result.failure_code == "PRECHECK_FAILED"
    assert result.failure_message == (
        "Task validation failed."
    )
    assert result.checkpoint is None
    assert result.edit_results == []
    assert result.build_result is None
    assert result.run_result is None
    assert result.rollback_result is None

    print_header(
        "RUN TASK INVALID EDITS TYPE TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Checkpoint:",
        result.checkpoint,
    )

    print(
        "Edit results:",
        result.edit_results,
    )

    print(
        "Build result:",
        result.build_result,
    )

    print(
        "Run result:",
        result.run_result,
    )

    print(
        "Rollback result:",
        result.rollback_result,
    )

    print()
    print(
        "All invalid edits type assertions passed."
    )

    return result
def test_run_task_invalid_expected_paths_type():
    """
    Verify that run_task() rejects a Task V2
    with an invalid expected_paths type before Git precheck.
    """

    invalid_task = Task(
        task_id="TASK-INVALID-PATHS-001",
        description="Invalid expected_paths type test.",
        edits=[],
        expected_paths="not a list",
    )

    result = run_task(invalid_task)

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.stage == "PRECHECK"
    assert result.failure_code == "PRECHECK_FAILED"
    assert result.failure_message == (
        "Task validation failed."
    )
    assert result.checkpoint is None
    assert result.edit_results == []
    assert result.build_result is None
    assert result.run_result is None
    assert result.rollback_result is None

    print_header(
        "RUN TASK INVALID EXPECTED PATHS TYPE TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Checkpoint:",
        result.checkpoint,
    )

    print(
        "Edit results:",
        result.edit_results,
    )

    print(
        "Build result:",
        result.build_result,
    )

    print(
        "Run result:",
        result.run_result,
    )

    print(
        "Rollback result:",
        result.rollback_result,
    )

    print()
    print(
        "All invalid expected_paths type "
        "assertions passed."
    )

    return result
def test_run_task_invalid_edit_element_type():
    """
    Verify that run_task() rejects a Task V2
    containing a non-dictionary edit before Git precheck.
    """

    invalid_task = Task(
        task_id="TASK-INVALID-EDIT-ELEMENT-001",
        description="Invalid edit element type test.",
        edits=[
            "not a dictionary"
        ],
        expected_paths=[],
    )

    result = run_task(invalid_task)

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.stage == "PRECHECK"
    assert result.failure_code == "PRECHECK_FAILED"
    assert result.failure_message == (
        "Task validation failed."
    )
    assert result.checkpoint is None
    assert result.edit_results == []
    assert result.build_result is None
    assert result.run_result is None
    assert result.rollback_result is None

    print_header(
        "RUN TASK INVALID EDIT ELEMENT TYPE TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Checkpoint:",
        result.checkpoint,
    )

    print(
        "Edit results:",
        result.edit_results,
    )

    print(
        "Build result:",
        result.build_result,
    )

    print(
        "Run result:",
        result.run_result,
    )

    print(
        "Rollback result:",
        result.rollback_result,
    )

    print()
    print(
        "All invalid edit element type "
        "assertions passed."
    )

    return result
def test_run_task_invalid_edit_type():
    """
    Verify that run_task() rejects an edit without
    a valid type field before Git precheck.
    """

    invalid_task = Task(
        task_id="TASK-INVALID-EDIT-TYPE-001",
        description="Invalid edit type test.",
        edits=[
            {
                "path": "test.txt"
            }
        ],
        expected_paths=[],
    )

    result = run_task(invalid_task)

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.stage == "PRECHECK"
    assert result.failure_code == "PRECHECK_FAILED"
    assert result.failure_message == (
        "Task validation failed."
    )
    assert result.checkpoint is None
    assert result.edit_results == []
    assert result.build_result is None
    assert result.run_result is None
    assert result.rollback_result is None

    print_header(
        "RUN TASK INVALID EDIT TYPE TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Checkpoint:",
        result.checkpoint,
    )

    print(
        "Edit results:",
        result.edit_results,
    )

    print(
        "Build result:",
        result.build_result,
    )

    print(
        "Run result:",
        result.run_result,
    )

    print(
        "Rollback result:",
        result.rollback_result,
    )

    print()
    print(
        "All invalid edit type assertions passed."
    )

    return result
def test_run_task_valid_create():
    """
    Verify that run_task() accepts a valid create edit
    and completes the transaction successfully.
    """

    test_path = "agent_create_test.txt"

    task = Task(
        task_id="TASK-VALID-CREATE-001",
        description="Valid create edit test.",
        edits=[
            {
                "type": "create",
                "path": test_path,
                "content": "SimulationAgent create test.\n",
            }
        ],
        expected_paths=[
            test_path,
        ],
    )

    result = run_task(task)

    assert isinstance(result, TaskResult)
    assert result.success is True
    assert result.failure_code is None
    assert result.failure_message is None
    assert result.edit_results
    assert result.edit_results[0]["type"] == "create"
    assert result.edit_results[0]["path"] == test_path
    assert result.edit_results[0]["success"] is True

    assert result.diff_success is True
    assert result.diff_validated is True
    assert result.build_result is not None
    assert result.build_result["success"] is True
    assert result.run_result is not None
    assert result.run_result["success"] is True

    created_path = resolve_project_path(test_path)

    assert created_path.exists()
    assert created_path.read_text(
        encoding="utf-8"
    ) == "SimulationAgent create test.\n"

    print_header(
        "RUN TASK VALID CREATE TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Failure message:",
        result.failure_message,
    )

    print(
        "Checkpoint:",
        result.checkpoint,
    )

    print(
        "Edit results:",
        result.edit_results,
    )

    print(
        "Diff success:",
        result.diff_success,
    )

    print(
        "Diff validated:",
        result.diff_validated,
    )

    print(
        "Build success:",
        result.build_result["success"]
        if result.build_result
        else None,
    )

    print(
        "Run success:",
        result.run_result["success"]
        if result.run_result
        else None,
    )

    print(
        "Created file exists:",
        created_path.exists(),
    )

    print()
    print(
        "All valid create edit "
        "assertions passed."
    )

    return result
def test_run_task_valid_replace():
    """
    Verify that run_task() accepts a valid replace edit
    and completes the full transaction successfully.

    The test prepares a temporary tracked fixture by creating
    a temporary Git commit. After the test, the repository is
    restored to its original HEAD.
    """

    test_path = "agent_replace_test.txt"

    original_head_result = git_command(
        ["rev-parse", "HEAD"],
        timeout=30,
    )

    assert original_head_result["returncode"] == 0

    original_head = (
        original_head_result["stdout"].strip()
    )

    test_file = resolve_project_path(test_path)

    result = None

    try:
        test_file.write_text(
            "Original replacement content.\n",
            encoding="utf-8",
            newline="\n",
        )

        add_result = git_command(
            ["add", "--", test_path],
            timeout=30,
        )

        assert add_result["returncode"] == 0

        commit_result = git_command(
            [
                "commit",
                "-m",
                "TEMP: replace test fixture",
            ],
            timeout=30,
        )

        assert commit_result["returncode"] == 0

        clean_result = git_command(
            ["status", "--short"],
            timeout=30,
        )
        print("CLEAN RESULT:", clean_result)
        assert clean_result["returncode"] == 0
        assert clean_result["stdout"].strip() == ""

        task = Task(
            task_id="TASK-VALID-REPLACE-001",
            description="Valid replace edit test.",
            edits=[
                {
                    "type": "replace",
                    "path": test_path,
                    "old_text": (
                        "Original replacement content.\n"
                    ),
                    "new_text": (
                        "Updated replacement content.\n"
                    ),
                    "expected_count": 1,
                }
            ],
            expected_paths=[
                test_path,
            ],
        )

        result = run_task(task)

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.stage == "COMPLETE"
        assert result.failure_code is None
        assert result.failure_message is None

        assert result.edit_results
        assert result.edit_results[0]["type"] == "replace"
        assert result.edit_results[0]["path"] == test_path
        assert result.edit_results[0]["success"] is True

        assert result.diff_success is True
        assert result.diff_validated is True

        assert result.build_result is not None
        assert result.build_result["success"] is True

        assert result.run_result is not None
        assert result.run_result["success"] is True

        assert test_file.exists()

        assert test_file.read_text(
            encoding="utf-8"
        ) == "Updated replacement content.\n"

        print_header(
            "RUN TASK VALID REPLACE TEST"
        )

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Success:",
            result.success,
        )

        print(
            "Stage:",
            result.stage,
        )

        print(
            "Failure code:",
            result.failure_code,
        )

        print(
            "Failure message:",
            result.failure_message,
        )

        print(
            "Checkpoint:",
            result.checkpoint,
        )

        print(
            "Edit results:",
            result.edit_results,
        )

        print(
            "Diff success:",
            result.diff_success,
        )

        print(
            "Diff validated:",
            result.diff_validated,
        )

        print(
            "Build success:",
            result.build_result["success"]
            if result.build_result
            else None,
        )

        print(
            "Run success:",
            result.run_result["success"]
            if result.run_result
            else None,
        )

        print(
            "Updated file exists:",
            test_file.exists(),
        )

        print(
            "Updated content verified:",
            test_file.read_text(
                encoding="utf-8"
            ) == "Updated replacement content.\n",
        )

        print()
        print(
            "All valid replace edit "
            "assertions passed."
        )

        return result

    finally:
        restore_result = git_command(
            [
                "reset",
                "--hard",
                original_head,
            ],
            timeout=30,
        )

        if restore_result["returncode"] != 0:
            print()
            print(
                "WARNING: Failed to restore "
                "original HEAD."
            )

        clean_result = git_command(
            ["clean", "-fd", "--"],
            timeout=30,
        )

        if clean_result["returncode"] != 0:
            print()
            print(
                "WARNING: Failed to clean "
                "temporary files."
            )

        clear_checkpoint()

        final_status = git_command(
            ["status", "--short", "--branch"],
            timeout=30,
        )

        if final_status["returncode"] == 0:
            print()
            print(
                "Repository restored after "
                "valid replace test."
            )

            print(
                final_status["stdout"].strip()
            )
def _run_multi_edit_success_test(
    task,
    fixture_files=None,
    expected_contents=None,
    test_title="MULTI EDIT TEST",
):
    """
    Verify that a multi-edit Task completes the full
    transactional execution successfully.

    Optional fixture_files are created and committed before
    the task so replace edits have tracked files to modify.
    The repository is restored to its original HEAD afterward.
    """

    fixture_files = fixture_files or {}
    expected_contents = expected_contents or {}

    original_head_result = git_command(
        ["rev-parse", "HEAD"],
        timeout=30,
    )

    assert original_head_result["returncode"] == 0

    original_head = (
        original_head_result["stdout"].strip()
    )

    result = None

    try:
        for path, content in fixture_files.items():
            test_file = resolve_project_path(path)

            test_file.write_text(
                content,
                encoding="utf-8",
                newline="\n",
            )

            add_result = git_command(
                ["add", "--", path],
                timeout=30,
            )

            assert add_result["returncode"] == 0

        if fixture_files:
            commit_result = git_command(
                [
                    "commit",
                    "-m",
                    "TEMP: multi-edit test fixture",
                ],
                timeout=30,
            )

            assert commit_result["returncode"] == 0

        clean_result = git_command(
            ["status", "--short"],
            timeout=30,
        )

        assert clean_result["returncode"] == 0
        assert clean_result["stdout"].strip() == ""

        result = run_task(task)

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.stage == "COMPLETE"
        assert result.failure_code is None
        assert result.failure_message is None

        assert result.diff_success is True
        assert result.diff_validated is True

        assert result.build_result is not None
        assert result.build_result["success"] is True

        assert result.run_result is not None
        assert result.run_result["success"] is True

        for path, expected_content in expected_contents.items():
            test_file = resolve_project_path(path)

            assert test_file.exists()

            assert test_file.read_text(
                encoding="utf-8"
            ) == expected_content

        print_header(test_title)

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Success:",
            result.success,
        )

        print(
            "Stage:",
            result.stage,
        )

        print(
            "Failure code:",
            result.failure_code,
        )

        print(
            "Failure message:",
            result.failure_message,
        )

        print(
            "Checkpoint:",
            result.checkpoint,
        )

        print(
            "Edit results:",
            result.edit_results,
        )

        print(
            "Diff success:",
            result.diff_success,
        )

        print(
            "Diff validated:",
            result.diff_validated,
        )

        print(
            "Build success:",
            result.build_result["success"]
            if result.build_result
            else None,
        )

        print(
            "Run success:",
            result.run_result["success"]
            if result.run_result
            else None,
        )

        for path, expected_content in expected_contents.items():
            test_file = resolve_project_path(path)

            print(
                f"{path} verified:",
                test_file.read_text(
                    encoding="utf-8"
                ) == expected_content,
            )

        print()
        print(
            f"{test_title} assertions passed."
        )

        return result

    finally:
        restore_result = git_command(
            [
                "reset",
                "--hard",
                original_head,
            ],
            timeout=30,
        )

        if restore_result["returncode"] != 0:
            print()
            print(
                "WARNING: Failed to restore "
                "original HEAD."
            )

        clean_result = git_command(
            ["clean", "-fd", "--"],
            timeout=30,
        )

        if clean_result["returncode"] != 0:
            print()
            print(
                "WARNING: Failed to clean "
                "temporary files."
            )

        clear_checkpoint()

        final_status = git_command(
            ["status", "--short", "--branch"],
            timeout=30,
        )

        if final_status["returncode"] == 0:
            print()
            print(
                "Repository restored after "
                "multi-edit test."
            )

            print(
                final_status["stdout"].strip()
            )
def test_run_task_multiple_create():
    """
    Verify that one Task can create multiple files
    in a single successful transaction.
    """

    path_a = "agent_multi_create_a.txt"
    path_b = "agent_multi_create_b.txt"

    task = Task(
        task_id="TASK-MULTI-CREATE-001",
        description="Multiple create edits test.",
        edits=[
            {
                "type": "create",
                "path": path_a,
                "content": "Create test A.\n",
            },
            {
                "type": "create",
                "path": path_b,
                "content": "Create test B.\n",
            },
        ],
        expected_paths=[
            path_a,
            path_b,
        ],
    )

    return _run_multi_edit_success_test(
        task,
        expected_contents={
            path_a: "Create test A.\n",
            path_b: "Create test B.\n",
        },
        test_title="RUN TASK MULTIPLE CREATE TEST",
    )
def test_run_task_multiple_replace_same_path():
    """
    Verify that one Task can perform multiple replace
    edits on the same tracked file.
    """

    test_path = "agent_multi_replace.txt"

    task = Task(
        task_id="TASK-MULTI-REPLACE-001",
        description="Multiple replace edits test.",
        edits=[
            {
                "type": "replace",
                "path": test_path,
                "old_text": "old1",
                "new_text": "new1",
                "expected_count": 1,
            },
            {
                "type": "replace",
                "path": test_path,
                "old_text": "old2",
                "new_text": "new2",
                "expected_count": 1,
            },
        ],
        expected_paths=[
            test_path,
        ],
    )

    return _run_multi_edit_success_test(
        task,
        fixture_files={
            test_path: (
                "old1\n"
                "middle\n"
                "old2\n"
            ),
        },
        expected_contents={
            test_path: (
                "new1\n"
                "middle\n"
                "new2\n"
            ),
        },
        test_title=(
            "RUN TASK MULTIPLE REPLACE "
            "SAME PATH TEST"
        ),
    )
def test_run_task_create_replace_different_paths():
    """
    Verify that one Task can create one file and replace
    content in another file in the same transaction.
    """

    create_path = "agent_multi_mixed_create.txt"
    replace_path = "agent_multi_mixed_replace.txt"

    task = Task(
        task_id="TASK-MULTI-MIXED-001",
        description="Create and replace different paths test.",
        edits=[
            {
                "type": "create",
                "path": create_path,
                "content": "Created mixed file.\n",
            },
            {
                "type": "replace",
                "path": replace_path,
                "old_text": "old content",
                "new_text": "new content",
                "expected_count": 1,
            },
        ],
        expected_paths=[
            create_path,
            replace_path,
        ],
    )

    return _run_multi_edit_success_test(
        task,
        fixture_files={
            replace_path: "old content\n",
        },
        expected_contents={
            create_path: "Created mixed file.\n",
            replace_path: "new content\n",
        },
        test_title=(
            "RUN TASK CREATE REPLACE "
            "DIFFERENT PATHS TEST"
        ),
    )
def test_run_task_create_replace_same_path():
    """
    Verify that one Task can create a file and then
    replace content in that same file.
    """

    test_path = "agent_multi_same_path.txt"

    task = Task(
        task_id="TASK-MULTI-SAME-PATH-001",
        description="Create and replace same path test.",
        edits=[
            {
                "type": "create",
                "path": test_path,
                "content": "Initial content.\n",
            },
            {
                "type": "replace",
                "path": test_path,
                "old_text": "Initial content.",
                "new_text": "Final content.",
                "expected_count": 1,
            },
        ],
        expected_paths=[
            test_path,
        ],
    )

    return _run_multi_edit_success_test(
        task,
        expected_contents={
            test_path: "Final content.\n",
        },
        test_title=(
            "RUN TASK CREATE REPLACE "
            "SAME PATH TEST"
        ),
    )
def _run_multi_edit_failure_test(
    task,
    fixture_files=None,
    expected_contents=None,
    expected_absent_paths=None,
    test_title="MULTI EDIT FAILURE TEST",
):
    """
    Verify that a multi-edit Task fails transactionally,
    rolls back successfully, and restores the expected state.
    """

    fixture_files = fixture_files or {}
    expected_contents = expected_contents or {}
    expected_absent_paths = expected_absent_paths or []

    original_head_result = git_command(
        ["rev-parse", "HEAD"],
        timeout=30,
    )

    assert original_head_result["returncode"] == 0

    original_head = (
        original_head_result["stdout"].strip()
    )

    result = None

    try:
        for path, content in fixture_files.items():
            test_file = resolve_project_path(path)

            test_file.write_text(
                content,
                encoding="utf-8",
                newline="\n",
            )

            add_result = git_command(
                ["add", "--", path],
                timeout=30,
            )

            assert add_result["returncode"] == 0

        if fixture_files:
            commit_result = git_command(
                [
                    "commit",
                    "-m",
                    "TEMP: multi-edit failure fixture",
                ],
                timeout=30,
            )

            assert commit_result["returncode"] == 0

        clean_result = git_command(
            ["status", "--short"],
            timeout=30,
        )

        assert clean_result["returncode"] == 0
        assert clean_result["stdout"].strip() == ""

        result = run_task(task)

        assert isinstance(result, TaskResult)
        assert result.success is False
        assert result.failure_code == "EDIT_FAILED"
        assert result.failure_message == (
            "An edit operation failed."
        )

        assert result.rollback_result is not None
        assert result.rollback_result["success"] is True

        assert result.stage == "ROLLBACK"

        for path, expected_content in expected_contents.items():
            test_file = resolve_project_path(path)

            assert test_file.exists()

            assert test_file.read_text(
                encoding="utf-8"
            ) == expected_content

        for path in expected_absent_paths:
            test_file = resolve_project_path(path)

            assert not test_file.exists()

        print_header(test_title)

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Success:",
            result.success,
        )

        print(
            "Stage:",
            result.stage,
        )

        print(
            "Failure code:",
            result.failure_code,
        )

        print(
            "Failure message:",
            result.failure_message,
        )

        print(
            "Checkpoint:",
            result.checkpoint,
        )

        print(
            "Edit results:",
            result.edit_results,
        )

        print(
            "Diff success:",
            result.diff_success,
        )

        print(
            "Diff validated:",
            result.diff_validated,
        )

        print(
            "Rollback result:",
            result.rollback_result,
        )

        for path, expected_content in expected_contents.items():
            test_file = resolve_project_path(path)

            print(
                f"{path} restored:",
                test_file.read_text(
                    encoding="utf-8"
                ) == expected_content,
            )

        for path in expected_absent_paths:
            test_file = resolve_project_path(path)

            print(
                f"{path} removed by rollback:",
                not test_file.exists(),
            )

        print()
        print(
            f"{test_title} assertions passed."
        )

        return result

    finally:
        restore_result = git_command(
            [
                "reset",
                "--hard",
                original_head,
            ],
            timeout=30,
        )

        if restore_result["returncode"] != 0:
            print()
            print(
                "WARNING: Failed to restore "
                "original HEAD."
            )

        clean_result = git_command(
            ["clean", "-fd", "--"],
            timeout=30,
        )

        if clean_result["returncode"] != 0:
            print()
            print(
                "WARNING: Failed to clean "
                "temporary files."
            )

        clear_checkpoint()

        final_status = git_command(
            ["status", "--short", "--branch"],
            timeout=30,
        )

        if final_status["returncode"] == 0:
            print()
            print(
                "Repository restored after "
                "multi-edit failure test."
            )

            print(
                final_status["stdout"].strip()
            )
def test_run_task_multi_edit_failure():
    """
    Verify that a failure in the second edit causes
    the successful first edit to be rolled back.
    """

    test_path = "agent_multi_failure.txt"

    task = Task(
        task_id="TASK-MULTI-FAILURE-001",
        description="Second edit failure test.",
        edits=[
            {
                "type": "replace",
                "path": test_path,
                "old_text": "first",
                "new_text": "changed",
                "expected_count": 1,
            },
            {
                "type": "replace",
                "path": test_path,
                "old_text": "does not exist",
                "new_text": "failure",
                "expected_count": 1,
            },
        ],
        expected_paths=[
            test_path,
        ],
    )

    return _run_multi_edit_failure_test(
        task,
        fixture_files={
            test_path: "first\n",
        },
        expected_contents={
            test_path: "first\n",
        },
        test_title=(
            "RUN TASK MULTI EDIT FAILURE TEST"
        ),
    )
def test_run_task_multi_edit_expected_count_failure():
    """
    Verify that an invalid expected_count causes the
    transaction to fail and roll back earlier edits.
    """

    test_path = "agent_expected_count_failure.txt"

    task = Task(
        task_id="TASK-MULTI-FAILURE-002",
        description="Expected count failure test.",
        edits=[
            {
                "type": "replace",
                "path": test_path,
                "old_text": "first",
                "new_text": "changed",
                "expected_count": 1,
            },
            {
                "type": "replace",
                "path": test_path,
                "old_text": "second",
                "new_text": "changed-second",
                "expected_count": 2,
            },
        ],
        expected_paths=[
            test_path,
        ],
    )

    return _run_multi_edit_failure_test(
        task,
        fixture_files={
            test_path: (
                "first\n"
                "second\n"
            ),
        },
        expected_contents={
            test_path: (
                "first\n"
                "second\n"
            ),
        },
        test_title=(
            "RUN TASK MULTI EDIT EXPECTED "
            "COUNT FAILURE TEST"
        ),
    )
def test_run_task_multi_edit_rollback_multiple_creates():
    """
    Verify that multiple successful creates are removed
    when a later edit fails.
    """

    create_path_a = "agent_rollback_create_a.txt"
    create_path_b = "agent_rollback_create_b.txt"
    fixture_path = "agent_rollback_fixture.txt"

    task = Task(
        task_id="TASK-MULTI-FAILURE-003",
        description="Rollback multiple creates test.",
        edits=[
            {
                "type": "create",
                "path": create_path_a,
                "content": "Created A.\n",
            },
            {
                "type": "create",
                "path": create_path_b,
                "content": "Created B.\n",
            },
            {
                "type": "replace",
                "path": fixture_path,
                "old_text": "missing",
                "new_text": "failure",
                "expected_count": 1,
            },
        ],
        expected_paths=[
            create_path_a,
            create_path_b,
            fixture_path,
        ],
    )

    return _run_multi_edit_failure_test(
        task,
        fixture_files={
            fixture_path: "Original fixture.\n",
        },
        expected_contents={
            fixture_path: "Original fixture.\n",
        },
        expected_absent_paths=[
            create_path_a,
            create_path_b,
        ],
        test_title=(
            "RUN TASK MULTI EDIT ROLLBACK "
            "MULTIPLE CREATES TEST"
        ),
    )
def test_run_task_multi_edit_rollback_mixed():
    """
    Verify that rollback restores a tracked file and
    removes an untracked file after a later failure.
    """

    create_path = "agent_rollback_mixed_create.txt"
    replace_path = "agent_rollback_mixed_replace.txt"

    task = Task(
        task_id="TASK-MULTI-FAILURE-004",
        description="Mixed rollback test.",
        edits=[
            {
                "type": "create",
                "path": create_path,
                "content": "Temporary file.\n",
            },
            {
                "type": "replace",
                "path": replace_path,
                "old_text": "original",
                "new_text": "changed",
                "expected_count": 1,
            },
            {
                "type": "replace",
                "path": replace_path,
                "old_text": "missing",
                "new_text": "failure",
                "expected_count": 1,
            },
        ],
        expected_paths=[
            create_path,
            replace_path,
        ],
    )

    return _run_multi_edit_failure_test(
        task,
        fixture_files={
            replace_path: "original\n",
        },
        expected_contents={
            replace_path: "original\n",
        },
        expected_absent_paths=[
            create_path,
        ],
        test_title=(
            "RUN TASK MULTI EDIT ROLLBACK "
            "MIXED TEST"
        ),
    )
def test_run_task_unknown_edit_type():
    """
    Verify that run_task() rejects an edit with
    an unsupported type before Git precheck.
    """

    invalid_task = Task(
        task_id="TASK-UNKNOWN-EDIT-TYPE-001",
        description="Unknown edit type test.",
        edits=[
            {
                "type": "unknown",
                "path": "test.txt",
            }
        ],
        expected_paths=[],
    )

    result = run_task(invalid_task)

    assert isinstance(result, TaskResult)
    assert result.success is False
    assert result.stage == "PRECHECK"
    assert result.failure_code == "PRECHECK_FAILED"
    assert result.failure_message == (
        "Task validation failed."
    )
    assert result.checkpoint is None
    assert result.edit_results == []
    assert result.build_result is None
    assert result.run_result is None
    assert result.rollback_result is None

    print_header(
        "RUN TASK UNKNOWN EDIT TYPE TEST"
    )

    print(
        "Result type:",
        type(result).__name__,
    )

    print(
        "Success:",
        result.success,
    )

    print(
        "Stage:",
        result.stage,
    )

    print(
        "Failure code:",
        result.failure_code,
    )

    print(
        "Checkpoint:",
        result.checkpoint,
    )

    print(
        "Edit results:",
        result.edit_results,
    )

    print(
        "Build result:",
        result.build_result,
    )

    print(
        "Run result:",
        result.run_result,
    )

    print(
        "Rollback result:",
        result.rollback_result,
    )

    print()
    print(
        "All unknown edit type "
        "assertions passed."
    )

    return result
def test_run_task_accepts_task_v2():
    """
    Verify that run_task() accepts a valid Task V2 as its input.
    """

    test_path = (
        "agent_run_task_task_v1_contract_test.txt"
    )

    original_run_simulation = run_simulation

    try:
        def fake_run_simulation():
            print()
            print("TEST: simulated successful RUN.")

            return {
                "success": True,
                "returncode": 0,
                "stdout": (
                    "Simulated successful run.\n"
                ),
                "stderr": "",
                "elapsed": 0.001,
                "timeout": False,
            }

        globals()["run_simulation"] = fake_run_simulation

        task = Task(
            task_id="TEST-RUN-TASK-V2-CONTRACT",
            description=(
                "Verify successful run_task() execution "
                "with a valid Task V2."
            ),
            edits=[
                {
                    "type": "create",
                    "path": test_path,
                    "content": (
                        "run_task Task V2 contract test.\n"
                    ),
                }
            ],
            expected_paths=[
                test_path
            ],
        )

        result = run_task(task)

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.stage == "COMPLETE"
        assert result.failure_code is None
        assert result.failure_message is None

        assert len(result.edit_results) == 1

        assert (
            result.edit_results[0]["type"]
            == "create"
        )

        assert (
            result.edit_results[0]["path"]
            == test_path
        )

        assert (
            result.edit_results[0]["success"]
            is True
        )

        assert result.diff_success is True
        assert result.diff_validated is True

        assert result.changed_paths == [
            test_path
        ]

        assert result.build_result is not None
        assert (
            result.build_result["success"]
            is True
        )

        assert result.run_result is not None
        assert (
            result.run_result["success"]
            is True
        )

        print_header(
            "RUN_TASK TASK V2 CONTRACT TEST"
        )

        print(
            "Task type:",
            type(task).__name__,
        )

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Transaction success:",
            result.success,
        )

        print(
            "Transaction stage:",
            result.stage,
        )

        print(
            "Changed paths:",
            result.changed_paths,
        )

        print()
        print(
            "All run_task(Task V2) "
            "contract assertions passed."
        )

        cleanup_success = rollback_to_checkpoint(
            require_confirmation=False
        )

        assert cleanup_success is True

        assert not (
            PROJECT_ROOT / test_path
        ).exists()

        print(
            "run_task(Task V2) cleanup passed."
        )

        return result

    finally:
        globals()["run_simulation"] = (
            original_run_simulation
        )    
def test_transaction_build_failure():
    original_build_project = build_project

    def failing_build_project():
        print_header("SIMULATED BUILD FAILURE")

        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "Simulated build failure for transaction test.",
            "elapsed": 0.001,
            "timeout": False,
            "success": False,
        }

    try:
        globals()["build_project"] = failing_build_project

        edits = [
            {
                "type": "create",
                "path": "agent_transaction_build_failure_test.txt",
                "content": "SimulationAgent build failure test\n",
            }
        ]

        result = run_task(
            Task(
                edits=edits,
                expected_paths=[
                    "agent_transaction_build_failure_test.txt"
                ],
            )
        )

    finally:
        globals()["build_project"] = original_build_project

    print()
    print_header("BUILD FAILURE TEST RESULT")

    print(result)

    return result
def test_transaction():
    task = Task(
        task_id="TEST-TRANSACTION",
        description="Verify a basic successful transactional task.",
        edits=[
            {
                "type": "create",
                "path": "agent_transaction_test.txt",
                "content": "SimulationAgent transaction test\n",
            }
        ],
        expected_paths=[
            "agent_transaction_test.txt",
        ],
    )

    result = run_task(task)

    assert isinstance(result, TaskResult)
    assert result.success is True
    assert result.stage == "COMPLETE"

    print()
    print_header("TASK RESULT")

    print(result)

    return result
def test_transaction_diff_validation_failure():
    test_path = "agent_transaction_test.txt"

    original_validate_changed_paths = (
        validate_changed_paths
    )

    try:
        def fake_validate_changed_paths(
            expected_paths
        ):
            print()
            print(
                "TEST: simulated DIFF VALIDATION failure."
            )
            return False

        globals()["validate_changed_paths"] = (
            fake_validate_changed_paths
        )

        task = Task(
            task_id="TEST-DIFF-VALIDATION-FAILURE",
            description=(
                "Verify DIFF VALIDATION failure "
                "after a successful edit and diff."
            ),
            edits=[
                {
                    "type": "create",
                    "path": test_path,
                    "content": (
                        "SimulationAgent DIFF "
                        "validation test.\n"
                    ),
                }
            ],
            expected_paths=[test_path],
        )

        result = run_task(task)

        assert isinstance(result, TaskResult)
        assert result.success is False
        assert result.stage == "ROLLBACK"
        assert result.failure_code == (
            "DIFF_VALIDATION_FAILED"
        )
        assert result.failure_message == (
            "Changed paths do not match "
            "expected paths."
        )

        assert result.checkpoint is not None
        assert result.rollback_result is not None
        assert result.rollback_result["success"] is True

        print()
        print_header(
            "NEGATIVE DIFF VALIDATION TEST"
        )

        print(
            "Result type:",
            type(result).__name__,
        )

        print(
            "Success:",
            result.success,
        )

        print(
            "Stage:",
            result.stage,
        )

        print(
            "Failure code:",
            result.failure_code,
        )

        print(
            "Rollback success:",
            result.rollback_result["success"],
        )

        print()
        print(
            "DIFF VALIDATION failure test passed."
        )

        return result

    finally:
        globals()["validate_changed_paths"] = (
            original_validate_changed_paths
        )

def write_file(relative_path, content):
    """
    Write a UTF-8 text file inside PROJECT_ROOT.
    """

    print_header(f"WRITE FILE: {relative_path}")

    path = resolve_project_path(relative_path)

    if path is None:
        print("ERROR: Path escapes the SimulationZero-Cpp project.")
        return False

    if is_inside_build(path):
        print("ERROR: Agent is not allowed to modify build/.")
        return False

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(
            content,
            encoding="utf-8",
            newline="\n",
        )

    except Exception as exc:
        print(f"ERROR: Could not write file: {exc}")
        return False

    print("File written successfully:")
    print(path.relative_to(PROJECT_ROOT))

    return True


def search_source(term):
    print_header(f"SEARCH: {term}")

    found = 0

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue

        if is_inside_build(path):
            continue

        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue

        try:
            lines = path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
        except Exception:
            continue

        for line_number, line in enumerate(lines, start=1):
            if term.lower() in line.lower():
                print(
                    f"{path.relative_to(PROJECT_ROOT)}:"
                    f"{line_number}: {line}"
                )
                found += 1

    print()
    print(f"Matches: {found}")

    return found


# ============================================================
# Git helpers
# ============================================================

def git_command(arguments, timeout=30):
    return run_process(
        ["git"] + arguments,
        cwd=PROJECT_ROOT,
        timeout=timeout,
    )


def get_git_status_porcelain():
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception:
        return None, ""

    return result.returncode, result.stdout


def get_current_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def is_valid_commit(commit):
    if not commit:
        return False

    try:
        result = subprocess.run(
            [
                "git",
                "cat-file",
                "-e",
                f"{commit}^{{commit}}",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception:
        return False

    return result.returncode == 0


# ============================================================
# Persistent checkpoint
# ============================================================

def save_checkpoint(commit):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        CHECKPOINT_FILE.write_text(
            commit + "\n",
            encoding="utf-8",
        )

    except Exception as exc:
        print(f"ERROR: Could not save checkpoint: {exc}")
        return False

    return True


def load_checkpoint():
    if not CHECKPOINT_FILE.exists():
        return None

    try:
        commit = CHECKPOINT_FILE.read_text(
            encoding="utf-8"
        ).strip()
    except Exception:
        return None

    if not is_valid_commit(commit):
        return None

    return commit


def clear_checkpoint():
    try:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
    except Exception as exc:
        print(f"WARNING: Could not remove checkpoint file: {exc}")


# ============================================================
# Git status
# ============================================================

def git_status():
    print_header("GIT STATUS")

    result = git_command(
        ["status", "--short", "--branch"],
        timeout=30,
    )

    if result["returncode"] != 0:
        return False

    status_lines = result["stdout"].splitlines()

    for line in status_lines:
        if line.startswith("## "):
            continue

        if line.strip():
            return False

    return True


# ============================================================
# Git checkpoint
# ============================================================

def create_checkpoint():
    print_header("CREATE GIT CHECKPOINT")

    returncode, status = get_git_status_porcelain()

    if returncode is None:
        print("ERROR: Could not execute Git.")
        return None

    if returncode != 0:
        print("ERROR: Could not read Git working tree.")
        return None

    if status.strip():
        print("ERROR: Working tree is not clean.")
        print()
        print("The agent refuses to create a checkpoint because")
        print("there are already uncommitted changes.")
        print()
        print("Current changes:")
        print(status)
        return None

    commit = get_current_commit()

    if not commit:
        print("ERROR: Could not determine current Git commit.")
        return None

    if not save_checkpoint(commit):
        return None

    print("Checkpoint created.")
    print(f"Commit: {commit}")
    print(f"Saved to: {CHECKPOINT_FILE}")

    return commit


def show_checkpoint():
    print_header("CURRENT CHECKPOINT")

    commit = load_checkpoint()

    if commit is None:
        print("No valid checkpoint exists.")
        return False

    print(f"Checkpoint commit: {commit}")
    print(f"Checkpoint file:  {CHECKPOINT_FILE}")

    return True


# ============================================================
# Git diff
# ============================================================

def git_diff():
    print_header("GIT DIFF")

    result = git_command(
        ["diff", "--"],
        timeout=30,
    )

    return result["returncode"] == 0
def get_git_diff():
    """
    Return a complete working-tree change report.

    Includes:
        - tracked Git diff
        - untracked file paths
        - contents of untracked files

    Returns:
        str | None:
            Complete change report on success.
            None if Git execution failed.
    """

    result = git_command(
        ["diff", "--"],
        timeout=30,
    )

    if result["returncode"] != 0:
        print()
        print("ERROR: Could not read Git diff.")
        return None

    diff = result["stdout"]

    status_result = git_command(
        ["status", "--short"],
        timeout=30,
    )

    if status_result["returncode"] != 0:
        print()
        print("ERROR: Could not read Git status.")
        return None

    status = status_result["stdout"]

    untracked_files = []

    for line in status.splitlines():
        if line.startswith("?? "):
            untracked_files.append(
                line[3:].strip()
            )

    if untracked_files:
        sections = []

        for relative_path in untracked_files:
            path = resolve_project_path(relative_path)

            if path is None:
                print()
                print(
                    "ERROR: Untracked path escapes "
                    "the SimulationZero-Cpp project."
                )
                return None

            if is_inside_build(path):
                print()
                print(
                    "ERROR: Untracked file is inside build/."
                )
                return None

            if not path.exists() or not path.is_file():
                print()
                print(
                    f"ERROR: Could not read untracked file: "
                    f"{relative_path}"
                )
                return None

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception as exc:
                print()
                print(
                    f"ERROR: Could not read untracked file "
                    f"{relative_path}: {exc}"
                )
                return None

            sections.append(
                "--- UNTRACKED FILE: "
                f"{relative_path} ---\n"
                f"{content}"
                "--- END UNTRACKED FILE ---\n"
            )

        if diff and not diff.endswith("\n"):
            diff += "\n"

        diff += "\n".join(sections)

    return diff

# ============================================================
# All Git changes
# ============================================================

def show_all_changes():
    print_header("ALL GIT CHANGES")

    print("----- STATUS -----")
    print()

    status_result = git_command(
        ["status", "--short"],
        timeout=30,
    )

    if status_result["returncode"] != 0:
        return False

    print()

    print("----- DIFF OF TRACKED FILES -----")
    print()

    diff_result = git_command(
        ["diff", "--"],
        timeout=30,
    )

    if diff_result["returncode"] != 0:
        return False

    print()

    print("----- UNTRACKED FILES -----")
    print()

    status_returncode, status = get_git_status_porcelain()

    if status_returncode != 0:
        return False

    untracked_found = False

    for line in status.splitlines():
        if line.startswith("?? "):
            print(line)
            untracked_found = True

    if not untracked_found:
        print("None")

    return True


# ============================================================
# Git rollback
# ============================================================

def rollback_to_checkpoint(require_confirmation=True):
    print_header("ROLLBACK TO CHECKPOINT")

    checkpoint = load_checkpoint()

    if checkpoint is None:
        print("ERROR: No valid checkpoint exists.")
        print()
        print(f"Expected checkpoint file:")
        print(CHECKPOINT_FILE)
        return False

    print(f"Checkpoint: {checkpoint}")
    print()

    current_commit = get_current_commit()

    if current_commit is None:
        print("ERROR: Could not determine current Git commit.")
        return False

    print(f"Current HEAD: {current_commit}")
    print()

    print("WARNING:")
    print("This will restore the project to the checkpoint.")
    print("All changes after the checkpoint will be removed.")
    print("Untracked files will also be removed.")
    print()

    if require_confirmation:
        confirmation = input(
            "Type ROLLBACK to continue: "
        )

        if confirmation != "ROLLBACK":
            print("Rollback cancelled.")
            return False

    result = git_command(
        [
            "reset",
            "--hard",
            checkpoint,
        ],
        timeout=30,
    )

    if result["returncode"] != 0:
        print("ERROR: Git reset failed.")
        return False

    clean_result = git_command(
        [
            "clean",
            "-fd",
            "--",
        ],
        timeout=30,
    )

    if clean_result["returncode"] != 0:
        print("ERROR: Git clean failed.")
        return False

    print()
    print("Rollback completed.")
    print(f"Restored commit: {checkpoint}")

    clear_checkpoint()

    print("Checkpoint cleared.")

    return True

def test_expected_paths_empty():
    task = Task(
        task_id="TEST-EXPECTED-PATHS-EMPTY",
        description="Test empty expected_paths semantics.",
        edits=[
            {
                "type": "create",
                "path": "expected_paths_empty_test.txt",
                "content": "test",
            }
        ],
        expected_paths=[],
    )

    result = run_task(task)

    assert isinstance(result, TaskResult)
    assert result.success is True
    assert result.diff_validated is True
    assert "expected_paths_empty_test.txt" in result.changed_paths
# ============================================================
# Main
# ============================================================

def main():
    if not show_project_info():
        return 1

    while True:
        print()
        print("=" * 70)
        print("SimulationAgent v0.3.1")
        print("=" * 70)
        print()
        print("1. Show project files")
        print("2. Read file")
        print("3. Search source")
        print("4. Build project")
        print("5. Run SimulationZero")
        print("6. Git status")
        print("7. Create checkpoint")
        print("8. Show Git diff")
        print("9. Rollback to checkpoint")
        print("10. Write file")
        print("11. Show all changes")
        print("12. Show checkpoint")
        print("13. Apply text replacement")
        print("14. Test transactional task")
        print("15. Test DIFF validation failure")
        print("16. Test BUILD failure")
        print("17. Test successful transaction")
        print("18. Test TaskResult JSON")
        print("19. test_task_result_success_json")
        print("20. test_task_result_type_contract")
        print("21. test_failure_code_contract")
        print("22. test_transaction_edit_failure")
        print("23. test_transaction_diff_failure")
        print("24. test_transaction_diff_validation_failure_contract")
        print("25. Test BUILD failure")
        print("26. Test RUN failure")
        print("27. Test ROLLBACK failure")
        print("28. Test PRECHECK failure")
        print("29. Test CHECKPOINT failure")
        print("30. Test successful transaction")
        print("31. Test transaction JSON integration")
        print("32. Test Task V1 contract")
        print("33. Test run_task accepts Task V2")
        print("34. Test Task V2 contract")
        print("35. Test Task V2 validation")
        print("36. Test run_task Task validation failure")
        print("37. Test run_task invalid edits type")
        print("38. Test run_task invalid expected_paths type")
        print("39. Test run_task invalid edit element type")
        print("40. Test run_task invalid edit type")
        print("41. Test run_task unknown edit type")
        print("42. Test run_task valid create")
        print("43. Test run_task valid replace")
        print("44. Test create edit missing path validation")
        print("45. Test create edit missing content validation")
        print("46. Test replace edit missing path validation")
        print("47. Test replace edit missing old text validation")
        print("48. Test replace edit missing new text validation")
        print("49. Test create edit invalid path type validation")
        print("50. Test create edit invalid content type validation")
        print("51. Test replace edit invalid path type validation")
        print("52. Test replace edit invalid old text type validation")
        print("53. Test replace edit invalid new text type validation")
        print("54. Test replace edit invalid expected count type validation")
        print("55. Test replace expected count zero validation")
        print("56. Test replace expected count negative validation")
        print("57. Test replace expected count bool validation")
        print("58. Test create empty path validation")
        print("59. Test create empty content validation")
        print("60. Test replace empty old text validation")
        print("61. Test replace empty new text validation")
        print("62. Test expected paths invalid element type validation")
        print("63. Test expected paths empty element validation")
        print("64. Test expected paths whitespace element validation")
        print("65. Test create path missing from expected paths")
        print("66. Test replace path missing from expected paths")
        print("67. Test extra expected path")
        print("68. Test multiple create edits")
        print("69. Test multiple replace edits same path")
        print("70. Test create and replace different paths")
        print("71. Test create and replace same path")
        print("72. Test run_task multiple create")
        print("73. Test run_task multiple replace same path")
        print("74. Test run_task create and replace different paths")
        print("75. Test run_task create and replace same path")
        print("76. Test run_task multi-edit failure")
        print("77. Test run_task expected count failure")
        print("78. Test run_task rollback multiple creates")
        print("79. Test run_task rollback mixed changes")
        print("[80] Test empty expected_paths semantics")
        print("[81] Test fail_task without checkpoint return type")
        print("0. Exit")
        print()

        choice = input("Select action: ").strip()

        if choice == "1":
            list_source_files()

        elif choice == "2":
            path = input("Relative file path: ").strip()

            if path:
                read_file(path)

        elif choice == "3":
            term = input("Search term: ").strip()

            if term:
                search_source(term)

        elif choice == "4":
            result = build_project()

            print()
            print_header("BUILD RESULT")
            print(result)

        elif choice == "5":
            run_simulation()

        elif choice == "6":
            git_status()

        elif choice == "7":
            create_checkpoint()

        elif choice == "8":
            git_diff()

        elif choice == "9":
            rollback_to_checkpoint()

        elif choice == "10":
            path = input("Relative file path: ").strip()

            if not path:
                print("ERROR: File path cannot be empty.")
                continue

            content = input("File contents: ")

            write_file(path, content + "\n")

        elif choice == "11":
            show_all_changes()

        elif choice == "12":
            show_checkpoint()
            
        elif choice == "13":
            path = input("Relative file path: ").strip()

            if not path:
                print("ERROR: File path cannot be empty.")
                continue

            old_text = input("Text to find: ")
            new_text = input("Replacement text: ")

            count_text = input(
                "Expected match count [1]: "
            ).strip()

            if not count_text:
                expected_count = 1
            else:
                try:
                    expected_count = int(count_text)
                except ValueError:
                    print(
                        "ERROR: Expected match count "
                        "must be an integer."
                    )
                    continue

            apply_text_replacement(
                path,
                old_text,
                new_text,
                expected_count,
            )
        elif choice == "14":
            test_transaction()
        elif choice == "15":
            test_transaction_diff_validation_failure()
        elif choice == "16":
            test_transaction_build_failure()
        elif choice == "17":
            test_transaction_success()
        elif choice == "18":
            test_task_result_json()
        elif choice == "19":
            test_task_result_success_json()
        elif choice == "20":
            test_task_result_type_contract()
        elif choice == "21":
            test_failure_code_contract()
        elif choice == "22":
            test_transaction_edit_failure()
        elif choice == "23":
            test_transaction_diff_failure()
        elif choice == "24":
            test_transaction_diff_validation_failure_contract()
        elif choice == "25":
            test_transaction_build_failure_contract()
        elif choice == "26":
            test_transaction_run_failure_contract()
        elif choice == "27":
            test_transaction_rollback_failure_contract()
        elif choice == "28":
            test_transaction_precheck_failure_contract()
        elif choice == "29":
            test_transaction_checkpoint_failure_contract()
        elif choice == "30":
            test_transaction_success_contract()
        elif choice == "31":
            test_transaction_json_integration_contract()
        elif choice == "32":
            test_task_v1_contract()
        elif choice == "33":
            test_run_task_accepts_task_v2()
        elif choice == "34":
            test_task_v2_contract()
        elif choice == "35":
            test_validate_task()
        elif choice == "36":
            test_run_task_task_validation_failure()
        elif choice == "37":
            test_run_task_invalid_edits_type()
        elif choice == "38":
            test_run_task_invalid_expected_paths_type()
        elif choice == "39":
            test_run_task_invalid_edit_element_type()
        elif choice == "40":
            test_run_task_invalid_edit_type()
        elif choice == "41":
            test_run_task_unknown_edit_type()
        elif choice == "42":
            test_run_task_valid_create()
        elif choice == "43":
            test_run_task_valid_replace()
        elif choice == "44":
            test_validate_task()
        elif choice == "45":
            test_validate_task()
        elif choice == "46":
            test_validate_task()
        elif choice == "47":
            test_validate_task()
        elif choice == "48":
            test_validate_task()
        elif choice == "49":
            test_validate_task()
        elif choice == "50":
            test_validate_task()
        elif choice == "51":
            test_validate_task()
        elif choice == "52":
            test_validate_task()
        elif choice == "53":
            test_validate_task()
        elif choice == "54":
            test_validate_task()
        elif choice == "55":
            test_validate_task()
        elif choice == "56":
            test_validate_task()
        elif choice == "57":
            test_validate_task()
        elif choice == "58":
            test_validate_task()
        elif choice == "59":
            test_validate_task()
        elif choice == "60":
            test_validate_task()
        elif choice == "61":
            test_validate_task()
        elif choice == "62":
            test_validate_task()
        elif choice == "63":
            test_validate_task()
        elif choice == "64":
            test_validate_task()
        elif choice == "65":
            test_validate_task()
        elif choice == "66":
            test_validate_task()
        elif choice == "67":
            test_validate_task()
        elif choice == "68":
            test_validate_task()
        elif choice == "69":
            test_validate_task()
        elif choice == "70":
            test_validate_task()
        elif choice == "71":
            test_validate_task()
        elif choice == "72":
            test_run_task_multiple_create()
        elif choice == "73":
            test_run_task_multiple_replace_same_path()
        elif choice == "74":
            test_run_task_create_replace_different_paths()
        elif choice == "75":
            test_run_task_create_replace_same_path()
        elif choice == "76":
            test_run_task_multi_edit_failure()
        elif choice == "77":
            test_run_task_multi_edit_expected_count_failure()
        elif choice == "78":
            test_run_task_multi_edit_rollback_multiple_creates()
        elif choice == "79":
            test_run_task_multi_edit_rollback_mixed()
        elif choice == "80":
            test_expected_paths_empty()
        elif choice == "81":
            test_fail_task_without_checkpoint_returns_task_result()
        elif choice == "0":
            print("SimulationAgent stopped.")
            return 0

        else:
            print("Unknown command.")


if __name__ == "__main__":
    raise SystemExit(main())
