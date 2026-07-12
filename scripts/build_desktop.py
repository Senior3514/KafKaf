"""Build the KafKaf desktop app into a single-file executable with PyInstaller.

Runs identically on Linux/macOS/Windows (the add-data separator is computed
via os.pathsep, not hardcoded), so the same command works in every OS's CI
runner — see .github/workflows/build-desktop.yml.

Usage: python scripts/build_desktop.py
"""

import os

from PyInstaller.__main__ import run


def main() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    web_static = os.path.join(project_root, "kafkaf", "clients", "web", "static")
    entry = os.path.join(project_root, "kafkaf", "clients", "desktop", "main.py")

    run(
        [
            entry,
            "--name",
            "kafkaf-desktop",
            "--onefile",
            "--noconfirm",
            "--add-data",
            f"{web_static}{os.pathsep}kafkaf/clients/web/static",
        ]
    )


if __name__ == "__main__":
    main()
