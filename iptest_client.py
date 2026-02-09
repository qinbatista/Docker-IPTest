#!/usr/bin/env python3
import os
import platform
import stat
import sys
from pathlib import Path


class IPTestInstaller:
    def __init__(self):
        self.script_directory = Path(__file__).resolve().parent
        self.runtime_script_path = self.script_directory / "iptest_runtime.py"
        self.install_command_names = ["iptest", "ip_test"]

    def is_macos(self):
        return platform.system() == "Darwin"

    def pick_install_directory(self):
        primary_directory = Path("/usr/local/bin")
        if primary_directory.exists() and os.access(primary_directory, os.W_OK):
            return primary_directory
        return Path.home() / ".local" / "bin"

    def build_wrapper_content(self):
        return f"""#!/bin/zsh
python3 \"{self.runtime_script_path}\" \"$@\"
"""

    def install_command(self, install_directory, command_name):
        command_path = install_directory / command_name
        command_path.write_text(self.build_wrapper_content(), encoding="utf-8")
        command_mode = command_path.stat().st_mode
        command_path.chmod(command_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return command_path

    def run(self):
        if not self.is_macos():
            print("This installer currently supports macOS only", file=sys.stderr)
            return 1
        if not self.runtime_script_path.exists():
            print(f"Runtime script not found: {self.runtime_script_path}", file=sys.stderr)
            return 1
        install_directory = self.pick_install_directory()
        install_directory.mkdir(parents=True, exist_ok=True)
        for command_name in self.install_command_names:
            command_path = self.install_command(install_directory, command_name)
            print(f"Reinstalled command: {command_path}")
        if str(install_directory) not in os.getenv("PATH", ""):
            print(f"Add this path to your shell config: export PATH=\"{install_directory}:$PATH\"")
        return 0


if __name__ == "__main__":
    sys.exit(IPTestInstaller().run())
