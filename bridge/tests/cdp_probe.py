import json
import urllib.request
import websocket


def get_chatgpt_target():
    with urllib.request.urlopen(
        "http://localhost:9222/json/list",
        timeout=5,
    ) as response:
        targets = json.load(response)

    for target in targets:
        if (
            target.get("type") == "page"
            and target.get("url") == "https://chatgpt.com/"
        ):
            return target

    raise RuntimeError("ChatGPT page target not found.")


def main():
    target = get_chatgpt_target()
    ws_url = target["webSocketDebuggerUrl"].replace(
        "localhost",
        "127.0.0.1",
    )

    print("Target:", target["id"])
    print("URL:", target["url"])

    ws = websocket.create_connection(
        ws_url,
        timeout=5,
    )

    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "document.title",
                "returnByValue": True,
            },
        }))

        while True:
            message = json.loads(ws.recv())

            if message.get("id") == 1:
                print("CDP response:")
                print(json.dumps(message, indent=2, ensure_ascii=False))
                break
    finally:
        ws.close()


if __name__ == "__main__":
    main()