#!/usr/bin/env python3
import json
import os
import platform
import shlex
import stat
import sys
from pathlib import Path


class IPTestInstaller:
    def __init__(self):
        self.script_directory = Path(__file__).resolve().parent
        self.runtime_script_path = self.script_directory / "iptest_runtime.py"
        self.config_path = self.script_directory / "client_config.json"
        self.install_command_names = ["iptest"]
        self.legacy_command_name = "ip_test"

    def is_macos(self):
        return platform.system() == "Darwin"

    def pick_install_directory(self):
        primary_directory = Path("/usr/local/bin")
        if primary_directory.exists() and os.access(primary_directory, os.W_OK):
            return primary_directory
        return Path.home() / ".local" / "bin"

    def load_install_server_url(self):
        configured_url = os.getenv("IPTEST_INSTALL_SERVER_URL", "").strip()
        if configured_url:
            return configured_url
        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as config_file:
                    config_mapping = json.load(config_file)
                if isinstance(config_mapping, dict):
                    config_server_url = str(config_mapping.get("server_url", "")).strip()
                    if config_server_url:
                        return config_server_url
            except Exception:
                pass
        return "127.0.0.1:8000"

    def build_wrapper_content(self, server_url):
        quoted_server_url = shlex.quote(str(server_url).strip())
        quoted_runtime_path = shlex.quote(str(self.runtime_script_path))
        return f"""#!/bin/zsh
IPTEST_SERVER_URL={quoted_server_url} python3 {quoted_runtime_path} "$@"
"""

    def install_command(self, install_directory, command_name, server_url):
        command_path = install_directory / command_name
        command_path.write_text(self.build_wrapper_content(server_url), encoding="utf-8")
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
        install_server_url = self.load_install_server_url()
        legacy_command_path = install_directory / self.legacy_command_name
        if legacy_command_path.exists():
            try:
                legacy_command_path.unlink()
            except Exception:
                pass
        for command_name in self.install_command_names:
            command_path = self.install_command(install_directory, command_name, install_server_url)
            print(f"Reinstalled command: {command_path}")
        print(f"Installed server URL: {install_server_url}")
        if str(install_directory) not in os.getenv("PATH", ""):
            print(f"Add this path to your shell config: export PATH=\"{install_directory}:$PATH\"")
        return 0


if __name__ == "__main__":
    sys.exit(IPTestInstaller().run())
