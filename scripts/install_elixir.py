#!/usr/bin/env python3
"""
scripts/install_elixir.py - Cross-Platform Global Elixir & Erlang Installer for Capsule Corp

Idempotently detects and installs Elixir and Erlang/OTP across:
  - macOS (Homebrew, mise, asdf)
  - Linux (Debian/Ubuntu, Fedora/RHEL, Arch, Alpine, openSUSE)
  - Windows (winget, Chocolatey, Scoop)

Usage:
  capsule install-elixir [--dry-run] [--force] [--yes] [--json] [--manager M] [--version V]
  python3 scripts/install_elixir.py [same flags]

Elixir is an optional installer only; the agent system does not depend on it at runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
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


NOTICE = (
    "Note: Elixir/Erlang is currently an optional installer only. The Capsule Corp agent "
    "system does not require or use it at runtime."
)

SUDO_WARNING = (
    "WARNING: this plan runs commands with sudo (administrator privileges). "
    "Review the commands above before confirming."
)


VERSION_RE = re.compile(r"[0-9][0-9A-Za-z.+_-]*")
_CTRL_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-_]|[\x00-\x1f\x7f-\x9f]")


def sanitize_text(text: object) -> str:
    """Strip ANSI sequences and control characters (incl. newlines) from display text."""
    return _CTRL_RE.sub("", str(text))


def validate_version(version: Optional[str]) -> Optional[str]:
    """Return an error message if `version` is not a plain version string, else None."""
    if version is None:
        return None
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        return (
            f"Invalid --version {sanitize_text(version)!r}: must match "
            "[0-9][0-9A-Za-z.+_-]* (e.g. 1.17.3)."
        )
    return None


def _is_under(path: str, base: str) -> bool:
    for candidate in {os.path.abspath(path), os.path.realpath(path)}:
        try:
            b = os.path.realpath(base)
            if os.path.commonpath([candidate, b]) == b:
                return True
        except ValueError:  # different drives on Windows
            continue
    return False


def safe_which(name: str) -> Optional[str]:
    """shutil.which, but refuse any binary that lives under the current working directory."""
    found = shutil.which(name)
    if not found:
        return None
    if _is_under(found, os.getcwd()):
        return None
    return found


def get_installed_versions() -> Dict[str, Optional[str]]:
    """Check if elixir and erl executables exist in PATH and get version info.

    Binaries resolved inside the current working directory are ignored and never executed.
    """
    result: Dict[str, Optional[str]] = {"elixir": None, "erlang": None, "path": None}
    elixir_path = safe_which("elixir")
    erl_path = safe_which("erl")

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


# Managers that can pin a version.
VERSIONED = {"mise", "asdf", "winget", "chocolatey"}
OS_MANAGERS = {
    "darwin": ["homebrew"],
    "linux": ["apt", "dnf", "pacman", "apk", "zypper"],
    "windows": ["winget", "chocolatey", "scoop"],
}
BINARY = {"homebrew": "brew", "chocolatey": "choco", "apt": "apt-get"}
ALIASES = {"brew": "homebrew", "choco": "chocolatey"}


def _commands_for(manager: str, version: Optional[str]) -> Tuple[List[List[str]], str]:
    v = version
    if manager == "mise":
        spec = [f"elixir@{v}"] if v else []
        return ([["mise", "use", "-g", "erlang@latest"] + spec],
                "Using mise to install global Erlang and Elixir (edits mise's global config; "
                "Erlang uses its latest release and may compile from source)")
    if manager == "asdf":
        return (
            [
                ["asdf", "plugin", "add", "erlang"],
                ["asdf", "plugin", "add", "elixir"],
                ["asdf", "install", "erlang", "latest"],
                ["asdf", "global", "erlang", "latest"],
                ["asdf", "install", "elixir", v or "latest"],
                ["asdf", "global", "elixir", v or "latest"],
            ],
            "Using asdf (Erlang uses its latest release, is built from source, can take a long time, and edits ~/.tool-versions)",
        )
    if manager == "homebrew":
        return [["brew", "install", "elixir"]], "Using Homebrew to install Elixir and Erlang/OTP globally"
    if manager == "apt":
        return (
            [["sudo", "apt-get", "update"],
             ["sudo", "apt-get", "install", "-y", "elixir", "erlang-dev", "erlang-xmerl"]],
            "Using apt-get to install Elixir and Erlang packages on Debian/Ubuntu",
        )
    if manager == "dnf":
        return [["sudo", "dnf", "install", "-y", "elixir", "erlang"]], "Using dnf to install Elixir and Erlang packages"
    if manager == "pacman":
        return [["sudo", "pacman", "-S", "--noconfirm", "elixir", "erlang"]], "Using pacman to install Elixir and Erlang packages"
    if manager == "apk":
        return [["sudo", "apk", "add", "elixir", "erlang"]], "Using apk to install Elixir and Erlang packages"
    if manager == "zypper":
        return [["sudo", "zypper", "install", "-y", "elixir", "erlang"]], "Using zypper to install Elixir and Erlang packages"
    if manager == "winget":
        cmd = ["winget", "install", "ErlangSolutions.Elixir"]
        if v:
            cmd += ["--version", v]
        cmd += ["--accept-package-agreements", "--accept-source-agreements"]
        return [cmd], "Using Windows Package Manager (winget) to install Elixir"
    if manager == "chocolatey":
        cmd = ["choco", "install", "-y", "elixir"]
        if v:
            cmd += ["--version", v]
        return [cmd], "Using Chocolatey to install Elixir"
    if manager == "scoop":
        return [["scoop", "install", "elixir"]], "Using Scoop to install Elixir"
    raise ValueError(manager)


def detect_installer(
    manager: Optional[str] = None, version: Optional[str] = None
) -> Tuple[str, List[List[str]], str]:
    """
    Choose an installer. The OS package manager is preferred; mise/asdf are used only
    when requested with `manager` (or as a last resort when no OS manager exists).
    Returns: (manager_name, list_of_command_argvs, explanation)
    """
    bad = validate_version(version)
    if bad:
        return ("unsupported", [], bad)
    os_name = platform.system().lower()
    if manager:
        manager = ALIASES.get(manager.lower(), manager.lower())
        candidates = [manager]
    else:
        candidates = list(OS_MANAGERS.get(os_name, [])) + ["mise", "asdf"]
        if os_name not in OS_MANAGERS:
            candidates = ["mise", "asdf"]

    chosen = None
    for cand in candidates:
        if safe_which(BINARY.get(cand, cand)):
            chosen = cand
            break
    if chosen is None:
        if manager:
            return ("unsupported", [], f"Requested manager '{sanitize_text(manager)}' was not found on PATH (binaries inside the working directory are ignored).")
        hint = {"darwin": " Install Homebrew at https://brew.sh first."}.get(os_name, "")
        return ("unsupported", [], f"No supported package manager found on {platform.system()}.{hint}")

    if version and chosen not in VERSIONED:
        return (
            "unsupported",
            [],
            f"--version is not supported with '{chosen}' (it installs its repository's current package). "
            f"Use --manager mise or asdf, or winget/chocolatey on Windows.",
        )
    if chosen in ("mise", "asdf") and not version:
        return (
            "unsupported",
            [],
            f"'{chosen}' would install 'latest' silently; pass --version <elixir version> (e.g. 1.17.3) to proceed.",
        )

    commands, explanation = _commands_for(chosen, version)
    resolved = safe_which(BINARY.get(chosen, chosen))
    if resolved:
        bare = BINARY.get(chosen, chosen)
        rewritten = []
        for c in commands:
            if c and c[0] == bare:
                c = [resolved] + c[1:]
            elif len(c) > 1 and c[0] == "sudo" and c[1] == bare:
                c = ["sudo", resolved] + c[2:]
            rewritten.append(c)
        commands = rewritten
    return chosen, commands, explanation


def adjust_for_privileges(commands: List[List[str]]) -> Tuple[List[List[str]], Optional[str]]:
    """Drop `sudo` when already root; error if sudo is needed but unavailable."""
    if not any(cmd and cmd[0] == "sudo" for cmd in commands):
        return commands, None
    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        return [cmd[1:] if cmd and cmd[0] == "sudo" else cmd for cmd in commands], None
    sudo_path = safe_which("sudo")
    if not sudo_path:
        return commands, "This installer needs root privileges but a trusted 'sudo' was not found (binaries inside the working directory are ignored). Re-run as root."
    return [[sudo_path] + cmd[1:] if cmd and cmd[0] == "sudo" else cmd for cmd in commands], None


def run_install(
    dry_run: bool = False,
    force: bool = False,
    yes: bool = False,
    json_mode: bool = False,
    manager: Optional[str] = None,
    version: Optional[str] = None,
) -> int:
    bad_version = validate_version(version)
    if bad_version:
        if json_mode:
            print(json.dumps({"status": "error", "error": bad_version}, indent=2))
        else:
            print(f"Error: {bad_version}", file=sys.stderr)
        return 2
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
            print(f" {NOTICE}")
            print(" (Use --force to reinstall or upgrade)")
            print("==========================================================================")
        return 0

    manager, commands, explanation = detect_installer(manager, version)

    if manager == "unsupported" or not commands:
        if json_mode:
            print(json.dumps({"status": "error", "error": explanation}, indent=2))
        else:
            print(f"Error: {explanation}", file=sys.stderr)
        return 1

    commands, priv_error = adjust_for_privileges(commands)
    if priv_error:
        if json_mode:
            print(json.dumps({"status": "error", "error": priv_error}, indent=2))
        else:
            print(f"Error: {priv_error}", file=sys.stderr)
        return 1

    flat_commands = [sanitize_text(" ".join(cmd)) for cmd in commands]
    explanation = sanitize_text(explanation)
    uses_sudo = any(cmd and os.path.basename(cmd[0]) == "sudo" for cmd in commands)

    if dry_run:
        if json_mode:
            print(
                json.dumps(
                    {
                        "status": "dry_run",
                        "manager": manager,
                        "commands": flat_commands,
                        "description": explanation,
                        "uses_sudo": uses_sudo,
                        "note": NOTICE,
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
            if uses_sudo:
                print(f" {SUDO_WARNING}")
            print(f" {NOTICE}")
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
        if uses_sudo:
            print(f" {SUDO_WARNING}")
        print(f" {NOTICE}")
        print("--------------------------------------------------------------------------")

    if not yes:
        if json_mode:
            print(
                json.dumps(
                    {"status": "error", "error": "--json requires --yes to run an installation non-interactively."},
                    indent=2,
                )
            )
            return 2
        try:
            choice = input("Proceed with installation? [y/N]: ").strip().lower()
            if choice not in ("y", "yes"):
                print("Installation aborted by user.")
                return 1
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return 1

    for cmd in commands:
        if not json_mode:
            print(f"==> Running: {sanitize_text(' '.join(cmd))}")
        try:
            # `asdf plugin add` exits non-zero when the plugin already exists.
            tolerant = [os.path.basename(cmd[0])] + cmd[1:3] == ["asdf", "plugin", "add"]
            subprocess.run(cmd, check=not tolerant)
        except subprocess.CalledProcessError as exc:
            if json_mode:
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "failed_command": sanitize_text(" ".join(cmd)),
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
            print(f" {NOTICE}")
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

    parser.add_argument(
        "--manager",
        help="Use a specific manager (mise, asdf, brew, apt, dnf, pacman, apk, zypper, winget, choco, scoop). "
        "Default: the OS package manager.",
    )
    parser.add_argument(
        "--version",
        help="Elixir version to pin (supported by mise, asdf, winget, choco; required for mise/asdf).",
    )

    args = parser.parse_args()
    return run_install(
        dry_run=args.dry_run, force=args.force, yes=args.yes, json_mode=args.json,
        manager=args.manager, version=args.version,
    )


if __name__ == "__main__":
    sys.exit(main())
