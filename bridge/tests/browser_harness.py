import json
import time
import urllib.request

import websocket


class BrowserHarness:
    CDP_LIST_URL = "http://localhost:9222/json/list"

    def __init__(self, timeout=10):
        self.timeout = timeout
        self.ws = None
        self._next_message_id = 1

    def connect(self):
        target = self.find_chatgpt_page()

        ws_url = target["webSocketDebuggerUrl"].replace(
            "localhost",
            "127.0.0.1",
        )

        self.ws = websocket.create_connection(
            ws_url,
            timeout=self.timeout,
        )
        self.evaluate(
            """
            (() => {
                window.__simulationAgentBridgeHarnessMessages = [];

                window.addEventListener("message", (event) => {
                    if (event.source === window) {
                        window.__simulationAgentBridgeHarnessMessages.push(
                            event.data
                        );
                    }
                });

                return "listener installed";
            })()
            """
        )

        return target

    def find_chatgpt_page(self):
        with urllib.request.urlopen(
            self.CDP_LIST_URL,
            timeout=self.timeout,
        ) as response:
            targets = json.load(response)

        for target in targets:
            if (
                target.get("type") == "page"
                and target.get("url") == "https://chatgpt.com/"
            ):
                return target

        raise RuntimeError("ChatGPT page target not found.")

    def evaluate(self, expression, *, await_promise=False):
        if self.ws is None:
            raise RuntimeError("BrowserHarness is not connected.")

        message_id = self._next_message_id
        self._next_message_id += 1

        self.ws.send(
            json.dumps(
                {
                    "id": message_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "returnByValue": True,
                        "awaitPromise": await_promise,
                    },
                }
            )
        )

        deadline = time.time() + self.timeout

        while time.time() < deadline:
            message = json.loads(self.ws.recv())

            if message.get("id") != message_id:
                continue

            if "error" in message:
                raise RuntimeError(
                    f"CDP Runtime.evaluate failed: {message['error']}"
                )

            return (
                message
                .get("result", {})
                .get("result", {})
                .get("value")
            )

        raise TimeoutError(
            "Timed out waiting for Runtime.evaluate response."
        )

    def send_page_message(self, message):
        expression = (
            "window.postMessage("
            f"{json.dumps(message, ensure_ascii=False)},"
            '"*"'
            ");"
        )

        return self.evaluate(expression)
    def clear_page_messages(self):
        self.evaluate(
            """
            window.__simulationAgentBridgeHarnessMessages = [];
            "cleared";
            """
        )
    def wait_for_page_message(
        self,
        *,
        source=None,
        message_type=None,
        request_id=None,
        timeout=None,
    ):
        if self.ws is None:
            raise RuntimeError("BrowserHarness is not connected.")

        timeout = self.timeout if timeout is None else timeout
        deadline = time.time() + timeout

        while time.time() < deadline:
            raw_messages = self.evaluate(
                """
                JSON.stringify(
                    window.__simulationAgentBridgeHarnessMessages || []
                )
                """
            )

            messages = json.loads(raw_messages or "[]")

            for message in messages:
                if not isinstance(message, dict):
                    continue

                if source is not None and message.get("source") != source:
                    continue

                if (
                    message_type is not None
                    and message.get("type") != message_type
                ):
                    continue

                if (
                    request_id is not None
                    and message.get("request_id") != request_id
                ):
                    continue

                return message

            time.sleep(0.1)

        raise TimeoutError(
            "Timed out waiting for matching page message."
        )
    def close(self):
        if self.ws is not None:
            self.ws.close()
            self.ws = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()