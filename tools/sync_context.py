from __future__ import annotations

import ast
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_ROOT = PROJECT_ROOT / "PROJECT_CONTEXT"
SOURCE_ROOT = CONTEXT_ROOT / "source"

EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "PROJECT_CONTEXT",
}



def relative_files() -> list[Path]:
    result: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        result.append(relative)
    return sorted(result, key=lambda p: p.as_posix().lower())



def numbered_text(text: str) -> str:
    lines = text.splitlines()
    output = "\n".join(
        f"{index:04d} | {line}"
        for index, line in enumerate(lines, start=1)
    )
    return output + ("\n" if text.endswith("\n") else "")



def capture_sources(files: list[Path]) -> list[str]:
    if SOURCE_ROOT.exists():
        shutil.rmtree(SOURCE_ROOT)
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)

    captured: list[str] = []

    for relative in files:
        if relative.suffix.lower() != ".py":
            continue

        source = PROJECT_ROOT / relative
        destination = SOURCE_ROOT / (relative.as_posix().replace("/", "__") + ".txt")
        destination.write_text(
            numbered_text(source.read_text(encoding="utf-8", errors="replace")),
            encoding="utf-8",
        )
        captured.append(relative.as_posix())

    return captured



def summarize_python(relative: Path) -> dict[str, object]:
    path = PROJECT_ROOT / relative
    text = path.read_text(encoding="utf-8", errors="replace")

    summary: dict[str, object] = {
        "path": relative.as_posix(),
        "lines": len(text.splitlines()),
        "classes": [],
        "functions": [],
    }

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        summary["syntax_error"] = f"{exc.msg} at line {exc.lineno}"
        return summary

    classes: list[dict[str, object]] = []
    functions: list[dict[str, object]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "methods": sorted(
                        child.name
                        for child in node.body
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ),
                }
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                }
            )

    classes.sort(key=lambda item: int(item["line"]))
    functions.sort(key=lambda item: int(item["line"]))

    summary["classes"] = classes
    summary["functions"] = functions
    return summary



def collect_git_state() -> dict[str, object]:
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        return {
            "repository": False,
            "head": None,
            "clean": None,
            "status": None,
        }

    def run(args: list[str]) -> tuple[int, str]:
        try:
            result = subprocess.run(
                args,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            return -1, str(exc)
        return result.returncode, (result.stdout or result.stderr).strip()

    head_code, head = run(["git", "rev-parse", "HEAD"])
    status_code, status = run(["git", "status", "--porcelain=v1", "--branch"])

    changed = []
    if status_code == 0:
        changed = [
            line for line in status.splitlines()
            if line and not line.startswith("##")
        ]

    return {
        "repository": True,
        "head": head if head_code == 0 else None,
        "clean": status_code == 0 and not changed,
        "status": status if status_code == 0 else None,
    }



def write_text(name: str, content: str) -> None:
    (CONTEXT_ROOT / name).write_text(content, encoding="utf-8")



def main() -> int:
    timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")

    CONTEXT_ROOT.mkdir(parents=True, exist_ok=True)

    files = relative_files()
    python_files = [path for path in files if path.suffix.lower() == ".py"]
    captured = capture_sources(files)
    git = collect_git_state()

    summaries = [summarize_python(path) for path in python_files]

    tree_lines = [f"{PROJECT_ROOT.name}/"]

    def build_tree(path: Path, prefix: str) -> None:
        entries = [
            child for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            if child.name not in EXCLUDED_DIRS and not child.is_symlink()
        ]
        for index, child in enumerate(entries):
            last = index == len(entries) - 1
            tree_lines.append(prefix + ("└── " if last else "├── ") + child.name + ("/" if child.is_dir() else ""))
            if child.is_dir():
                build_tree(child, prefix + ("    " if last else "│   "))

    build_tree(PROJECT_ROOT, "")

    state = {
        "generated_at": timestamp,
        "project_root": str(PROJECT_ROOT),
        "file_count": len(files),
        "python_file_count": len(python_files),
        "captured_source_count": len(captured),
        "git": git,
        "pytest": {
            "status": "NOT_RUN",
            "reason": "Automatic pytest execution is intentionally disabled in context sync.",
        },
    }

    write_text(
        "INDEX.md",
        "\n".join([
            "# SimulationAgent — Project Context",
            "",
            f"Generated: `{timestamp}`",
            f"Project root: `{PROJECT_ROOT}`",
            "",
            "## Files",
            f"- Total files: `{len(files)}`",
            f"- Python files: `{len(python_files)}`",
            f"- Captured sources: `{len(captured)}`",
            "",
            "## Generated files",
            "- `INDEX.md` — index",
            "- `STATE.md` — current technical state",
            "- `TREE.md` — directory tree",
            "- `GIT.md` — Git state when applicable",
            "- `PYTHON_INDEX.md` — classes/functions and line numbers",
            "- `source/` — numbered Python source snapshots",
            "",
            "## Important",
            "This directory is generated context. It is not the project source of truth.",
            "",
        ])
    )

    write_text(
        "STATE.md",
        "# SimulationAgent — Current Technical State\n\n```json\n"
        + json.dumps(state, ensure_ascii=False, indent=2)
        + "\n```\n",
    )

    write_text(
        "TREE.md",
        "# SimulationAgent — Project Tree\n\n"
        + "\n".join(tree_lines)
        + "\n",
    )

    if git["repository"]:
        git_text = (
            "# SimulationAgent — Git Snapshot\n\n"
            f"HEAD: `{git['head']}`\n\n"
            f"Clean: `{git['clean']}`\n\n"
            "```text\n"
            f"{git['status'] or ''}\n"
            "```\n"
        )
    else:
        git_text = (
            "# SimulationAgent — Git Snapshot\n\n"
            "This project is not a Git repository.\n"
        )

    write_text("GIT.md", git_text)

    write_text(
        "PYTHON_INDEX.md",
        "# SimulationAgent — Python Index\n\n"
        "```json\n"
        + json.dumps(summaries, ensure_ascii=False, indent=2)
        + "\n```\n",
    )

    print("=" * 70)
    print("SimulationAgent Project Context Sync")
    print("=" * 70)
    print(f"Project root:       {PROJECT_ROOT}")
    print(f"Context root:       {CONTEXT_ROOT}")
    print(f"Project files:      {len(files)}")
    print(f"Python files:       {len(python_files)}")
    print(f"Captured sources:   {len(captured)}")
    if git["repository"]:
        print(f"Git HEAD:           {git['head']}")
        print(f"Git clean:          {'YES' if git['clean'] else 'NO'}")
    else:
        print("Git:                not a repository")
    print("Pytest:             NOT RUN (intentional)")
    print("Status:             PASS")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
