#!/usr/bin/env bash
# scripts/install_elixir.sh - Standalone Shell Installer for Elixir & Erlang
# Elixir is an optional installer only; the Capsule Corp agent system does not use it at runtime.
# Flags (fallback mode, when python3 is missing): --yes/-y, --dry-run, --force
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/install_elixir.py"

# Validate any --version value before forwarding (no option injection / control chars).
prev=""
for arg in "$@"; do
    val=""
    if [ "${prev}" = "--version" ]; then val="${arg}"
    elif [[ "${arg}" == --version=* ]]; then val="${arg#--version=}"
    fi
    if [ "${prev}" = "--version" ] || [[ "${arg}" == --version=* ]]; then
        if ! [[ "${val}" =~ ^[0-9][0-9A-Za-z.+_-]*$ ]] || [[ "${val}" == *$'\n'* ]]; then
            echo "Error: invalid --version; must match [0-9][0-9A-Za-z.+_-]* (e.g. 1.17.3)." >&2
            exit 2
        fi
    fi
    prev="${arg}"
done

if [ -z "${CAPSULE_INSTALL_FORCE_FALLBACK:-}" ] && command -v python3 >/dev/null 2>&1; then
    exec python3 "${PYTHON_SCRIPT}" "$@"
fi

YES=0; DRY=0; FORCE=0
for arg in "$@"; do
    case "${arg}" in
        --yes|-y) YES=1 ;;
        --dry-run) DRY=1 ;;
        --force) FORCE=1 ;;
        *) echo "Error: unsupported option '${arg}' (fallback accepts --yes, --dry-run, --force)" >&2; exit 2 ;;
    esac
done

if command -v elixir >/dev/null 2>&1 && [ "${FORCE}" -eq 0 ]; then
    echo "Elixir is already installed (use --force to reinstall)."
    elixir --version
    exit 0
fi

echo "==> Detecting host environment..."
OS="$(uname -s)"
CMDS=()
SUDO_USED=0

case "${OS}" in
    Darwin)
        if command -v brew >/dev/null 2>&1; then
            CMDS=("brew install elixir")
        else
            echo "Error: Homebrew is required on macOS. Install from https://brew.sh" >&2
            exit 1
        fi
        ;;
    Linux)
        if command -v apt-get >/dev/null 2>&1; then
            CMDS=("sudo apt-get update" "sudo apt-get install -y elixir erlang-dev erlang-xmerl"); SUDO_USED=1
        elif command -v dnf >/dev/null 2>&1; then
            CMDS=("sudo dnf install -y elixir erlang"); SUDO_USED=1
        elif command -v pacman >/dev/null 2>&1; then
            CMDS=("sudo pacman -S --noconfirm elixir erlang"); SUDO_USED=1
        elif command -v apk >/dev/null 2>&1; then
            CMDS=("sudo apk add elixir erlang"); SUDO_USED=1
        else
            echo "Error: Unsupported Linux package manager. Please install Elixir manually." >&2
            exit 1
        fi
        ;;
    *)
        echo "Error: Unsupported OS '${OS}'. Use Windows PowerShell script or manual install." >&2
        exit 1
        ;;
esac

echo "Plan:"
for c in "${CMDS[@]}"; do echo "  \$ ${c}"; done
if [ "${SUDO_USED}" -eq 1 ]; then
    echo "WARNING: this plan runs commands with sudo (administrator privileges)."
fi
echo "Note: Elixir/Erlang is an optional installer only; the agent system does not use it at runtime."

if [ "${DRY}" -eq 1 ]; then
    echo "Dry run: nothing executed."
    exit 0
fi
if [ "${YES}" -ne 1 ]; then
    echo "Refusing to install without --yes. Re-run with --yes to proceed (or --dry-run to preview)." >&2
    exit 1
fi

for c in "${CMDS[@]}"; do
    echo "==> Running: ${c}"
    # shellcheck disable=SC2086
    ${c}
done

echo "Elixir installed."
elixir --version || echo "Restart your shell to refresh PATH."
