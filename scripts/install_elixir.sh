#!/usr/bin/env bash
# scripts/install_elixir.sh - Standalone Shell Installer for Elixir & Erlang
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/install_elixir.py"

if command -v python3 >/dev/null 2>&1; then
    exec python3 "${PYTHON_SCRIPT}" "$@"
fi

# Fallback POSIX detection if python3 is not yet installed
echo "==> Detecting host environment..."
OS="$(uname -s)"

case "${OS}" in
    Darwin)
        if command -v brew >/dev/null 2>&1; then
            echo "==> Installing Elixir via Homebrew..."
            brew install elixir
        else
            echo "Error: Homebrew is required on macOS. Install from https://brew.sh" >&2
            exit 1
        fi
        ;;
    Linux)
        if command -v apt-get >/dev/null 2>&1; then
            echo "==> Installing Elixir via apt-get..."
            sudo apt-get update && sudo apt-get install -y elixir erlang-dev erlang-xmerl
        elif command -v dnf >/dev/null 2>&1; then
            echo "==> Installing Elixir via dnf..."
            sudo dnf install -y elixir erlang
        elif command -v pacman >/dev/null 2>&1; then
            echo "==> Installing Elixir via pacman..."
            sudo pacman -S --noconfirm elixir erlang
        elif command -v apk >/dev/null 2>&1; then
            echo "==> Installing Elixir via apk..."
            sudo apk add elixir erlang
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

echo "✓ Elixir installed successfully."
elixir --version
