# Multi-Agent Support Design

**Date:** 2026-05-19
**Status:** Approved

## Goal

Expand the devcontainer from Claude Code-only to support Claude Code, Codex, and Pi — all installed in a single container. Rebrand from "Claude Code Devcontainer" to "Agentic Devcontainer".

## Agents

| Agent | Install | Auth env vars | Auto-approve |
|-------|---------|---------------|--------------|
| Claude Code | `claude.ai/install.sh` (existing) | `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY` | `bypassPermissions` in `settings.json` |
| Codex | `npm install -g @openai/codex` | `OPENAI_API_KEY`, `CODEX_ACCESS_TOKEN` | `approval_mode = "full-auto"` in `~/.codex/config.toml` |
| Pi | `npm install -g @earendil-works/pi-coding-agent` | TBD (auto-approve by default) | Default behaviour |

Codex supports device code login (headless, no browser required) as well as API key auth via `OPENAI_API_KEY`.

## Architecture

Introduce an `agents/` package alongside `post_install.py`. Each agent owns its setup logic in its own module. `post_install.py` becomes a thin orchestrator.

```
agents/
  __init__.py
  claude.py     ← onboarding bypass + bypassPermissions settings
  codex.py      ← full-auto approval config
  pi.py         ← minimal placeholder (auto-approve by default)
post_install.py ← shared setup + calls agent setup() functions
```

Each module exports a single `setup()` function. `post_install.py` calls them in sequence after running shared setup (tmux, gitignore, directory ownership).

## File Changes

### `agents/__init__.py`
Empty — marks the directory as a Python package.

### `agents/claude.py`
Moves `setup_onboarding_bypass()` and `setup_claude_settings()` out of `post_install.py` verbatim. Exports `setup()` which calls both.

### `agents/codex.py`
Writes `~/.codex/config.toml` with `approval_mode = "full-auto"`. Skips if file already exists. Logs whether `OPENAI_API_KEY` / `CODEX_ACCESS_TOKEN` are present (does not validate them). Exports `setup()`.

### `agents/pi.py`
No approval config needed (Pi is auto-approve by default). Logs presence of any Pi auth env var if discovered. Exports `setup()` as a no-op placeholder.

### `post_install.py`
- Retains shared functions: `setup_tmux_config`, `fix_directory_ownership`, `setup_global_gitignore`
- Removes `setup_onboarding_bypass` and `setup_claude_settings` (moved to `agents/claude.py`)
- `main()` imports and calls `claude.setup()`, `codex.setup()`, `pi.setup()`

### `Dockerfile`
- Rename top comment to "Agentic Devcontainer"
- Add after existing Claude install block:
  ```dockerfile
  RUN npm install -g @openai/codex
  RUN npm install -g @earendil-works/pi-coding-agent
  ```
- Add `COPY --chown=vscode:vscode agents/ /opt/agents/` after the existing `post_install.py` COPY line

### `devcontainer.json`
- `name`: `"Agentic Devcontainer"` (was `"Claude Code Sandbox"`)
- Add to `remoteEnv`:
  ```json
  "OPENAI_API_KEY": "${localEnv:OPENAI_API_KEY:}",
  "CODEX_ACCESS_TOKEN": "${localEnv:CODEX_ACCESS_TOKEN:}"
  ```

### `install.sh`
- Rename top comment to "Agentic Devcontainer CLI Helper"
- Rename the CLI command from `devc` to `devx` throughout (usage text, log messages, self-install target path `~/.local/bin/devx`, symlink name)
- `cmd_upgrade`: run all three upgrade commands in sequence:
  1. `claude update`
  2. `npm install -g @openai/codex@latest`
  3. `npm install -g @earendil-works/pi-coding-agent@latest`
- Log message changes: replace "Claude Code" references with "agents" where generic

### `README.md`
- Title: `# Agentic Devcontainer`
- Rebrand throughout (remove Claude Code-specific framing in intro/overview)
- Add section documenting each agent, its auth env vars, and how to configure tokens
- Update container details table to list all three agents
- Rename repo clone path in quick-start examples to `~/.agentic-devcontainer`
- Replace all `devc` command references with `devx`

## What Does Not Change

- Container base image, system packages, volumes, mounts
- `devx` command names and behaviour (except `upgrade`)
- `devc sync` (Claude Code session sync — remains Claude-specific)
- `setup_tmux_config`, `fix_directory_ownership`, `setup_global_gitignore`
- Security model (filesystem isolation, `bypassPermissions` concept extended to all agents)

## Out of Scope

- Per-agent container selection (all agents installed in every container)
- `devc sync` for Codex/Pi sessions
- Pi auth env var (unknown at time of writing; `agents/pi.py` is a placeholder)
