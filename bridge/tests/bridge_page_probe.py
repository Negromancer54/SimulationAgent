import json

from browser_harness import BrowserHarness


REQUEST_ID = "E-01-PROBE-REQ"

TASK = {
    "task_id": "E-01-PROBE-TASK",
    "description": "Browser Bridge page probe.",
    "edits": [
        {
            "type": "create",
            "path": "e01_probe.txt",
            "content": "Browser Bridge probe.\n",
        }
    ],
    "expected_paths": [
        "e01_probe.txt",
    ],
}


def main():
    with BrowserHarness(timeout=30) as browser:
        target = browser.find_chatgpt_page()

        print("Target:", target["id"])
        print("URL:", target["url"])

        browser.clear_page_messages()

        browser.send_page_message(
            {
                "source": "simulationagent-page",
                "type": "task_request",
                "request_id": REQUEST_ID,
                "task": TASK,
            }
        )

        print("Task sent.")

        response = browser.wait_for_page_message(
            source="simulationagent-bridge",
            message_type="task_response",
            request_id=REQUEST_ID,
            timeout=30,
        )

        print("Bridge response:")
        print(
            json.dumps(
                response,
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()