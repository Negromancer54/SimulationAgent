import json
import struct
import subprocess
import sys
from pathlib import Path
from browser_harness import BrowserHarness

CONTRACT_FILE = Path(
    r"C:\Users\Gycha\SimulationAgent\bridge\tests\bridge_test_contract.json"
)

HOST_CMD = Path(
    r"C:\Users\Gycha\SimulationAgent\bridge\native_host\host.cmd"
)
PROJECT_ROOT = Path(
    r"C:\Users\Gycha\SimulationZero-Cpp"
)

CHECKPOINT_FILE = Path(
    r"C:\Users\Gycha\SimulationAgent\state\checkpoint"
)

REQUIRED_TEST_FIELDS = {
    "id",
    "name",
    "level",
    "regression",
    "setup",
    "input",
    "actions",
    "expected",
    "invariants",
    "oracle",
    "metrics",
    "pass_criteria",
}


VALID_LEVELS = {
    "B",
    "P",
    "E",
    "PA",
}


def load_contract():
    if not CONTRACT_FILE.exists():
        raise FileNotFoundError(
            f"Contract file not found: {CONTRACT_FILE}"
        )

    with CONTRACT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def validate_contract(contract):
    errors = []

    if not isinstance(contract, dict):
        errors.append(
            "Contract root must be an object."
        )
        return errors

    if contract.get("schema_version") != 1:
        errors.append(
            "schema_version must be 1."
        )

    if contract.get("contract") != "Bridge Test Contract":
        errors.append(
            "contract must be 'Bridge Test Contract'."
        )

    if contract.get("version") != "0.1":
        errors.append(
            "version must be '0.1'."
        )

    levels = contract.get("levels")

    if not isinstance(levels, dict):
        errors.append(
            "levels must be an object."
        )
    else:
        for level in VALID_LEVELS:
            if level not in levels:
                errors.append(
                    f"Missing level definition: {level}"
                )

    tests = contract.get("tests")

    if not isinstance(tests, list):
        errors.append(
            "tests must be an array."
        )
        return errors

    seen_ids = set()

    for index, test in enumerate(tests):
        prefix = f"tests[{index}]"

        if not isinstance(test, dict):
            errors.append(
                f"{prefix} must be an object."
            )
            continue

        missing_fields = (
            REQUIRED_TEST_FIELDS
            - set(test.keys())
        )

        for field in sorted(missing_fields):
            errors.append(
                f"{prefix} missing required field: {field}"
            )

        test_id = test.get("id")

        if not isinstance(
            test_id,
            str
        ) or not test_id:
            errors.append(
                f"{prefix}.id must be a non-empty string."
            )
        else:
            if test_id in seen_ids:
                errors.append(
                    f"Duplicate test id: {test_id}"
                )

            seen_ids.add(test_id)

        level = test.get("level")

        if level not in VALID_LEVELS:
            errors.append(
                f"{prefix}.level must be one of "
                f"{sorted(VALID_LEVELS)}."
            )

        if (
            isinstance(test_id, str)
            and test_id
            and level in VALID_LEVELS
        ):
            expected_prefix = f"{level}-"

            if not test_id.startswith(
                expected_prefix
            ):
                errors.append(
                    f"{prefix}.id '{test_id}' does not match "
                    f"level '{level}'."
                )

        if not isinstance(
            test.get("regression"),
            bool
        ):
            errors.append(
                f"{prefix}.regression must be boolean."
            )

        for field in (
            "setup",
            "input",
            "expected",
            "oracle",
            "metrics",
        ):
            if not isinstance(
                test.get(field),
                dict
            ):
                errors.append(
                    f"{prefix}.{field} must be an object."
                )

        for field in (
            "actions",
            "invariants",
            "pass_criteria",
        ):
            if not isinstance(
                test.get(field),
                list
            ):
                errors.append(
                    f"{prefix}.{field} must be an array."
                )

        if isinstance(
            test.get("actions"),
            list
        ):
            if len(test["actions"]) == 0:
                errors.append(
                    f"{prefix}.actions must not be empty."
                )

        if isinstance(
            test.get("pass_criteria"),
            list
        ):
            if len(test["pass_criteria"]) == 0:
                errors.append(
                    f"{prefix}.pass_criteria must not be empty."
                )

    return errors


def print_summary(contract):
    tests = contract["tests"]

    counts = {
        "B": 0,
        "P": 0,
        "E": 0,
        "PA": 0,
    }

    regression_count = 0

    for test in tests:
        level = test["level"]
        counts[level] += 1

        if test["regression"]:
            regression_count += 1

    print()
    print("=" * 70)
    print("BRIDGE TEST CONTRACT VALIDATION")
    print("=" * 70)
    print()
    print(
        f"Contract: {contract['contract']}"
    )
    print(
        f"Version: {contract['version']}"
    )
    print(
        f"Schema version: {contract['schema_version']}"
    )
    print()
    print(
        f"Total tests: {len(tests)}"
    )
    print(
        f"B tests: {counts['B']}"
    )
    print(
        f"P tests: {counts['P']}"
    )
    print(
        f"E tests: {counts['E']}"
    )
    print(
        f"PA tests: {counts['PA']}"
    )
    print(
        f"Regression tests: {regression_count}"
    )
    print()


def encode_native_message(message):
    payload = json.dumps(
        message,
        ensure_ascii=False
    ).encode("utf-8")

    return (
        struct.pack(
            "<I",
            len(payload)
        )
        + payload
    )


def write_native_message(process, message):
    encoded = encode_native_message(
        message
    )

    process.stdin.write(encoded)
    process.stdin.flush()


def read_native_message(process):
    raw_length = process.stdout.read(4)

    if len(raw_length) != 4:
        raise RuntimeError(
            "Native host closed stdout before sending message length."
        )

    message_length = struct.unpack(
        "<I",
        raw_length
    )[0]

    raw_message = process.stdout.read(
        message_length
    )

    if len(raw_message) != message_length:
        raise RuntimeError(
            "Native host closed stdout before sending complete message."
        )

    return json.loads(
        raw_message.decode("utf-8")
    )


def start_native_host():
    if not HOST_CMD.exists():
        raise FileNotFoundError(
            f"Native host command not found: {HOST_CMD}"
        )

    return subprocess.Popen(
        [
            str(HOST_CMD)
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def stop_native_host(process):
    if process.poll() is None:
        process.terminate()

        try:
            process.wait(
                timeout=5
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run_native_request(message):
    process = start_native_host()

    try:
        write_native_message(
            process,
            message
        )

        return read_native_message(
            process
        )

    finally:
        stop_native_host(
            process
        )
def run_native_sequence(messages):
    process = start_native_host()

    responses = []

    try:
        for message in messages:
            write_native_message(
                process,
                message
            )

            response = read_native_message(
                process
            )

            responses.append(
                response
            )

        return responses

    finally:
        stop_native_host(
            process
        )
def get_git_status():
    result = subprocess.run(
        [
            "git",
            "-C",
            str(PROJECT_ROOT),
            "status",
            "--porcelain",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Failed to query Git status: "
            + result.stderr.strip()
        )

    return result.stdout.strip()


def ensure_project_clean():
    status = get_git_status()

    if status:
        raise RuntimeError(
            "SimulationZero-Cpp working tree is not clean:\n"
            + status
        )

    if CHECKPOINT_FILE.exists():
        raise RuntimeError(
            "SimulationAgent checkpoint already exists:\n"
            + str(CHECKPOINT_FILE)
        )

    return True


def cleanup_transaction_state():
    status = get_git_status()

    if status:
        raise RuntimeError(
            "Cannot cleanup transaction state because "
            "working tree is not clean:\n"
            + status
        )

    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
def remove_test_file(relative_path):
    path = PROJECT_ROOT / relative_path

    if path.exists():
        if not path.is_file():
            raise RuntimeError(
                f"Test cleanup target is not a file: {path}"
            )

        path.unlink()


def cleanup_p03_state(relative_path):
    remove_test_file(relative_path)

    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
def get_test_by_id(contract, test_id):
    for test in contract["tests"]:
        if test["id"] == test_id:
            return test

    raise KeyError(
        f"Test not found: {test_id}"
    )

def get_value_by_path(data, path):
    current = data

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        if part not in current:
            return None

        current = current[part]

    return current
def assert_oracle(response, oracle):
    for path, expected in oracle.items():
        actual = get_value_by_path(
            {
                "response": response
            },
            path
        )

        if expected == "non-empty":
            if not actual:
                return False, (
                    f"Oracle failed at {path}: "
                    "expected non-empty value."
                )

            continue

        if actual != expected:
            return False, (
                f"Oracle failed at {path}: "
                f"expected {expected!r}, "
                f"got {actual!r}."
            )

    return True, "PASS"
def run_native_test(test):
    message = test["input"]["message"]

    response = run_native_request(
        message
    )

    return assert_oracle(
        response,
        test["oracle"]
    )
def run_p01(test):
    return run_native_test(test)
def run_p02(test):
    return run_native_test(test)
def run_p03(test):
    message = test["input"]["message"]

    task = message["task"]
    probe_path = task["edits"][0]["path"]

    try:
        response = run_native_request(
            message
        )

        oracle = test["oracle"]

        if response.get("type") != (
            oracle["response.type"]
        ):
            return False, (
                "Unexpected response type: "
                f"{response.get('type')}"
            )

        if response.get("task_id") != (
            oracle["response.task_id"]
        ):
            return False, (
                "Unexpected task_id: "
                f"{response.get('task_id')}"
            )

        result = response.get("result")

        if not isinstance(result, dict):
            return False, (
                "Response result is not an object."
            )

        if result.get("success") != (
            oracle["response.result.success"]
        ):
            return False, (
                "Unexpected TaskResult.success: "
                f"{result.get('success')}"
            )

        if result.get("stage") != (
            oracle["response.result.stage"]
        ):
            return False, (
                "Unexpected TaskResult.stage: "
                f"{result.get('stage')}"
            )

        if result.get("diff_validated") != (
            oracle["response.result.diff_validated"]
        ):
            return False, (
                "Unexpected diff_validated: "
                f"{result.get('diff_validated')}"
            )

        probe = PROJECT_ROOT / probe_path

        if not probe.exists():
            return False, (
                f"Expected probe file was not created: {probe_path}"
            )

        return True, "PASS"

    finally:
        cleanup_p03_state(
            probe_path
        )
def run_p04(test):
    return run_native_test(test)
def run_p05(test):
    return run_native_test(test)
def run_p06(test):
    probe_path = (
        test["input"]["message"]["task"]["edits"][0]["path"]
    )

    try:
        return run_native_test(test)

    finally:
        cleanup_p03_state(
            probe_path
        )


def run_p07(test):
    probe_path = (
        test["input"]["message"]["task"]["edits"][0]["path"]
    )

    try:
        return run_native_test(test)

    finally:
        cleanup_p03_state(
            probe_path
        )
def run_p08(test):
    return run_native_test(test)
def run_p09(test):
    return run_native_test(test)
def run_p10(test):
    messages = test["input"]["messages"]

    if len(messages) != 2:
        return False, (
            f"Expected two task messages, got {len(messages)}."
        )

    first_task = messages[0]["task"]
    second_task = messages[1]["task"]

    first_probe = first_task["edits"][0]["path"]
    second_probe = second_task["edits"][0]["path"]

    process = start_native_host()

    responses = []

    try:
        # First task.
        write_native_message(
            process,
            messages[0]
        )

        first_response = read_native_message(
            process
        )

        responses.append(
            first_response
        )

        first_result = first_response.get("result")

        if not isinstance(first_result, dict):
            return False, (
                "First task result is not an object."
            )

        if first_response.get("type") != "task_result":
            return False, (
                "Unexpected first response type: "
                f"{first_response.get('type')}"
            )

        if first_response.get("task_id") != (
            first_task["task_id"]
        ):
            return False, (
                "Unexpected first task_id: "
                f"{first_response.get('task_id')}"
            )

        if first_result.get("success") is not True:
            return False, (
                "First task did not complete successfully: "
                f"{first_result.get('success')}"
            )

        # The first successful transaction leaves the project dirty.
        # Clean only the artifacts created by this test.
        cleanup_p03_state(
            first_probe
        )

        if get_git_status():
            return False, (
                "Project is not clean after first task cleanup."
            )

        if CHECKPOINT_FILE.exists():
            return False, (
                "Checkpoint still exists after first task cleanup."
            )

        # Second task, same native host process.
        write_native_message(
            process,
            messages[1]
        )

        second_response = read_native_message(
            process
        )

        responses.append(
            second_response
        )

        second_result = second_response.get("result")

        if not isinstance(second_result, dict):
            return False, (
                "Second task result is not an object."
            )

        if second_response.get("type") != "task_result":
            return False, (
                "Unexpected second response type: "
                f"{second_response.get('type')}"
            )

        if second_response.get("task_id") != (
            second_task["task_id"]
        ):
            return False, (
                "Unexpected second task_id: "
                f"{second_response.get('task_id')}"
            )

        if second_result.get("success") is not True:
            return False, (
                "Second task did not complete successfully: "
                f"{second_result.get('success')}"
            )

        second_probe_file = PROJECT_ROOT / second_probe

        if not second_probe_file.exists():
            return False, (
                "Second probe file was not created: "
                f"{second_probe}"
            )

        return True, "PASS"

    finally:
        remove_test_file(first_probe)
        remove_test_file(second_probe)

        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()

        stop_native_host(
            process
        )
def run_e01(test):
    message = test["input"]

    task = message["task"]
    probe_path = task["edits"][0]["path"]

    request_id = message["request_id"]

    try:
        with BrowserHarness(timeout=10) as browser:
            target = browser.find_chatgpt_page()

            if target.get("type") != "page":
                return False, (
                    "Unexpected browser target type: "
                    f"{target.get('type')}"
                )

            if target.get("url") != "https://chatgpt.com/":
                return False, (
                    "Unexpected browser target URL: "
                    f"{target.get('url')}"
                )

            browser.clear_page_messages()

            browser.send_page_message(
                message
            )

            response = browser.wait_for_page_message(
                source="simulationagent-bridge",
                message_type="task_response",
                request_id=request_id,
                timeout=30,
            )

        oracle = test["oracle"]

        if response.get("source") != "simulationagent-bridge":
            return False, (
                "Unexpected response source: "
                f"{response.get('source')}"
            )

        if response.get("type") != oracle["response.type"]:
            return False, (
                "Unexpected response type: "
                f"{response.get('type')}"
            )

        if response.get("request_id") != oracle["response.request_id"]:
            return False, (
                "Unexpected request_id: "
                f"{response.get('request_id')}"
            )

        if response.get("success") != oracle["response.success"]:
            return False, (
                "Unexpected bridge success: "
                f"{response.get('success')}"
            )

        result = response.get("result")

        if not isinstance(result, dict):
            return False, (
                "Response result is not an object."
            )

        if result.get("success") != oracle["response.result.success"]:
            return False, (
                "Unexpected TaskResult.success: "
                f"{result.get('success')}"
            )

        if result.get("stage") != oracle["response.result.stage"]:
            return False, (
                "Unexpected TaskResult.stage: "
                f"{result.get('stage')}"
            )

        if result.get("diff_validated") != (
            oracle["response.result.diff_validated"]
        ):
            return False, (
                "Unexpected diff_validated: "
                f"{result.get('diff_validated')}"
            )

        if result.get("rollback_result") != (
            oracle["response.result.rollback_result"]
        ):
            return False, (
                "Unexpected rollback_result: "
                f"{result.get('rollback_result')}"
            )

        probe = PROJECT_ROOT / probe_path

        if not probe.exists():
            return False, (
                f"Expected probe file was not created: {probe_path}"
            )

        return True, "PASS"

    finally:
        cleanup_p03_state(
            probe_path
        )
def run_e02(test):
    message = test["input"]
    request_id = message["request_id"]

    try:
        with BrowserHarness(timeout=10) as browser:
            target = browser.find_chatgpt_page()

            if target.get("type") != "page":
                return False, (
                    "Unexpected browser target type: "
                    f"{target.get('type')}"
                )

            if target.get("url") != "https://chatgpt.com/":
                return False, (
                    "Unexpected browser target URL: "
                    f"{target.get('url')}"
                )

            browser.clear_page_messages()

            browser.send_page_message(
                message
            )

            response = browser.wait_for_page_message(
                source="simulationagent-bridge",
                message_type="task_response",
                request_id=request_id,
                timeout=30,
            )

        oracle = test["oracle"]

        if response.get("source") != (
            oracle["response.source"]
        ):
            return False, (
                "Unexpected response source: "
                f"{response.get('source')}"
            )

        if response.get("type") != (
            oracle["response.type"]
        ):
            return False, (
                "Unexpected response type: "
                f"{response.get('type')}"
            )

        if response.get("request_id") != (
            oracle["response.request_id"]
        ):
            return False, (
                "Unexpected request_id: "
                f"{response.get('request_id')}"
            )

        if response.get("success") != (
            oracle["response.success"]
        ):
            return False, (
                "Unexpected bridge success: "
                f"{response.get('success')}"
            )

        error = response.get("error")

        if not isinstance(error, dict):
            return False, (
                "Bridge error is not an object."
            )

        if error.get("code") != (
            oracle["response.error.code"]
        ):
            return False, (
                "Unexpected bridge error code: "
                f"{error.get('code')}"
            )

        if CHECKPOINT_FILE.exists():
            return False, (
                "Checkpoint was created for rejected Bridge request."
            )

        if get_git_status():
            return False, (
                "Project repository changed after rejected "
                "Bridge request."
            )

        return True, "PASS"

    finally:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
def run_pa01(test):
    message = test["input"]
    task = message["task"]
    probe_path = task["edits"][0]["path"]

    expression = f"""
    (async () => {{
        if (
            !window.SimulationAgentBridge ||
            typeof window.SimulationAgentBridge.sendTask !== "function"
        ) {{
            throw new Error(
                "SimulationAgentBridge.sendTask is not available."
            );
        }}

        const task = {json.dumps(task, ensure_ascii=False)};

        const promise =
            window.SimulationAgentBridge.sendTask(task);

        const isPromise =
            promise instanceof Promise;

        const result =
            await promise;

        return {{
            isPromise: isPromise,
            result: result
        }};
    }})()
    """

    try:
        with BrowserHarness(timeout=10) as browser:
            result = browser.evaluate(
                expression,
                await_promise=True,
            )

        oracle = test["oracle"]

        if not isinstance(result, dict):
            return False, (
                "Page API did not return a diagnostic object."
            )

        if result.get("isPromise") is not True:
            return False, (
                "SimulationAgentBridge.sendTask() "
                "did not return a Promise."
            )

        result = result.get("result")

        if not isinstance(result, dict):
            return False, (
                "Page API did not return a TaskResult object."
            )

        if result.get("success") != (
            oracle["result_success"]
        ):
            return False, (
                "Unexpected TaskResult.success: "
                f"{result.get('success')}"
            )

        if result.get("stage") != (
            oracle["result_stage"]
        ):
            return False, (
                "Unexpected TaskResult.stage: "
                f"{result.get('stage')}"
            )

        if result.get("diff_validated") != (
            oracle["result_diff_validated"]
        ):
            return False, (
                "Unexpected diff_validated: "
                f"{result.get('diff_validated')}"
            )

        if result.get("rollback_result") != (
            oracle["result_rollback_result"]
        ):
            return False, (
                "Unexpected rollback_result: "
                f"{result.get('rollback_result')}"
            )

        probe = PROJECT_ROOT / probe_path

        if not probe.exists():
            return False, (
                f"Expected probe file was not created: {probe_path}"
            )

        return True, "PASS"

    finally:
        cleanup_p03_state(
            probe_path
        )
def cleanup_test_state(relative_paths):
    errors = []

    for relative_path in relative_paths:
        try:
            path = PROJECT_ROOT / relative_path

            if path.exists():
                path.unlink()
        except Exception as exc:
            errors.append(
                f"{relative_path}: {exc}"
            )

    try:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
    except Exception as exc:
        errors.append(
            f"checkpoint: {exc}"
        )

    if errors:
        raise RuntimeError(
            "; ".join(errors)
        )


def run_pa02(test):
    task = {
        "task_id": "PA-02-TASK-001",
        "description": "PA-02 synthetic transport failure test.",
        "edits": [],
        "expected_paths": [],
    }

    expression = f"""
    (async () => {{
        const originalPostMessage = window.postMessage;
        let capturedRequestId = null;

        try {{
            window.postMessage = function(message, targetOrigin) {{
                if (
                    message &&
                    message.source === "simulationagent-page" &&
                    message.type === "task_request"
                ) {{
                    capturedRequestId = message.request_id;

                    setTimeout(() => {{
                        originalPostMessage.call(
                            window,
                            {{
                                source: "simulationagent-bridge",
                                type: "task_response",
                                request_id: capturedRequestId,
                                success: false,
                                error: {{
                                    code: "BRIDGE_REQUEST_FAILED",
                                    message: "Synthetic transport failure."
                                }}
                            }},
                            "*"
                        );
                    }}, 0);

                    return;
                }}

                return originalPostMessage.call(
                    window,
                    message,
                    targetOrigin
                );
            }};

            try {{
                await window.SimulationAgentBridge.sendTask(
                    {json.dumps(task, ensure_ascii=False)}
                );

                return {{
                    rejected: false,
                    error: null
                }};
            }} catch (error) {{
                return {{
                    rejected: true,
                    error: error
                }};
            }}
        }} finally {{
            window.postMessage = originalPostMessage;
        }}
    }})()
    """

    with BrowserHarness(timeout=10) as browser:
        result = browser.evaluate(
            expression,
            await_promise=True,
        )

    oracle = test["oracle"]

    if not isinstance(result, dict):
        return False, (
            "PA-02 did not return a diagnostic object."
        )

    if result.get("rejected") is not True:
        return False, (
            "PA-02 Promise did not reject."
        )

    error = result.get("error")

    if not isinstance(error, dict):
        return False, (
            "PA-02 did not return a Bridge error object."
        )

    if error.get("code") != oracle["error.code"]:
        return False, (
            "Unexpected PA-02 error code: "
            f"{error.get('code')}"
        )

    return True, "PASS"


def run_pa03(test):
    expression = """
    (async () => {
        const inputs = [null, [], "invalid-task"];
        const results = [];

        for (const input of inputs) {
            try {
                const promise =
                    window.SimulationAgentBridge.sendTask(input);

                const isPromise =
                    promise instanceof Promise;

                await promise;

                results.push({
                    is_promise: isPromise,
                    rejected: false,
                    error: null
                });
            } catch (error) {
                results.push({
                    is_promise: true,
                    rejected: true,
                    error: error
                });
            }
        }

        return results;
    })()
    """

    with BrowserHarness(timeout=10) as browser:
        results = browser.evaluate(
            expression,
            await_promise=True,
        )

    oracle = test["oracle"]

    if not isinstance(results, list):
        return False, (
            "PA-03 did not return a result array."
        )

    if len(results) != 3:
        return False, (
            f"PA-03 returned {len(results)} results, "
            "expected 3."
        )

    for index, result in enumerate(results):
        if not isinstance(result, dict):
            return False, (
                f"PA-03 result {index} is not an object."
            )

        if result.get("is_promise") is not True:
            return False, (
                f"PA-03 input {index} did not "
                "produce a Promise."
            )

        if result.get("rejected") is not True:
            return False, (
                f"PA-03 input {index} was not rejected."
            )

        error = result.get("error")

        if not isinstance(error, dict):
            return False, (
                f"PA-03 input {index} returned "
                "no error object."
            )

        if error.get("code") != oracle["error.code"]:
            return False, (
                f"PA-03 input {index} returned "
                f"unexpected error code: {error.get('code')}"
            )

    return True, "PASS"


def run_pa04(test):
    task = {
        "task_id": "PA-04-TASK-001",
        "description": "PA-04 timeout test.",
        "edits": [],
        "expected_paths": [],
    }

    expression = f"""
    (async () => {{
        const originalPostMessage = window.postMessage;

        try {{
            window.postMessage = function(message, targetOrigin) {{
                if (
                    message &&
                    message.source === "simulationagent-page" &&
                    message.type === "task_request"
                ) {{
                    return;
                }}

                return originalPostMessage.call(
                    window,
                    message,
                    targetOrigin
                );
            }};

            try {{
                await window.SimulationAgentBridge.sendTask(
                    {json.dumps(task, ensure_ascii=False)},
                    {{
                        timeout: 100
                    }}
                );

                return {{
                    rejected: false,
                    error: null
                }};
            }} catch (error) {{
                return {{
                    rejected: true,
                    error: error
                }};
            }}
        }} finally {{
            window.postMessage = originalPostMessage;
        }}
    }})()
    """

    with BrowserHarness(timeout=10) as browser:
        result = browser.evaluate(
            expression,
            await_promise=True,
        )

    oracle = test["oracle"]

    if not isinstance(result, dict):
        return False, (
            "PA-04 did not return a diagnostic object."
        )

    if result.get("rejected") is not True:
        return False, (
            "PA-04 Promise did not reject."
        )

    error = result.get("error")

    if not isinstance(error, dict):
        return False, (
            "PA-04 did not return an error object."
        )

    if error.get("code") != oracle["error.code"]:
        return False, (
            "Unexpected PA-04 error code: "
            f"{error.get('code')}"
        )

    return True, "PASS"


def run_pa05(test):
    expression = """
    (async () => {
        const originalPostMessage = window.postMessage;
        const captured = [];

        try {
            window.postMessage = function(message, targetOrigin) {
                if (
                    message &&
                    message.source === "simulationagent-page" &&
                    message.type === "task_request"
                ) {
                    captured.push(message.request_id);
                    return;
                }

                return originalPostMessage.call(
                    window,
                    message,
                    targetOrigin
                );
            };

            const promiseA =
                window.SimulationAgentBridge.sendTask({
                    task_id: "PA-05-A",
                    description: "PA-05 A",
                    edits: [],
                    expected_paths: []
                });

            const promiseB =
                window.SimulationAgentBridge.sendTask({
                    task_id: "PA-05-B",
                    description: "PA-05 B",
                    edits: [],
                    expected_paths: []
                });

            await new Promise(resolve => setTimeout(resolve, 20));

            if (captured.length !== 2) {
                throw new Error(
                    "Expected two concurrent request captures."
                );
            }

            const requestA = captured[0];
            const requestB = captured[1];

            if (requestA === requestB) {
                throw new Error(
                    "Concurrent requests received identical request IDs."
                );
            }

            originalPostMessage.call(
                window,
                {
                    source: "simulationagent-bridge",
                    type: "task_response",
                    request_id: requestB,
                    success: true,
                    result: {
                        success: true,
                        marker: "B"
                    }
                },
                "*"
            );

            originalPostMessage.call(
                window,
                {
                    source: "simulationagent-bridge",
                    type: "task_response",
                    request_id: requestA,
                    success: true,
                    result: {
                        success: true,
                        marker: "A"
                    }
                },
                "*"
            );

            const [resultA, resultB] =
                await Promise.all([
                    promiseA,
                    promiseB
                ]);

            return {
                request_count: captured.length,
                distinct_request_ids:
                    requestA !== requestB,
                resultA: resultA,
                resultB: resultB
            };
        } finally {
            window.postMessage = originalPostMessage;
        }
    })()
    """

    with BrowserHarness(timeout=10) as browser:
        result = browser.evaluate(
            expression,
            await_promise=True,
        )

    oracle = test["oracle"]

    if not isinstance(result, dict):
        return False, (
            "PA-05 did not return a diagnostic object."
        )

    if result.get("request_count") != oracle["requests"]:
        return False, (
            f"PA-05 request count was "
            f"{result.get('request_count')}."
        )

    if result.get("distinct_request_ids") is not True:
        return False, (
            "PA-05 requests did not receive "
            "distinct request IDs."
        )

    result_a = result.get("resultA")
    result_b = result.get("resultB")

    if not isinstance(result_a, dict):
        return False, (
            "PA-05 first Promise did not resolve."
        )

    if not isinstance(result_b, dict):
        return False, (
            "PA-05 second Promise did not resolve."
        )

    if result_a.get("marker") != "A":
        return False, (
            "PA-05 first Promise received "
            "the wrong response."
        )

    if result_b.get("marker") != "B":
        return False, (
            "PA-05 second Promise received "
            "the wrong response."
        )

    if oracle["both_promises_resolved"] is not True:
        return False, "Invalid PA-05 oracle."

    return True, "PASS"


def run_pa06(test):
    expression = """
    (async () => {
        const originalPostMessage = window.postMessage;
        const captured = [];

        try {
            window.postMessage = function(message, targetOrigin) {
                if (
                    message &&
                    message.source === "simulationagent-page" &&
                    message.type === "task_request"
                ) {
                    captured.push(message.request_id);
                    return;
                }

                return originalPostMessage.call(
                    window,
                    message,
                    targetOrigin
                );
            };

            const promiseA =
                window.SimulationAgentBridge.sendTask({
                    task_id: "PA-06-A",
                    description: "PA-06 A",
                    edits: [],
                    expected_paths: []
                });

            const promiseB =
                window.SimulationAgentBridge.sendTask({
                    task_id: "PA-06-B",
                    description: "PA-06 B",
                    edits: [],
                    expected_paths: []
                });

            await new Promise(resolve => setTimeout(resolve, 20));

            if (captured.length !== 2) {
                throw new Error(
                    "Expected two concurrent request captures."
                );
            }

            originalPostMessage.call(
                window,
                {
                    source: "simulationagent-bridge",
                    type: "task_response",
                    request_id: captured[1],
                    success: true,
                    result: {
                        success: true,
                        marker: "SUCCESS"
                    }
                },
                "*"
            );

            originalPostMessage.call(
                window,
                {
                    source: "simulationagent-bridge",
                    type: "task_response",
                    request_id: captured[0],
                    success: true,
                    result: {
                        success: false,
                        marker: "FAILED_RESULT"
                    }
                },
                "*"
            );

            const [resultA, resultB] =
                await Promise.all([
                    promiseA,
                    promiseB
                ]);

            return {
                request_count: captured.length,
                resultA: resultA,
                resultB: resultB
            };
        } finally {
            window.postMessage = originalPostMessage;
        }
    })()
    """

    with BrowserHarness(timeout=10) as browser:
        result = browser.evaluate(
            expression,
            await_promise=True,
        )

    oracle = test["oracle"]

    if not isinstance(result, dict):
        return False, (
            "PA-06 did not return a diagnostic object."
        )

    if result.get("request_count") != oracle["requests"]:
        return False, (
            f"PA-06 request count was "
            f"{result.get('request_count')}."
        )

    result_a = result.get("resultA")
    result_b = result.get("resultB")

    if not isinstance(result_a, dict):
        return False, (
            "PA-06 first Promise did not resolve."
        )

    if not isinstance(result_b, dict):
        return False, (
            "PA-06 second Promise did not resolve."
        )

    if result_a.get("success") is not False:
        return False, (
            "PA-06 first result did not preserve "
            "success=false."
        )

    if result_a.get("marker") != "FAILED_RESULT":
        return False, (
            "PA-06 first Promise received "
            "the wrong result."
        )

    if result_b.get("success") is not True:
        return False, (
            "PA-06 second result did not preserve "
            "success=true."
        )

    if result_b.get("marker") != "SUCCESS":
        return False, (
            "PA-06 second Promise received "
            "the wrong result."
        )

    return True, "PASS"


def run_pa07(test):
    task_templates = [
        ("PA-07-TASK-001", "pa07_page_api_a.txt"),
        ("PA-07-TASK-002", "pa07_page_api_b.txt"),
        ("PA-07-TASK-003", "pa07_page_api_c.txt"),
    ]

    try:
        for task_id, probe_path in task_templates:
            task = {
                "task_id": task_id,
                "description": "PA-07 sequential Page API task.",
                "edits": [
                    {
                        "type": "create",
                        "path": probe_path,
                        "content": f"{task_id}\n",
                    }
                ],
                "expected_paths": [
                    probe_path
                ],
            }

            expression = f"""
            (async () => {{
                const promise =
                    window.SimulationAgentBridge.sendTask(
                        {json.dumps(task, ensure_ascii=False)}
                    );

                const isPromise =
                    promise instanceof Promise;

                const result =
                    await promise;

                return {{
                    isPromise: isPromise,
                    result: result
                }};
            }})()
            """

            with BrowserHarness(timeout=60) as browser:
                result = browser.evaluate(
                    expression,
                    await_promise=True,
                )

            if not isinstance(result, dict):
                return False, (
                    f"PA-07 {task_id} returned "
                    "no diagnostic object."
                )

            if result.get("isPromise") is not True:
                return False, (
                    f"PA-07 {task_id} did not "
                    "return a Promise."
                )

            task_result = result.get("result")

            if not isinstance(task_result, dict):
                return False, (
                    f"PA-07 {task_id} did not "
                    "return TaskResult."
                )

            if task_result.get("success") is not True:
                return False, (
                    f"PA-07 {task_id} failed."
                )

            if task_result.get("stage") != "COMPLETE":
                return False, (
                    f"PA-07 {task_id} did not complete."
                )

            cleanup_test_state([probe_path])

        return True, "PASS"

    finally:
        cleanup_test_state(
            [path for _, path in task_templates]
        )


def run_pa08(test):
    task = {
        "task_id": "PA-08-TASK-001",
        "description": "PA-08 TaskResult integrity test.",
        "edits": [
            {
                "type": "create",
                "path": "pa08_page_api_probe.txt",
                "content": "PA-08 Page API test.\n",
            }
        ],
        "expected_paths": [
            "pa08_page_api_probe.txt"
        ],
    }

    probe_path = task["edits"][0]["path"]

    expression = f"""
    (async () => {{
        const promise =
            window.SimulationAgentBridge.sendTask(
                {json.dumps(task, ensure_ascii=False)}
            );

        const isPromise =
            promise instanceof Promise;

        const result =
            await promise;

        return {{
            isPromise: isPromise,
            result: result
        }};
    }})()
    """

    try:
        with BrowserHarness(timeout=60) as browser:
            result = browser.evaluate(
                expression,
                await_promise=True,
            )

        if not isinstance(result, dict):
            return False, (
                "PA-08 returned no result object."
            )

        if result.get("isPromise") is not True:
            return False, (
                "PA-08 sendTask did not return "
                "a Promise."
            )

        task_result = result.get("result")

        if not isinstance(task_result, dict):
            return False, (
                "PA-08 did not return TaskResult."
            )

        required_fields = [
            "success",
            "stage",
            "checkpoint",
            "attempts",
            "edit_results",
            "diff",
            "changed_paths",
            "diff_success",
            "diff_validated",
            "build_result",
            "run_result",
            "rollback_result",
            "failure_code",
            "failure_message",
            "diagnostics_stdout",
            "diagnostics_stderr",
        ]

        missing = [
            field
            for field in required_fields
            if field not in task_result
        ]

        if missing:
            return False, (
                "PA-08 TaskResult is missing fields: "
                + ", ".join(missing)
            )

        if task_result.get("success") is not True:
            return False, (
                "PA-08 TaskResult.success "
                "is not true."
            )

        if task_result.get("stage") != "COMPLETE":
            return False, (
                "PA-08 TaskResult.stage "
                "is not COMPLETE."
            )

        if task_result.get("diff_validated") is not True:
            return False, (
                "PA-08 TaskResult.diff_validated "
                "is not true."
            )

        return True, "PASS"

    finally:
        cleanup_test_state([probe_path])


def run_pa09(test):
    expression = """
    (async () => {
        const originalPostMessage = window.postMessage;
        let capturedRequestId = null;

        try {
            window.postMessage = function(message, targetOrigin) {
                if (
                    message &&
                    message.source === "simulationagent-page" &&
                    message.type === "task_request"
                ) {
                    capturedRequestId = message.request_id;
                    return;
                }

                return originalPostMessage.call(
                    window,
                    message,
                    targetOrigin
                );
            };

            const promise =
                window.SimulationAgentBridge.sendTask({
                    task_id: "PA-09-TASK-001",
                    description: "PA-09 foreign response test.",
                    edits: [],
                    expected_paths: []
                });

            await new Promise(resolve => setTimeout(resolve, 20));

            if (!capturedRequestId) {
                throw new Error(
                    "PA-09 did not capture a request ID."
                );
            }

            originalPostMessage.call(
                window,
                {
                    source: "simulationagent-bridge",
                    type: "task_response",
                    request_id:
                        capturedRequestId + "-FOREIGN",
                    success: true,
                    result: {
                        success: true,
                        marker: "FOREIGN"
                    }
                },
                "*"
            );

            const pendingState =
                await Promise.race([
                    promise.then(() => "RESOLVED"),
                    new Promise(resolve =>
                        setTimeout(
                            () => resolve("PENDING"),
                            50
                        )
                    )
                ]);

            originalPostMessage.call(
                window,
                {
                    source: "simulationagent-bridge",
                    type: "task_response",
                    request_id: capturedRequestId,
                    success: true,
                    result: {
                        success: true,
                        marker: "LEGITIMATE"
                    }
                },
                "*"
            );

            const result = await promise;

            return {
                foreign_ignored:
                    pendingState === "PENDING",
                result: result
            };
        } finally {
            window.postMessage = originalPostMessage;
        }
    })()
    """

    with BrowserHarness(timeout=10) as browser:
        result = browser.evaluate(
            expression,
            await_promise=True,
        )

    oracle = test["oracle"]

    if not isinstance(result, dict):
        return False, (
            "PA-09 did not return a diagnostic object."
        )

    if result.get("foreign_ignored") != (
        oracle["foreign_response_ignored"]
    ):
        return False, (
            "PA-09 foreign response was not ignored."
        )

    legitimate = result.get("result")

    if not isinstance(legitimate, dict):
        return False, (
            "PA-09 legitimate response "
            "was not resolved."
        )

    if legitimate.get("marker") != "LEGITIMATE":
        return False, (
            "PA-09 resolved the wrong response."
        )

    return True, "PASS"


def run_pa10(test):
    task = {
        "task_id": "PA-10-TASK-001",
        "description": "PA-10 late response test.",
        "edits": [],
        "expected_paths": [],
    }

    expression = f"""
    (async () => {{
        const originalPostMessage = window.postMessage;
        let capturedRequestId = null;

        try {{
            window.postMessage = function(message, targetOrigin) {{
                if (
                    message &&
                    message.source === "simulationagent-page" &&
                    message.type === "task_request"
                ) {{
                    capturedRequestId = message.request_id;
                    return;
                }}

                return originalPostMessage.call(
                    window,
                    message,
                    targetOrigin
                );
            }};

            let timeoutError = null;

            try {{
                await window.SimulationAgentBridge.sendTask(
                    {json.dumps(task, ensure_ascii=False)},
                    {{
                        timeout: 100
                    }}
                );
            }} catch (error) {{
                timeoutError = error;
            }}

            if (
                !timeoutError ||
                timeoutError.code !== "TIMEOUT"
            ) {{
                return {{
                    timeout_detected: false,
                    late_response_ignored: false
                }};
            }}

            originalPostMessage.call(
                window,
                {{
                    source: "simulationagent-bridge",
                    type: "task_response",
                    request_id: capturedRequestId,
                    success: true,
                    result: {{
                        success: true,
                        marker: "LATE"
                    }}
                }},
                "*"
            );

            await new Promise(resolve =>
                setTimeout(resolve, 50)
            );

            window.postMessage =
                originalPostMessage;

            const followupTask = {{
                task_id: "PA-10-TASK-002",
                description: "PA-10 follow-up task.",
                edits: [
                    {{
                        type: "create",
                        path: "pa10_page_api_probe.txt",
                        content: "PA-10 follow-up.\\n"
                    }}
                ],
                expected_paths: [
                    "pa10_page_api_probe.txt"
                ]
            }};

            const followupResult =
                await window.SimulationAgentBridge.sendTask(
                    followupTask
                );

            return {{
                timeout_detected: true,
                late_response_ignored: true,
                followup_result: followupResult
            }};
        }} finally {{
            window.postMessage = originalPostMessage;
        }}
    }})()
    """

    try:
        with BrowserHarness(timeout=60) as browser:
            result = browser.evaluate(
                expression,
                await_promise=True,
            )

        oracle = test["oracle"]

        if not isinstance(result, dict):
            return False, (
                "PA-10 did not return a diagnostic object."
            )

        if result.get("timeout_detected") != (
            oracle["timeout_error.code"] == "TIMEOUT"
        ):
            return False, (
                "PA-10 timeout was not detected correctly."
            )

        if result.get("late_response_ignored") != (
            oracle["late_response_ignored"]
        ):
            return False, (
                "PA-10 late response handling failed."
            )

        followup = result.get("followup_result")

        if not isinstance(followup, dict):
            return False, (
                "PA-10 follow-up request did not "
                "return TaskResult."
            )
        if oracle["subsequent_request_success"] is not True:
            return False, "Invalid PA-10 oracle."
        if followup.get("success") is not True:
            return False, (
                "PA-10 follow-up Page API request failed."
            )

        if followup.get("stage") != "COMPLETE":
            return False, (
                "PA-10 follow-up request did not complete."
            )

        return True, "PASS"

    finally:
        cleanup_test_state(
            ["pa10_page_api_probe.txt"]
        )
def run_e03(test):
    message = test["input"]
    request_id = message["request_id"]

    try:
        with BrowserHarness(timeout=10) as browser:
            target = browser.find_chatgpt_page()

            if target.get("type") != "page":
                return False, (
                    "Unexpected browser target type: "
                    f"{target.get('type')}"
                )

            if target.get("url") != "https://chatgpt.com/":
                return False, (
                    "Unexpected browser target URL: "
                    f"{target.get('url')}"
                )

            browser.clear_page_messages()

            browser.send_page_message(
                message
            )

            response = browser.wait_for_page_message(
                source="simulationagent-bridge",
                message_type="task_response",
                request_id=request_id,
                timeout=30,
            )

        oracle = test["oracle"]

        if response.get("source") != (
            oracle["response.source"]
        ):
            return False, (
                "Unexpected response source: "
                f"{response.get('source')}"
            )

        if response.get("type") != (
            oracle["response.type"]
        ):
            return False, (
                "Unexpected response type: "
                f"{response.get('type')}"
            )

        if response.get("request_id") != (
            oracle["response.request_id"]
        ):
            return False, (
                "Unexpected request_id: "
                f"{response.get('request_id')}"
            )

        if response.get("success") != (
            oracle["response.success"]
        ):
            return False, (
                "Unexpected bridge success: "
                f"{response.get('success')}"
            )

        result = response.get("result")

        if not isinstance(result, dict):
            return False, (
                "Response result is not an object."
            )

        if result.get("success") != (
            oracle["response.result.success"]
        ):
            return False, (
                "Unexpected TaskResult.success: "
                f"{result.get('success')}"
            )

        if CHECKPOINT_FILE.exists():
            return False, (
                "Checkpoint was created for invalid Task."
            )

        if get_git_status():
            return False, (
                "Project repository changed after invalid Task."
            )

        return True, "PASS"

    finally:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
def run_test(test):
    test_id = test["id"]

    if test_id == "P-01":
        return run_p01(test)

    if test_id == "P-02":
        return run_p02(test)
        
    if test_id == "P-03":
        return run_p03(test)
        
    if test_id == "P-04":
        return run_p04(test)

    if test_id == "P-05":
        return run_p05(test)

    if test_id == "P-06":
        return run_p06(test)
        
    if test_id == "P-07":
        return run_p07(test)

    if test_id == "P-08":
        return run_p08(test)
        
    if test_id == "P-09":
        return run_p09(test)

    if test_id == "P-10":
        return run_p10(test)
        
    if test_id == "PA-01":
        return run_pa01(test)

    if test_id == "PA-02":
        return run_pa02(test)

    if test_id == "PA-03":
        return run_pa03(test)

    if test_id == "PA-04":
        return run_pa04(test)

    if test_id == "PA-05":
        return run_pa05(test)

    if test_id == "PA-06":
        return run_pa06(test)

    if test_id == "PA-07":
        return run_pa07(test)

    if test_id == "PA-08":
        return run_pa08(test)

    if test_id == "PA-09":
        return run_pa09(test)

    if test_id == "PA-10":
        return run_pa10(test)
    
    if test_id == "E-01":
        return run_e01(test)

    if test_id == "E-02":
        return run_e02(test)
        
    if test_id == "E-03":
        return run_e03(test)
        
    return False, "NOT_IMPLEMENTED"


def main():
    try:
        contract = load_contract()

    except Exception as exc:
        print(
            f"ERROR: Failed to load contract: {exc}"
        )
        return 1

    errors = validate_contract(
        contract
    )

    if errors:
        print()
        print("=" * 70)
        print(
            "BRIDGE TEST CONTRACT VALIDATION FAILED"
        )
        print("=" * 70)
        print()

        for error in errors:
            print(
                f"ERROR: {error}"
            )

        print()

        return 1

    print_summary(
        contract
    )

    print(
        "Contract validation: PASS"
    )
    print()
    try:
        ensure_project_clean()

    except Exception as exc:
        print(
            "PROJECT PRECHECK: FAIL"
        )
        print(
            f"    {exc}"
        )
        return 1

    print(
        "PROJECT PRECHECK: PASS"
    )
    print()
    p_tests = [
        test
        for test in contract["tests"]
        if test["id"] in {
            "P-01",
            "P-02",
            "P-03",
            "P-04",
            "P-05",
            "P-06",
            "P-07",
            "P-08",
            "P-09",
            "P-10",
        }
    ]

    e_tests = [
        test
        for test in contract["tests"]
        if test["id"].startswith("E-")
    ]

    print("=" * 70)
    print("EXECUTING P TESTS")
    print("=" * 70)
    print()

    failed = 0

    for test in p_tests:
        print(
            f"[{test['id']}] {test['name']}"
        )

        try:
            success, message = run_test(
                test
            )

        except Exception as exc:
            success = False
            message = (
                f"EXCEPTION: {exc}"
            )

        if success:
            print(
                "    PASS"
            )
        else:
            print(
                f"    FAIL: {message}"
            )
            failed += 1

    print()

    if failed:
        print(
            f"P tests failed: {failed}"
        )
        return 1

    print(
        f"P tests passed: {len(p_tests)}"
    )
    print()

    try:
        ensure_project_clean()

    except Exception as exc:
        print(
            "PROJECT POSTCHECK: FAIL"
        )
        print(
            f"    {exc}"
        )
        return 1

    print(
        "PROJECT POSTCHECK: PASS"
    )
    print()

    if e_tests:
        print("=" * 70)
        print("EXECUTING E TESTS")
        print("=" * 70)
        print()

        e_failed = 0

        for test in e_tests:
            print(
                f"[{test['id']}] {test['name']}"
            )

            try:
                success, message = run_test(
                    test
                )

            except Exception as exc:
                success = False
                message = (
                    f"EXCEPTION: {exc}"
                )

            if success:
                print(
                    "    PASS"
                )
            else:
                print(
                    f"    FAIL: {message}"
                )
                e_failed += 1

        print()

        if e_failed:
            print(
                f"E tests failed: {e_failed}"
            )
            return 1

        print(
            f"E tests passed: {len(e_tests)}"
        )
        print()

        try:
            ensure_project_clean()

        except Exception as exc:
            print(
                "PROJECT FINAL POSTCHECK: FAIL"
            )
            print(
                f"    {exc}"
            )
            return 1

        print(
            "PROJECT FINAL POSTCHECK: PASS"
        )
        print()


    pa_tests = [
        test
        for test in contract["tests"]
        if test["id"].startswith("PA-")
    ]

    if pa_tests:
        print("=" * 70)
        print("EXECUTING PA TESTS")
        print("=" * 70)
        print()

        pa_failed = 0

        for test in pa_tests:
            print(
                f"[{test['id']}] {test['name']}"
            )

            try:
                success, message = run_test(
                    test
                )

            except Exception as exc:
                success = False
                message = (
                    f"EXCEPTION: {exc}"
                )

            if success:
                print(
                    "    PASS"
                )
            else:
                print(
                    f"    FAIL: {message}"
                )
                pa_failed += 1

        print()

        if pa_failed:
            print(
                f"PA tests failed: {pa_failed}"
            )
            return 1

        print(
            f"PA tests passed: {len(pa_tests)}"
        )
        print()

        try:
            ensure_project_clean()

        except Exception as exc:
            print(
                "PROJECT PA FINAL POSTCHECK: FAIL"
            )
            print(
                f"    {exc}"
            )
            return 1

        print(
            "PROJECT PA FINAL POSTCHECK: PASS"
        )
        print()
        
        
    return 0
    
if __name__ == "__main__":
    sys.exit(main())