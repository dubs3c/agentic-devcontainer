# Multi-Agent Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the devcontainer to support Claude Code, Codex, and Pi in a single container, and rebrand from "Claude Code Devcontainer" to "Agentic Devcontainer" with `devx` as the CLI command.

**Architecture:** Introduce an `agents/` Python package where each agent owns its setup logic in a module exporting a `setup()` function. `post_install.py` becomes a thin orchestrator that calls each agent's `setup()` after running shared infrastructure setup. All other files (Dockerfile, devcontainer.json, install.sh, README) are updated to include the new agents and drop Claude-specific branding.

**Tech Stack:** Python 3.13, pytest (via uv), TOML (stdlib `tomllib`/write manually), Bash, Docker devcontainers

---

## File Map

**Created:**
- `agents/__init__.py` — package marker (empty)
- `agents/claude.py` — onboarding bypass + bypassPermissions settings
- `agents/codex.py` — full-auto approval config + auth token logging
- `agents/pi.py` — no-op placeholder (Pi is auto-approve by default)
- `tests/__init__.py` — test package marker (empty)
- `tests/test_agents_claude.py` — tests for agents/claude.py
- `tests/test_agents_codex.py` — tests for agents/codex.py
- `tests/test_agents_pi.py` — tests for agents/pi.py

**Modified:**
- `post_install.py` — remove Claude-specific functions, add agent imports + calls
- `Dockerfile` — add Codex/Pi installs, rename comment, add `agents/` COPY
- `devcontainer.json` — rename to "Agentic Devcontainer", add OPENAI_API_KEY + CODEX_ACCESS_TOKEN
- `install.sh` — rename `devc` → `devx` throughout, update `cmd_upgrade`, update clone path reference
- `README.md` — full rebrand: title, intro, agent auth docs, container table, all `devc` → `devx`

---

## Task 1: Create agents package + test scaffold

**Files:**
- Create: `agents/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create the agents package**

```bash
mkdir -p agents tests
touch agents/__init__.py tests/__init__.py
```

- [ ] **Step 2: Verify Python can import it**

```bash
uv run --no-project python -c "import agents; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add agents/__init__.py tests/__init__.py
git commit -m "chore: scaffold agents package and tests directory"
```

---

## Task 2: Implement agents/claude.py

Moves `setup_onboarding_bypass()` and `setup_claude_settings()` out of `post_install.py` into a dedicated module.

**Files:**
- Create: `agents/claude.py`
- Create: `tests/test_agents_claude.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_agents_claude.py`:

```python
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_setup_claude_settings_creates_file(tmp_path, monkeypatch):
    """setup() writes bypassPermissions to settings.json."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import claude
    claude.setup()

    settings = json.loads((tmp_path / "settings.json").read_text())
    assert settings["permissions"]["defaultMode"] == "bypassPermissions"


def test_setup_claude_settings_preserves_existing_keys(tmp_path, monkeypatch):
    """setup() merges into existing settings without clobbering other keys."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

    existing = {"someOtherKey": "someValue"}
    (tmp_path / "settings.json").write_text(json.dumps(existing))

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import claude
    claude.setup()

    settings = json.loads((tmp_path / "settings.json").read_text())
    assert settings["someOtherKey"] == "someValue"
    assert settings["permissions"]["defaultMode"] == "bypassPermissions"


def test_setup_skips_onboarding_bypass_when_no_token(tmp_path, monkeypatch, capsys):
    """setup() skips onboarding bypass when CLAUDE_CODE_OAUTH_TOKEN is not set."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import claude
    claude.setup()

    captured = capsys.readouterr()
    assert "skipping onboarding bypass" in captured.err


def test_setup_onboarding_bypass_sets_flag(tmp_path, monkeypatch):
    """setup() sets hasCompletedOnboarding when token is set and claude -p succeeds."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "fake-token")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))

    # Simulate claude -p writing the config file then timing out
    def fake_run(cmd, **kwargs):
        (tmp_path / ".claude.json").write_text("{}")
        raise subprocess.TimeoutExpired(cmd, 30)

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import claude
    with patch("subprocess.run", side_effect=fake_run):
        claude.setup()

    config = json.loads((tmp_path / ".claude.json").read_text())
    assert config["hasCompletedOnboarding"] is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --no-project --with pytest pytest tests/test_agents_claude.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` — `agents.claude` does not exist yet.

- [ ] **Step 3: Create agents/claude.py**

Copy `setup_onboarding_bypass` and `setup_claude_settings` from `post_install.py` verbatim, then wrap in `setup()`:

```python
#!/usr/bin/env python3
"""Claude Code agent setup for the Agentic Devcontainer."""

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path


def setup_onboarding_bypass():
    """Bypass the interactive onboarding wizard when CLAUDE_CODE_OAUTH_TOKEN is set.

    Runs `claude -p` to seed ~/.claude.json with auth state. The subprocess
    writes the config file during startup before the API call completes, so
    a timeout is expected and acceptable. After the subprocess finishes (or
    times out), we check whether ~/.claude.json was populated and only then
    set hasCompletedOnboarding.

    Workaround for https://github.com/anthropics/claude-code/issues/8938.
    """
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not token:
        print(
            "[post_install] No CLAUDE_CODE_OAUTH_TOKEN set, skipping onboarding bypass",
            file=sys.stderr,
        )
        return

    # When `CLAUDE_CONFIG_DIR` is set, claude looks for `.claude.json` in that
    # folder instead of `~`. See https://github.com/anthropics/claude-code/issues/3833
    claude_json_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home()))
    claude_json = claude_json_dir / ".claude.json"

    print("[post_install] Running claude -p to populate auth state...", file=sys.stderr)
    try:
        result = subprocess.run(
            ["claude", "-p", "ok"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(
                f"[post_install] claude -p exited {result.returncode}: "
                f"{result.stderr.strip()}",
                file=sys.stderr,
            )
    except subprocess.TimeoutExpired:
        print(
            "[post_install] claude -p timed out (expected on cold start)",
            file=sys.stderr,
        )
    except (FileNotFoundError, OSError) as e:
        print(
            f"[post_install] Warning: could not run claude ({e}) — "
            "onboarding bypass skipped",
            file=sys.stderr,
        )
        return

    if not claude_json.exists():
        print(
            f"[post_install] Warning: {claude_json} not created by claude -p — "
            "onboarding bypass skipped",
            file=sys.stderr,
        )
        return

    config: dict = {}
    try:
        config = json.loads(claude_json.read_text())
    except json.JSONDecodeError as e:
        print(
            f"[post_install] Warning: {claude_json} has invalid JSON ({e}), "
            "starting fresh",
            file=sys.stderr,
        )

    config["hasCompletedOnboarding"] = True
    claude_json.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(
        f"[post_install] Onboarding bypass configured: {claude_json}", file=sys.stderr
    )


def setup_claude_settings():
    """Configure Claude Code with bypassPermissions enabled."""
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    claude_dir.mkdir(parents=True, exist_ok=True)

    settings_file = claude_dir / "settings.json"

    settings = {}
    if settings_file.exists():
        with contextlib.suppress(json.JSONDecodeError):
            settings = json.loads(settings_file.read_text())

    if "permissions" not in settings:
        settings["permissions"] = {}
    settings["permissions"]["defaultMode"] = "bypassPermissions"

    settings_file.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(
        f"[post_install] Claude settings configured: {settings_file}", file=sys.stderr
    )


def setup():
    """Run all Claude Code setup steps."""
    setup_onboarding_bypass()
    setup_claude_settings()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --no-project --with pytest pytest tests/test_agents_claude.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/claude.py tests/test_agents_claude.py
git commit -m "feat: add agents/claude.py with onboarding bypass and settings setup"
```

---

## Task 3: Implement agents/codex.py

**Files:**
- Create: `agents/codex.py`
- Create: `tests/test_agents_codex.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_agents_codex.py`:

```python
import sys
from pathlib import Path

import pytest


def test_setup_writes_config_toml(tmp_path, monkeypatch):
    """setup() creates ~/.codex/config.toml with approval_mode = full-auto."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_ACCESS_TOKEN", raising=False)

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import codex
    codex.setup()

    config_file = tmp_path / ".codex" / "config.toml"
    assert config_file.exists()
    content = config_file.read_text()
    assert 'approval_mode = "full-auto"' in content


def test_setup_skips_if_config_exists(tmp_path, monkeypatch, capsys):
    """setup() skips writing config.toml if it already exists."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_ACCESS_TOKEN", raising=False)

    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir(parents=True)
    config_file = codex_dir / "config.toml"
    config_file.write_text('approval_mode = "ask"\n')

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import codex
    codex.setup()

    # File should not have been overwritten
    assert config_file.read_text() == 'approval_mode = "ask"\n'
    captured = capsys.readouterr()
    assert "exists, skipping" in captured.err


def test_setup_logs_openai_api_key_present(tmp_path, monkeypatch, capsys):
    """setup() logs that OPENAI_API_KEY is set."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.delenv("CODEX_ACCESS_TOKEN", raising=False)

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import codex
    codex.setup()

    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.err


def test_setup_logs_codex_access_token_present(tmp_path, monkeypatch, capsys):
    """setup() logs that CODEX_ACCESS_TOKEN is set."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CODEX_ACCESS_TOKEN", "fake-token")

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import codex
    codex.setup()

    captured = capsys.readouterr()
    assert "CODEX_ACCESS_TOKEN" in captured.err
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --no-project --with pytest pytest tests/test_agents_codex.py -v 2>&1 | head -20
```

Expected: `ImportError` — `agents.codex` does not exist yet.

- [ ] **Step 3: Create agents/codex.py**

```python
#!/usr/bin/env python3
"""Codex agent setup for the Agentic Devcontainer."""

import os
import sys
from pathlib import Path


def setup():
    """Configure Codex with full-auto approval mode."""
    codex_dir = Path.home() / ".codex"
    config_file = codex_dir / "config.toml"

    if config_file.exists():
        print(
            f"[post_install] Codex config exists, skipping: {config_file}",
            file=sys.stderr,
        )
    else:
        codex_dir.mkdir(parents=True, exist_ok=True)
        config_file.write_text('approval_mode = "full-auto"\n', encoding="utf-8")
        print(
            f"[post_install] Codex configured (full-auto): {config_file}",
            file=sys.stderr,
        )

    # Log auth token presence (values are never logged)
    if os.environ.get("OPENAI_API_KEY"):
        print("[post_install] OPENAI_API_KEY is set", file=sys.stderr)
    else:
        print("[post_install] OPENAI_API_KEY not set — Codex will prompt for login", file=sys.stderr)

    if os.environ.get("CODEX_ACCESS_TOKEN"):
        print("[post_install] CODEX_ACCESS_TOKEN is set", file=sys.stderr)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --no-project --with pytest pytest tests/test_agents_codex.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/codex.py tests/test_agents_codex.py
git commit -m "feat: add agents/codex.py with full-auto approval config"
```

---

## Task 4: Implement agents/pi.py

**Files:**
- Create: `agents/pi.py`
- Create: `tests/test_agents_pi.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_agents_pi.py`:

```python
import sys
from pathlib import Path

import pytest


def test_setup_runs_without_error(capsys):
    """setup() completes without raising."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import pi
    pi.setup()  # must not raise


def test_setup_logs_something(capsys):
    """setup() emits at least one log line so operators know it ran."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import pi
    pi.setup()

    captured = capsys.readouterr()
    assert captured.err.strip() != ""
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --no-project --with pytest pytest tests/test_agents_pi.py -v 2>&1 | head -20
```

Expected: `ImportError` — `agents.pi` does not exist yet.

- [ ] **Step 3: Create agents/pi.py**

```python
#!/usr/bin/env python3
"""Pi agent setup for the Agentic Devcontainer.

Pi is auto-approve by default — no approval config required.
Auth env var is TBD; this module is a placeholder for future setup steps.
"""

import sys


def setup():
    """Pi setup — no-op (auto-approve by default)."""
    print(
        "[post_install] Pi agent: auto-approve is default, no config needed",
        file=sys.stderr,
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --no-project --with pytest pytest tests/test_agents_pi.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/pi.py tests/test_agents_pi.py
git commit -m "feat: add agents/pi.py placeholder (auto-approve by default)"
```

---

## Task 5: Refactor post_install.py to use agents package

Remove `setup_onboarding_bypass` and `setup_claude_settings`, add `sys.path` setup and agent calls.

**Files:**
- Modify: `post_install.py`

- [ ] **Step 1: Read the current post_install.py**

```bash
# Confirm the functions to remove
grep -n "def setup_" post_install.py
```

Expected output shows `setup_onboarding_bypass`, `setup_claude_settings`, `setup_tmux_config`, `fix_directory_ownership`, `setup_global_gitignore`.

- [ ] **Step 2: Rewrite post_install.py**

Replace the entire file contents with:

```python
#!/usr/bin/env python3
"""Post-install configuration for the Agentic Devcontainer.

Runs on container creation to set up:
- Each coding agent (Claude Code, Codex, Pi)
- Tmux configuration (200k history, mouse support)
- Directory ownership fixes for mounted volumes
- Global gitignore
"""

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

# agents/ lives alongside this script in /opt/
sys.path.insert(0, str(Path(__file__).parent))
from agents import claude, codex, pi


def setup_tmux_config():
    """Configure tmux with 200k history, mouse support, and vi keys."""
    tmux_conf = Path.home() / ".tmux.conf"

    if tmux_conf.exists():
        print("[post_install] Tmux config exists, skipping", file=sys.stderr)
        return

    config = """\
# 200k line scrollback history
set-option -g history-limit 200000

# Enable mouse support
set -g mouse on

# Use vi keys in copy mode
setw -g mode-keys vi

# Start windows and panes at 1, not 0
set -g base-index 1
setw -g pane-base-index 1

# Renumber windows when one is closed
set -g renumber-windows on

# Faster escape time for vim
set -sg escape-time 10

# True color support
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"

# Terminal features (ghostty, cursor shape in vim)
set -as terminal-features ",xterm-ghostty:RGB"
set -as terminal-features ",xterm*:RGB"
set -ga terminal-overrides ",xterm*:colors=256"
set -ga terminal-overrides '*:Ss=\\E[%p1%d q:Se=\\E[ q'

# Status bar
set -g status-style 'bg=#333333 fg=#ffffff'
set -g status-left '[#S] '
set -g status-right '%Y-%m-%d %H:%M'
"""
    tmux_conf.write_text(config, encoding="utf-8")
    print(f"[post_install] Tmux configured: {tmux_conf}", file=sys.stderr)


def fix_directory_ownership():
    """Fix ownership of mounted volumes that may have root ownership."""
    uid = os.getuid()
    gid = os.getgid()

    dirs_to_fix = [
        Path.home() / ".claude",
        Path("/commandhistory"),
        Path.home() / ".config" / "gh",
    ]

    for dir_path in dirs_to_fix:
        if dir_path.exists():
            try:
                stat_info = dir_path.stat()
                if stat_info.st_uid != uid:
                    subprocess.run(
                        ["sudo", "chown", "-R", f"{uid}:{gid}", str(dir_path)],
                        check=True,
                        capture_output=True,
                    )
                    print(
                        f"[post_install] Fixed ownership: {dir_path}", file=sys.stderr
                    )
            except (PermissionError, subprocess.CalledProcessError) as e:
                print(
                    f"[post_install] Warning: Could not fix ownership of {dir_path}: {e}",
                    file=sys.stderr,
                )


def setup_global_gitignore():
    """Set up global gitignore and local git config.

    Since ~/.gitconfig is mounted read-only from host, we create a local
    config file that includes the host config and adds container-specific
    settings like core.excludesfile and delta configuration.

    GIT_CONFIG_GLOBAL env var (set in devcontainer.json) points git to this
    local config as the "global" config.
    """
    home = Path.home()
    gitignore = home / ".gitignore_global"
    local_gitconfig = home / ".gitconfig.local"
    host_gitconfig = home / ".gitconfig"

    patterns = """\
# Claude Code
.claude/

# macOS
.DS_Store
.AppleDouble
.LSOverride
._*

# Python
*.pyc
*.pyo
__pycache__/
*.egg-info/
.eggs/
*.egg
.venv/
venv/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
.npm/

# Editors
*.swp
*.swo
*~
.idea/
.vscode/
*.sublime-*

# Misc
*.log
.env.local
.env.*.local
"""
    gitignore.write_text(patterns, encoding="utf-8")
    print(f"[post_install] Global gitignore created: {gitignore}", file=sys.stderr)

    local_config = f"""\
# Container-local git config
# Includes host config (mounted read-only) and adds container settings

[include]
    path = {host_gitconfig}

[core]
    excludesfile = {gitignore}
    pager = delta

[interactive]
    diffFilter = delta --color-only

[delta]
    navigate = true
    light = false
    line-numbers = true
    side-by-side = false

[merge]
    conflictstyle = diff3

[diff]
    colorMoved = default

[gpg "ssh"]
    program = /usr/bin/ssh-keygen
"""
    local_gitconfig.write_text(local_config, encoding="utf-8")
    print(
        f"[post_install] Local git config created: {local_gitconfig}", file=sys.stderr
    )


def main():
    """Run all post-install configuration."""
    print("[post_install] Starting post-install configuration...", file=sys.stderr)

    fix_directory_ownership()
    setup_tmux_config()
    setup_global_gitignore()

    claude.setup()
    codex.setup()
    pi.setup()

    print("[post_install] Configuration complete!", file=sys.stderr)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run full test suite to confirm nothing broke**

```bash
uv run --no-project --with pytest pytest tests/ -v
```

Expected: all tests PASS (6 or more).

- [ ] **Step 4: Commit**

```bash
git add post_install.py
git commit -m "refactor: post_install.py delegates to agents package"
```

---

## Task 6: Update Dockerfile

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Update top comment**

In `Dockerfile` line 1, change:
```dockerfile
# Claude Code Devcontainer
```
to:
```dockerfile
# Agentic Devcontainer
```

- [ ] **Step 2: Add Codex and Pi installs**

After the existing Claude Code install block (the `RUN curl -fsSL https://claude.ai/install.sh | bash ...` block), add:

```dockerfile
# Install Codex
RUN npm install -g @openai/codex

# Install Pi coding agent
RUN npm install -g @earendil-works/pi-coding-agent
```

Note: these use fnm-managed Node. They must appear after fnm is set up and `PATH` includes fnm's node. Verify the install block for Claude Code already works with this PATH — if yes, Codex and Pi installs go right after it.

- [ ] **Step 3: Add agents/ COPY**

After the existing line:
```dockerfile
COPY --chown=vscode:vscode post_install.py /opt/post_install.py
```
Add:
```dockerfile
COPY --chown=vscode:vscode agents/ /opt/agents/
```

- [ ] **Step 4: Verify Dockerfile syntax**

```bash
docker build --no-cache --dry-run . 2>&1 | head -20
```

If `--dry-run` is not supported by your Docker version, just check for obvious syntax errors:
```bash
grep -n "COPY\|RUN npm" Dockerfile
```

Confirm the `agents/` COPY line appears and the npm install lines are present.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile
git commit -m "feat: install Codex and Pi in Dockerfile, copy agents package"
```

---

## Task 7: Update devcontainer.json

**Files:**
- Modify: `devcontainer.json`

- [ ] **Step 1: Update name**

Change line:
```json
"name": "Claude Code Sandbox",
```
to:
```json
"name": "Agentic Devcontainer",
```

- [ ] **Step 2: Add Codex auth env vars**

In the `"remoteEnv"` block, after the existing `ANTHROPIC_API_KEY` entry, add:

```json
"OPENAI_API_KEY": "${localEnv:OPENAI_API_KEY:}",
"CODEX_ACCESS_TOKEN": "${localEnv:CODEX_ACCESS_TOKEN:}"
```

The final `remoteEnv` block should look like:
```json
"remoteEnv": {
  "CLAUDE_CODE_OAUTH_TOKEN": "${localEnv:CLAUDE_CODE_OAUTH_TOKEN:}",
  "ANTHROPIC_API_KEY": "${localEnv:ANTHROPIC_API_KEY:}",
  "OPENAI_API_KEY": "${localEnv:OPENAI_API_KEY:}",
  "CODEX_ACCESS_TOKEN": "${localEnv:CODEX_ACCESS_TOKEN:}"
},
```

- [ ] **Step 3: Verify valid JSON**

```bash
python3 -c "import json; json.load(open('devcontainer.json')); print('valid')"
```

Expected: `valid`

- [ ] **Step 4: Commit**

```bash
git add devcontainer.json
git commit -m "feat: rename to Agentic Devcontainer, add Codex auth env vars"
```

---

## Task 8: Update install.sh — rename devc → devx and update upgrade

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Rename the top comment**

Change line 4:
```bash
# Claude Code Devcontainer CLI Helper
# Provides the `devc` command for managing devcontainers
```
to:
```bash
# Agentic Devcontainer CLI Helper
# Provides the `devx` command for managing devcontainers
```

- [ ] **Step 2: Replace all `devc` references with `devx` in usage text and log messages**

In `print_usage()`, replace every occurrence of `devc` with `devx`. The usage block starting at line 25 should read `Usage: devx <command>` and all examples should use `devx`.

Also update `cmd_self_install`:
- Change `local install_path="$install_dir/devc"` to `local install_path="$install_dir/devx"`
- Change the success message from `"Installed 'devc' to $install_path"` to `"Installed 'devx' to $install_path"`

- [ ] **Step 3: Update cmd_upgrade to upgrade all three agents**

Replace the current `cmd_upgrade` function body:

```bash
cmd_upgrade() {
  local workspace_folder
  workspace_folder="$(get_workspace_folder)"

  check_devcontainer_cli
  log_info "Upgrading Claude Code..."

  devcontainer exec --workspace-folder "$workspace_folder" claude update

  log_success "Claude Code upgraded"
}
```

with:

```bash
cmd_upgrade() {
  local workspace_folder
  workspace_folder="$(get_workspace_folder)"

  check_devcontainer_cli
  log_info "Upgrading all agents..."

  devcontainer exec --workspace-folder "$workspace_folder" claude update
  devcontainer exec --workspace-folder "$workspace_folder" npm install -g @openai/codex@latest
  devcontainer exec --workspace-folder "$workspace_folder" npm install -g @earendil-works/pi-coding-agent@latest

  log_success "All agents upgraded"
}
```

- [ ] **Step 4: Update the clone path reference in cmd_update**

In `cmd_update`, find the error message that references `~/.claude-devcontainer`:
```bash
log_info "Re-clone with: rm -rf ~/.claude-devcontainer && git clone https://github.com/trailofbits/claude-code-devcontainer ~/.claude-devcontainer"
```
Change to:
```bash
log_info "Re-clone with: rm -rf ~/.agentic-devcontainer && git clone https://github.com/trailofbits/agentic-devcontainer ~/.agentic-devcontainer"
```

- [ ] **Step 5: Verify no remaining `devc` references in user-facing strings**

```bash
grep -n "\bdevc\b" install.sh
```

Expected: zero matches (only `devx` in user-facing text). Any matches in internal variable names or comments that don't affect user output can remain but should be reviewed.

- [ ] **Step 6: Verify the script is still valid bash**

```bash
bash -n install.sh && echo "syntax ok"
```

Expected: `syntax ok`

- [ ] **Step 7: Commit**

```bash
git add install.sh
git commit -m "feat: rename devc to devx, upgrade all agents in cmd_upgrade"
```

---

## Task 9: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update title and intro**

Change:
```markdown
# Claude Code in a devcontainer

A sandboxed development environment for running Claude Code with `bypassPermissions` safely enabled. Built at [Trail of Bits](https://www.trailofbits.com/) for security audit workflows.
```
to:
```markdown
# Agentic Devcontainer

A sandboxed development environment for running AI coding agents with auto-approve safely enabled. Built at [Trail of Bits](https://www.trailofbits.com/) for security audit workflows.

Supports Claude Code, Codex, and Pi — all pre-installed in a single container.
```

- [ ] **Step 2: Update the Prerequisites terminal install block**

Change:
```bash
git clone https://github.com/trailofbits/claude-code-devcontainer ~/.claude-devcontainer
~/.claude-devcontainer/install.sh self-install
```
to:
```bash
git clone https://github.com/trailofbits/agentic-devcontainer ~/.agentic-devcontainer
~/.agentic-devcontainer/install.sh self-install
```

- [ ] **Step 3: Replace all `devc` command references with `devx`**

```bash
# Preview what will change
grep -n "\bdevc\b" README.md
```

Replace every occurrence of `devc` (as a command) with `devx` throughout the README. This includes all code blocks and inline references.

- [ ] **Step 4: Add Agents section**

After the "Why Use This?" section, add:

```markdown
## Agents

All three agents are pre-installed in every container. Configure them by setting the relevant environment variables on your host before starting the container.

| Agent | Command | Auth env vars |
|-------|---------|---------------|
| Claude Code | `claude` | `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` |
| Codex | `codex` | `OPENAI_API_KEY` or `CODEX_ACCESS_TOKEN` |
| Pi | `pi` | — (auto-approve by default) |

### Token-Based Auth

Set any combination of these on your host before running `devx`:

```bash
export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...   # Claude Code
export ANTHROPIC_API_KEY=sk-ant-...               # Claude Code (API key)
export OPENAI_API_KEY=sk-...                      # Codex
export CODEX_ACCESS_TOKEN=...                     # Codex (ChatGPT OAuth)
```

Tokens are forwarded into the container via `remoteEnv` in `devcontainer.json`. Values are never logged.
```

- [ ] **Step 5: Update Token-Based Auth section**

The existing "Token-Based Auth (Headless)" section is Claude-specific. Update it to reference the new Agents section and remove duplication. Replace:

```markdown
## Token-Based Auth (Headless)

For headless servers or to skip the interactive login wizard:

```bash
claude setup-token                          # run on host, one-time
export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
devc rebuild                                # rebuilds with token
```

The token is forwarded into the container...
```

with:

```markdown
## Token-Based Auth (Headless)

See [Agents](#agents) above for the full list of supported env vars per agent.

For Claude Code specifically, run the one-time setup on your host:

```bash
claude setup-token                          # run on host, one-time
export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
devx rebuild                                # rebuilds with token
```

The token is forwarded into the container. On each container creation, `post_install.py` runs a one-shot auth handshake so `claude` starts without the login wizard.
```

- [ ] **Step 6: Update Container Details table**

The current table lists only Claude config. Update the `Auto-configured` row:

Change:
```
| Auto-configured | [anthropics](https://github.com/anthropics/claude-code-plugins) + [trailofbits](https://github.com/trailofbits/claude-code-plugins) skills, git-delta |
```
to:
```
| Agents | Claude Code (with skills), Codex, Pi |
| Auto-configured | [anthropics](https://github.com/anthropics/claude-code-plugins) + [trailofbits](https://github.com/trailofbits/claude-code-plugins) skills, git-delta |
```

- [ ] **Step 7: Verify no remaining `devc` references**

```bash
grep -n "\bdevc\b" README.md
```

Expected: zero matches.

- [ ] **Step 8: Commit**

```bash
git add README.md
git commit -m "docs: rebrand to Agentic Devcontainer, document all agents, rename devc to devx"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run --no-project --with pytest pytest tests/ -v
```

Expected: all tests PASS, no failures.

- [ ] **Step 2: Verify no remaining Claude-only branding in key files**

```bash
grep -rn "Claude Code Devcontainer\|Claude Code Sandbox\|\bdevc\b" \
  Dockerfile devcontainer.json install.sh README.md
```

Expected: zero matches.

- [ ] **Step 3: Verify JSON and bash syntax**

```bash
python3 -c "import json; json.load(open('devcontainer.json')); print('devcontainer.json: valid')"
bash -n install.sh && echo "install.sh: syntax ok"
```

Expected: both lines print their success message.

- [ ] **Step 4: Commit if anything was missed**

If Step 2 or 3 found issues, fix them and commit:
```bash
git add -p
git commit -m "fix: clean up remaining Claude-specific references"
```
