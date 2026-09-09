import os

from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.terminal import TerminalTool


def main() -> None:
    workspace = os.path.abspath("openhands_sandbox")

    print("OpenHands experiment")
    print(f"Workspace: {workspace}")

    llm = LLM(
        model="gpt-5.5",
        api_key=os.getenv("LLM_API_KEY"),
    )

    agent = Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
        ],
    )

    conversation = Conversation(
        agent=agent,
        workspace=workspace,
    )

    conversation.send_message(
        "Create a file named HELLO.txt in the current workspace. "
        "Put exactly three lines into it: "
        "OpenHands, "
        "Sandbox test, "
        "Success."
    )

    conversation.run()

    print("OpenHands experiment finished.")


if __name__ == "__main__":
    main()