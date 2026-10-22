"""Cross-platform task runner: `python tasks.py <setup|serve|test|screenshots>`."""

from __future__ import annotations

import subprocess
import sys

PY = sys.executable
TASKS = {
    "setup": [PY, "-m", "pip", "install", "-e", ".[dev]"],
    "serve": [PY, "-m", "uvicorn", "studybuddy.app:app", "--reload", "--port", "8000"],
    "test": [PY, "-m", "pytest", "-q"],
    "screenshots": [PY, "scripts/screenshots.py"],
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        raise SystemExit(f"usage: python tasks.py [{'|'.join(TASKS)}] [extra args]")
    raise SystemExit(subprocess.call(TASKS[sys.argv[1]] + sys.argv[2:]))


if __name__ == "__main__":
    main()
