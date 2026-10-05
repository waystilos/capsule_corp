#!/usr/bin/env python3
"""
scripts/install_elixir.py - Cross-Platform Global Elixir & Erlang Installer for Capsule Corp

Idempotently detects and installs Elixir and Erlang/OTP across:
  - macOS (Homebrew, mise, asdf)
  - Linux (Debian/Ubuntu, Fedora/RHEL, Arch, Alpine, openSUSE)
  - Windows (winget, Chocolatey, Scoop)

Usage:
  capsule install-elixir [--dry-run] [--force] [--yes] [--json]
  python3 scripts/install_elixir.py [--dry-run] [--force] [--yes] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


def configure_utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


configure_utf8_stdio()


def get_installed_versions() -> Dict[str, Optional[str]]:
    """Check if elixir and erl executables exist in PATH and get version info."""
    result: Dict[str, Optional[str]] = {"elixir": None, "erlang": None, "path": None}
    elixir_path = shutil.which("elixir")
    erl_path = shutil.which("erl")

    if elixir_path:
        result["path"] = elixir_path
        try:
            out = subprocess.check_output(
                [elixir_path, "--version"], stderr=subprocess.STDOUT, text=True, timeout=5
            )
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Elixir"):
                    result["elixir"] = line
                elif "Erlang/OTP" in line:
                    result["erlang"] = line
        except Exception:
            result["elixir"] = "installed (version unknown)"

    if not result["erlang"] and erl_path:
        result["erlang"] = f"erl found at {erl_path}"

    return result


def detect_installer() -> Tuple[str, List[List[str]], str]:
    """
    Detect the host operating system and choose the best global package manager.
    Returns: (manager_name, list_of_command_argvs, explanation)
    """
    os_name = platform.system().lower()

    # 1. Version Managers (Cross-Platform) if developer already uses them
    if shutil.which("mise"):
        return (
            "mise",
            [["mise", "use", "-g", "erlang@latest", "elixir@latest"]],
            "Using mise cross-runtime manager to install global Erlang and Elixir",
        )
    if shutil.which("asdf"):
        return (
            "asdf",
            [
                ["asdf", "plugin", "add", "erlang"],
                ["asdf", "plugin", "add", "elixir"],
                ["asdf", "install", "erlang", "latest"],
                ["asdf", "global", "erlang", "latest"],
                ["asdf", "install", "elixir", "latest"],
                ["asdf", "global", "elixir", "latest"],
            ],
            "Using asdf version manager to install Erlang and Elixir",
        )

    # 2. macOS (Darwin)
    if os_name == "darwin":
        if shutil.which("brew"):
            return (
                "homebrew",
                [["brew", "install", "elixir"]],
                "Using Homebrew to install Elixir and Erlang/OTP globally",
            )
        return (
            "unsupported",
            [],
            "macOS detected, but Homebrew ('brew') was not found. Please install Homebrew at https://brew.sh first.",
        )

    # 3. Linux
    if os_name == "linux":
        if shutil.which("apt-get"):
            return (
                "apt",
                [
                    ["sudo", "apt-get", "update"],
                    ["sudo", "apt-get", "install", "-y", "elixir", "erlang-dev", "erlang-xmerl"],
                ],
                "Using apt-get to install Elixir and Erlang packages on Debian/Ubuntu",
            )
        if shutil.which("dnf"):
            return (
                "dnf",
                [["sudo", "dnf", "install", "-y", "elixir", "erlang"]],
                "Using dnf to install Elixir and Erlang packages on Fedora/RHEL",
            )
        if shutil.which("pacman"):
            return (
                "pacman",
                [["sudo", "pacman", "-S", "--noconfirm", "elixir", "erlang"]],
                "Using pacman to install Elixir and Erlang packages on Arch Linux",
            )
        if shutil.which("apk"):
            return (
                "apk",
                [["sudo", "apk", "add", "elixir", "erlang"]],
                "Using apk to install Elixir and Erlang packages on Alpine Linux",
            )
        if shutil.which("zypper"):
            return (
                "zypper",
                [["sudo", "zypper", "install", "-y", "elixir", "erlang"]],
                "Using zypper to install Elixir and Erlang packages on openSUSE",
            )
        return (
            "unsupported",
            [],
            "Linux detected, but no supported package manager (apt, dnf, pacman, apk, zypper, mise) was found.",
        )

    # 4. Windows
    if os_name == "windows":
        if shutil.which("winget"):
            return (
                "winget",
                [
                    [
                        "winget",
                        "install",
                        "ErlangSolutions.Elixir",
                        "--accept-package-agreements",
                        "--accept-source-agreements",
                    ]
                ],
                "Using Windows Package Manager (winget) to install Elixir globally",
            )
        if shutil.which("choco"):
            return (
                "chocolatey",
                [["choco", "install", "-y", "elixir"]],
                "Using Chocolatey to install Elixir globally",
            )
        if shutil.which("scoop"):
            return (
                "scoop",
                [["scoop", "install", "elixir"]],
                "Using Scoop to install Elixir globally",
            )
        return (
            "unsupported",
            [],
            "Windows detected, but no supported package manager (winget, choco, scoop) was found.",
        )

    return (
        "unsupported",
        [],
        f"Operating system '{platform.system()}' is not directly supported by automatic installer.",
    )


def run_install(dry_run: bool = False, force: bool = False, yes: bool = False, json_mode: bool = False) -> int:
    installed = get_installed_versions()
    has_elixir = bool(installed["elixir"])

    if has_elixir and not force:
        if json_mode:
            print(
                json.dumps(
                    {
                        "status": "already_installed",
                        "elixir": installed["elixir"],
                        "erlang": installed["erlang"],
                        "path": installed["path"],
                    },
                    indent=2,
                )
            )
        else:
            print("==========================================================================")
            print(" 💧 ELIXIR & ERLANG RUNTIME STATUS (CAPSULE CORP)")
            print("==========================================================================")
            print(f" ✓ Elixir Status:  {installed['elixir']}")
            print(f" ✓ Erlang Status:  {installed['erlang']}")
            print(f" ✓ Binary Path:    {installed['path']}")
            print("--------------------------------------------------------------------------")
            print(" Runtime is ready for Actor model execution & BEAM processes.")
            print(" (Use --force to reinstall or upgrade)")
            print("==========================================================================")
        return 0

    manager, commands, explanation = detect_installer()

    if manager == "unsupported" or not commands:
        if json_mode:
            print(json.dumps({"status": "error", "error": explanation}, indent=2))
        else:
            print(f"Error: {explanation}", file=sys.stderr)
        return 1

    flat_commands = [" ".join(cmd) for cmd in commands]

    if dry_run:
        if json_mode:
            print(
                json.dumps(
                    {
                        "status": "dry_run",
                        "manager": manager,
                        "commands": flat_commands,
                        "description": explanation,
                    },
                    indent=2,
                )
            )
        else:
            print("==========================================================================")
            print(" 💧 ELIXIR GLOBAL INSTALLER (DRY RUN)")
            print("==========================================================================")
            print(f" OS / Platform:      {platform.system()} ({platform.machine()})")
            print(f" Package Manager:    {manager}")
            print(f" Plan:               {explanation}")
            print(" Commands to execute:")
            for cmd in flat_commands:
                print(f"   $ {cmd}")
            print("==========================================================================")
        return 0

    if not json_mode:
        print("==========================================================================")
        print(" 💧 INSTALLING ELIXIR & ERLANG/OTP GLOBALLY")
        print("==========================================================================")
        print(f" Package Manager: {manager}")
        print(f" Plan:            {explanation}")
        print(" Commands:")
        for cmd in flat_commands:
            print(f"   $ {cmd}")
        print("--------------------------------------------------------------------------")

    if not yes and not json_mode:
        try:
            choice = input("Proceed with installation? [y/N]: ").strip().lower()
            if choice not in ("y", "yes"):
                print("Installation aborted by user.")
                return 0
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return 1

    for cmd in commands:
        if not json_mode:
            print(f"==> Running: {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            if json_mode:
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "failed_command": " ".join(cmd),
                            "exit_code": exc.returncode,
                        },
                        indent=2,
                    )
                )
            else:
                print(f"Error: command failed with exit code {exc.returncode}", file=sys.stderr)
            return exc.returncode
        except Exception as exc:
            if json_mode:
                print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
            else:
                print(f"Error executing command: {exc}", file=sys.stderr)
            return 1

    post_check = get_installed_versions()
    if post_check["elixir"]:
        if json_mode:
            print(
                json.dumps(
                    {
                        "status": "success",
                        "elixir": post_check["elixir"],
                        "erlang": post_check["erlang"],
                        "path": post_check["path"],
                    },
                    indent=2,
                )
            )
        else:
            print("==========================================================================")
            print(" ✓ ELIXIR & ERLANG SUCCESSFULLY INSTALLED")
            print("==========================================================================")
            print(f" ✓ Elixir: {post_check['elixir']}")
            print(f" ✓ Erlang: {post_check['erlang']}")
            print(f" ✓ Binary: {post_check['path']}")
            print("==========================================================================")
        return 0
    else:
        if json_mode:
            print(
                json.dumps(
                    {
                        "status": "warning",
                        "message": "Commands finished, but 'elixir' executable not found in PATH yet. Restart terminal.",
                    },
                    indent=2,
                )
            )
        else:
            print("Warning: Commands completed, but 'elixir' was not immediately detected in PATH.")
            print("Please restart your shell or terminal session to reload your PATH environment.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Global Elixir & Erlang installer for Capsule Corp multi-agent workflows."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the detected platform and install command without running it.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force installation or upgrade even if Elixir is already present.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Automatically confirm prompt without interactive confirmation.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format.",
    )

    args = parser.parse_args()
    return run_install(dry_run=args.dry_run, force=args.force, yes=args.yes, json_mode=args.json)


if __name__ == "__main__":
    sys.exit(main())
