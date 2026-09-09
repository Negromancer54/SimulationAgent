from browser_harness import BrowserHarness


def main():
    with BrowserHarness() as browser:
        target = browser.find_chatgpt_page()

        print("Target:", target["id"])
        print("URL:", target["url"])

        title = browser.evaluate("document.title")

        print("Title:", title)

        result = browser.evaluate(
            "window.__simulationAgentBridgeHarnessProbe = true; "
            "typeof window.__simulationAgentBridgeHarnessProbe"
        )

        print("Runtime result:", result)


if __name__ == "__main__":
    main()