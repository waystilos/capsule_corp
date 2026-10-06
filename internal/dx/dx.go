package dx

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// BashCompletion returns the bash autocompletion script.
func BashCompletion() string {
	return `_capsule_completions() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local commands="room clock-in clock-out heartbeat send inbox ack list route models check verify security attack grill spy validate scaffold init doctor serve hook completion install"
    local bots="@bulma @goku @trunks @piccolo @whis @android-17 @cell @king-kai @android-18 @videl @vegeta @roshi @hercule @zarbon @dr-gero @goten @android-16 @beerus"
    local tools="gemini copilot claude cursor windsurf codex all"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return 0
    fi

    case "${COMP_WORDS[1]}" in
        init)
            case "$prev" in
                --tool)
                    COMPREPLY=( $(compgen -W "$tools" -- "$cur") )
                    return 0
                    ;;
            esac
            COMPREPLY=( $(compgen -W "--tool --force" -- "$cur") )
            ;;
        route)
            case "$prev" in
                --bot)
                    COMPREPLY=( $(compgen -W "$bots" -- "$cur") )
                    return 0
                    ;;
                --tier)
                    COMPREPLY=( $(compgen -W "flash pro premium" -- "$cur") )
                    return 0
                    ;;
            esac
            COMPREPLY=( $(compgen -W "--bot --tier --json" -- "$cur") )
            ;;
        send)
            case "$prev" in
                --to)
                    COMPREPLY=( $(compgen -W "$bots" -- "$cur") )
                    return 0
                    ;;
            esac
            COMPREPLY=( $(compgen -W "--to --body --file" -- "$cur") )
            ;;
        hook)
            COMPREPLY=( $(compgen -W "install uninstall" -- "$cur") )
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") )
            ;;
        clock-in)
            COMPREPLY=( $(compgen -W "--task --files --role --agent --force" -- "$cur") )
            ;;
        clock-out)
            COMPREPLY=( $(compgen -W "--summary --session --agent" -- "$cur") )
            ;;
        serve)
            COMPREPLY=( $(compgen -W "--port --host" -- "$cur") )
            ;;
    esac
}
complete -F _capsule_completions capsule
`
}

// ZshCompletion returns the zsh autocompletion script.
func ZshCompletion() string {
	return `#compdef capsule

_capsule() {
    local -a commands
    commands=(
        'room:Display active check-in room status'
        'clock-in:Claim active shift and files'
        'clock-out:Conclude active shift'
        'heartbeat:Refresh active shift heartbeat'
        'send:Send message to agent inbox'
        'inbox:Read messages for agent'
        'ack:Acknowledge message by ID'
        'list:List cohort roster and model mappings'
        'route:Route task request to agent'
        'models:Inspect model tier resolution'
        'check:Execute project checks and gates'
        'verify:Deterministic verification gate'
        'security:Scan codebase for exposed secrets'
        'attack:Run red-team prompt injection checks'
        'grill:Architectural inquisition'
        'spy:Watchdog audit for scope drift'
        'validate:Evaluate product idea'
        'scaffold:Generate new bot definition'
        'init:Initialize multi-AI tool configuration'
        'doctor:Diagnose environment health'
        'serve:Run as HTTP REST service daemon'
        'hook:Manage Git verification hooks (install/uninstall)'
        'completion:Generate shell autocompletion script'
        'install:Install capsule binary into system path'
    )

    local -a bots
    bots=(@bulma @goku @trunks @piccolo @whis @android-17 @cell @king-kai @android-18 @videl @vegeta @roshi @hercule @zarbon @dr-gero @goten @android-16 @beerus)

    local -a tools
    tools=(gemini copilot claude cursor windsurf codex all)

    if (( CURRENT == 2 )); then
        _describe -t commands 'capsule commands' commands
    else
        case "$words[2]" in
            init)
                _arguments '--tool[Target AI tool]:tool:($tools)' '--force[Overwrite existing configuration]'
                ;;
            route)
                _arguments '--bot[Target bot archetype]:bot:($bots)' '--tier[Model tier]:tier:(flash pro premium)' '--json[Output JSON]'
                ;;
            send)
                _arguments '--to[Recipient agent]:recipient:($bots)' '--body[Message body]:body:' '--file[Message file]:file:_files'
                ;;
            hook)
                _values 'hook action' 'install' 'uninstall'
                ;;
            completion)
                _values 'shell' 'bash' 'zsh' 'fish'
                ;;
            serve)
                _arguments '--port[HTTP service port]:port:' '--host[HTTP service host]:host:'
                ;;
        esac
    fi
}

_capsule "$@"
`
}

// FishCompletion returns the fish autocompletion script.
func FishCompletion() string {
	return `# fish completion for capsule
set -l commands room clock-in clock-out heartbeat send inbox ack list route models check verify security attack grill spy validate scaffold init doctor serve hook completion install

complete -c capsule -f
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a room -d "Display active check-in room status"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a clock-in -d "Claim active shift and files"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a clock-out -d "Conclude active shift"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a heartbeat -d "Refresh active shift heartbeat"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a send -d "Send message to agent inbox"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a inbox -d "Read messages for agent"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a ack -d "Acknowledge message by ID"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a list -d "List cohort roster"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a route -d "Route task request"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a check -d "Execute project checks and gates"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a verify -d "Deterministic verification gate"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a security -d "Scan codebase for exposed secrets"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a attack -d "Run red-team fuzzing checks"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a grill -d "Architectural inquisition"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a spy -d "Watchdog audit for scope drift"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a validate -d "Evaluate product idea"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a scaffold -d "Generate new bot definition"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a init -d "Initialize multi-AI tool configuration"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a doctor -d "Diagnose environment health"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a serve -d "Run as HTTP REST service daemon"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a hook -d "Manage Git pre-commit hooks"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a completion -d "Generate shell autocompletions"
complete -c capsule -n "not __fish_seen_subcommand_from $commands" -a install -d "Install capsule binary into system path"

complete -c capsule -n "__fish_seen_subcommand_from hook" -a "install uninstall"
complete -c capsule -n "__fish_seen_subcommand_from completion" -a "bash zsh fish"
complete -c capsule -n "__fish_seen_subcommand_from init" -l tool -a "gemini copilot claude cursor windsurf codex all"
`
}

const PreCommitHookContent = `#!/bin/sh
# Capsule Corp Pre-Commit Verification Gate
set -e

if command -v capsule >/dev/null 2>&1; then
    capsule check . --trust
elif [ -x "./bin/capsule" ]; then
    ./bin/capsule check . --trust
fi
`

// InstallGitHook installs the pre-commit verification gate into .git/hooks/pre-commit.
func InstallGitHook(repoRoot string) (string, error) {
	hooksDir := filepath.Join(repoRoot, ".git", "hooks")
	if err := os.MkdirAll(hooksDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create git hooks directory: %w", err)
	}

	hookFile := filepath.Join(hooksDir, "pre-commit")
	if err := os.WriteFile(hookFile, []byte(PreCommitHookContent), 0755); err != nil {
		return "", fmt.Errorf("failed to write pre-commit hook: %w", err)
	}

	return hookFile, nil
}

// UninstallGitHook removes the pre-commit verification hook.
func UninstallGitHook(repoRoot string) error {
	hookFile := filepath.Join(repoRoot, ".git", "hooks", "pre-commit")
	if _, err := os.Stat(hookFile); os.IsNotExist(err) {
		return nil
	}
	return os.Remove(hookFile)
}

// InstallBinary copies the capsule binary to ~/.local/bin or GOPATH/bin.
func InstallBinary(sourceBinary string) (string, bool, error) {
	if _, err := os.Stat(sourceBinary); err != nil {
		return "", false, fmt.Errorf("source binary not found: %s", sourceBinary)
	}

	// Target directory resolution:
	// 1. $GOPATH/bin if GOPATH set
	// 2. $HOME/.local/bin (standard XDG user binary dir)
	targetDir := ""
	if gopath := os.Getenv("GOPATH"); gopath != "" {
		targetDir = filepath.Join(gopath, "bin")
	} else if home, err := os.UserHomeDir(); err == nil {
		targetDir = filepath.Join(home, ".local", "bin")
	} else {
		targetDir = "/usr/local/bin"
	}

	if err := os.MkdirAll(targetDir, 0755); err != nil {
		return "", false, fmt.Errorf("failed to create target directory %s: %w", targetDir, err)
	}

	targetBinary := filepath.Join(targetDir, "capsule")
	if strings.HasSuffix(sourceBinary, ".exe") {
		targetBinary += ".exe"
	}

	// Copy file
	src, err := os.Open(sourceBinary)
	if err != nil {
		return "", false, err
	}
	defer src.Close()

	dst, err := os.OpenFile(targetBinary, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
	if err != nil {
		return "", false, err
	}
	defer dst.Close()

	if _, err := io.Copy(dst, src); err != nil {
		return "", false, err
	}

	// Check if in PATH
	inPath := false
	if pathVar := os.Getenv("PATH"); pathVar != "" {
		paths := filepath.SplitList(pathVar)
		for _, p := range paths {
			if filepath.Clean(p) == filepath.Clean(targetDir) {
				inPath = true
				break
			}
		}
	}

	if !inPath {
		if _, err := exec.LookPath("capsule"); err == nil {
			inPath = true
		}
	}

	return targetBinary, inPath, nil
}
