"""Cross-platform entry point for Capsule Corp skill synchronization."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize Capsule Corp skills and rules")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    resource_root = Path(os.environ.get("CAPSULE_RESOURCE_ROOT", Path(__file__).resolve().parent.parent)).resolve()
    shell_script = resource_root / "config" / "sync_all_ais.sh"
    if os.name == "nt":
        print("capsule sync requires a Bash environment on Windows; use Git Bash or WSL.", file=sys.stderr)
        return 1
    if not shell_script.exists():
        print(
            "Global sync is available from a Capsule Corp source checkout. "
            "The installed package supports cross-platform project initialization.",
            file=sys.stderr,
        )
        return 1

    command = ["bash", str(shell_script)]
    if args.force:
        command.append("--force")
    if args.dry_run:
        command.append("--dry-run")
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
