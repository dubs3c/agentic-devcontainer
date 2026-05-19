# Agentic Devcontainer

A sandboxed development environment for running AI coding agents with auto-approve safely enabled. Built at [Trail of Bits](https://www.trailofbits.com/) for security audit workflows.

Supports Claude Code, Codex, and Pi — all pre-installed in a single container.

## Why Use This?

Running Claude with `bypassPermissions` on your host machine is risky—it can execute any command without confirmation. This devcontainer provides **filesystem isolation** so you get the productivity benefits of unrestricted Claude without risking your host system.

**Designed for:**

- **Security audits**: Review client code without risking your host
- **Untrusted repositories**: Explore unknown codebases safely
- **Experimental work**: Let Claude modify code freely in isolation
- **Multi-repo engagements**: Work on multiple related repositories

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

## Prerequisites

- **Docker runtime** (one of):
  - [Docker Desktop](https://docker.com/products/docker-desktop) - ensure it's running
  - [OrbStack](https://orbstack.dev/)
  - [Colima](https://github.com/abiosoft/colima): `brew install colima docker && colima start`

- **For terminal workflows** (one-time install):

  ```bash
  npm install -g @devcontainers/cli
  git clone https://github.com/trailofbits/agentic-devcontainer ~/.agentic-devcontainer
  ~/.agentic-devcontainer/install.sh self-install
  ```

<details>
<summary><strong>Optimizing Colima for Apple Silicon</strong></summary>

Colima's defaults (QEMU + sshfs) are conservative. For better performance:

```bash
# Stop and delete current VM (removes containers/images)
colima stop && colima delete

# Start with optimized settings
colima start \
  --cpu 4 \
  --memory 8 \
  --disk 100 \
  --vm-type vz \
  --vz-rosetta \
  --mount-type virtiofs
```

Adjust `--cpu` and `--memory` based on your Mac (e.g., 6/16 for Pro, 8/32 for Max).

| Option | Benefit |
|--------|---------|
| `--vm-type vz` | Apple Virtualization.framework (faster than QEMU) |
| `--mount-type virtiofs` | 5-10x faster file I/O than sshfs |
| `--vz-rosetta` | Run x86 containers via Rosetta |

Verify with `colima status` - should show "macOS Virtualization.Framework" and "virtiofs".

</details>

## Quick Start

Choose the pattern that fits your workflow:

### Pattern A: Per-Project Container (Isolated)

Each project gets its own container with independent volumes. Best for one-off reviews, untrusted repos, or when you need isolation between projects.

**Terminal:**

```bash
git clone <untrusted-repo>
cd untrusted-repo
devx .          # Installs template + starts container
devx shell      # Opens shell in container
```

**VS Code / Cursor:**

1. Install the Dev Containers extension:
   - VS Code: `ms-vscode-remote.remote-containers`
   - Cursor: `anysphere.remote-containers`

2. Set up the devcontainer (choose one):

   ```bash
   # Option A: Use devx (recommended)
   devx .

   # Option B: Clone manually
   git clone https://github.com/trailofbits/agentic-devcontainer .devcontainer/
   ```

3. Open **your project folder** in VS Code, then:
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "Reopen in Container" and select **Dev Containers: Reopen in Container**

### Pattern B: Shared Workspace Container (Grouped)

A parent directory contains the devcontainer config, and you clone multiple repos inside. Shared volumes across all repos. Best for client engagements, related repositories, or ongoing work.

```bash
# Create workspace for a client engagement
mkdir -p ~/sandbox/client-name
cd ~/sandbox/client-name
devx .          # Install template + start container
devx shell      # Opens shell in container

# Inside container:
git clone <client-repo-1>
git clone <client-repo-2>
cd client-repo-1
claude          # Ready to work
```

## Token-Based Auth (Headless)

See [Agents](#agents) above for the full list of supported env vars per agent.

For Claude Code specifically, run the one-time setup on your host:

```bash
claude setup-token                          # run on host, one-time
export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
devx rebuild                                # rebuilds with token
```

The token is forwarded into the container. On each container creation, `post_install.py` runs a one-shot auth handshake so `claude` starts without the login wizard.

This works around Claude Code's interactive onboarding wizard always showing in containers, even with valid credentials ([#8938](https://github.com/anthropics/claude-code/issues/8938)).

If you don't set a token, the interactive login flow works as before.

## CLI Helper Commands

```
devx .              Install template + start container in current directory
devx up             Start the devcontainer
devx rebuild        Rebuild container (preserves persistent volumes)
devx destroy [-f]   Remove container, volumes, and image for current project
devx down           Stop the container
devx shell          Open zsh shell in container
devx exec CMD       Execute command inside the container
devx upgrade        Upgrade all agents in the container
devx mount SRC DST  Add a bind mount (host → container)
devx sync [NAME]    Sync Claude Code sessions from devcontainers to host
devx template DIR   Copy devcontainer files to directory
devx self-install   Install devx to ~/.local/bin
```

> **Note:** Use `devx destroy` to clean up a project's Docker resources. Removing containers manually (e.g., `docker rm`) will leave orphaned volumes and images behind that `devx destroy` won't be able to find.

## Session Sync for `/insights`

Claude Code's `/insights` command analyzes your session history, but it only reads from `~/.claude/projects/` on the host. Sessions inside devcontainer volumes are invisible to it.

`devx sync` copies session logs from all devcontainers (running and stopped) to the host so `/insights` can include them:

```bash
devx sync              # Sync all devcontainers
devx sync crypto       # Filter by project name (substring match)
```

Devcontainers are auto-discovered via Docker labels — no need to know container names or IDs. The sync is incremental, so it's safe to run repeatedly.

## File Sharing

### VS Code / Cursor

Drag files from your host into the VS Code Explorer panel — they are copied into `/workspace/` automatically. No configuration needed.

### Terminal: `devx mount`

To make a host directory available inside the container:

```bash
devx mount ~/drop /drop           # Read-write
devx mount ~/secrets /secrets --readonly
```

This adds a bind mount to `devcontainer.json` and recreates the container. Existing mounts are preserved across `devx template` updates.

**Tip:** A shared "drop folder" is useful for passing files in without mounting your entire home directory.

> **Security note:** Avoid mounting large host directories (e.g., `$HOME`). Every mounted path is writable from inside the container unless `--readonly` is specified, which undermines the filesystem isolation this project provides.

## Network Isolation

By default, containers have full outbound network access. For stricter security, use iptables to restrict network access.

### When to Enable Network Isolation

- Reviewing code that may contain malicious dependencies
- Auditing software with telemetry or phone-home behavior
- Maximum isolation for highly sensitive reviews

### Example: Claude + GitHub + Package Registries

```bash
sudo iptables -A OUTPUT -d api.anthropic.com -j ACCEPT
sudo iptables -A OUTPUT -d github.com -j ACCEPT
sudo iptables -A OUTPUT -d raw.githubusercontent.com -j ACCEPT
sudo iptables -A OUTPUT -d registry.npmjs.org -j ACCEPT
sudo iptables -A OUTPUT -d pypi.org -j ACCEPT
sudo iptables -A OUTPUT -d files.pythonhosted.org -j ACCEPT
sudo iptables -A OUTPUT -o lo -j ACCEPT
sudo iptables -A OUTPUT -j DROP
```

### Trade-offs

- Blocks package managers unless you allowlist registries
- May break tools that require network access
- DNS resolution still works (consider blocking if paranoid)

## Threat Model

The primary threat this project addresses is **Claude Code running arbitrary commands on your host machine**. When `bypassPermissions` is enabled, Claude executes shell commands, installs packages, and modifies files without confirmation. On a host machine this means it can modify your shell config, `rm -rf` outside the project directory, or abuse locally stored credentials. The devcontainer confines all of that to a disposable container where the blast radius is limited to `/workspace`.

The container includes common development tooling so you can do all development work inside it - not just run Claude. The intended workflow is: clone a repository, start the devcontainer, and work entirely within it. If your project needs additional runtimes or tools beyond what's included, either add them to the Dockerfile for repeated use or install them ad-hoc with `devx exec`.

For the specific boundaries of what is and isn't isolated, see [Security Model](#security-model) below. One nuance worth calling out: the devcontainer runtime automatically forwards your host's SSH agent socket (`SSH_AUTH_SOCK`) into the container. This lets code inside the container authenticate as you over SSH (e.g., `git push`), but the actual private key material stays on the host and is never exposed to the container.

## Security Model

This devcontainer provides **filesystem isolation** but not complete sandboxing.

**Sandboxed:** Filesystem (host files inaccessible), processes (isolated from host), package installations (stay in container)

**Not sandboxed:** Network (full outbound by default—see [Network Isolation](#network-isolation)), git identity (`~/.gitconfig` mounted read-only), SSH agent (socket forwarded, keys stay on host), Docker socket (not mounted by default)

The container auto-configures `bypassPermissions` mode—Claude runs commands without confirmation. This would be risky on a host machine, but the container itself is the sandbox.

## Container Details

| Component | Details |
|-----------|---------|
| Base | Ubuntu 24.04, Node.js 22, Python 3.13 + uv, zsh |
| User | `vscode` (passwordless sudo), working dir `/workspace` |
| Tools | `rg`, `fd`, `tmux`, `fzf`, `delta`, `iptables`, `ipset` |
| Volumes (survive rebuilds) | Command history (`/commandhistory`), Claude config (`~/.claude`), GitHub CLI auth (`~/.config/gh`) |
| Host mounts | `~/.gitconfig` (read-only), `.devcontainer/` (read-only) |
| Agents | Claude Code (with skills), Codex, Pi |
| Auto-configured | [anthropics](https://github.com/anthropics/claude-code-plugins) + [trailofbits](https://github.com/trailofbits/claude-code-plugins) skills, git-delta |

Volumes are stored outside the container, so your shell history, Claude settings, and `gh` login persist even after `devx rebuild`. Host `~/.gitconfig` is mounted read-only for git identity.

## Troubleshooting

### "devcontainer CLI not found"

```bash
npm install -g @devcontainers/cli
```

### Container won't start

1. Check Docker is running
2. Try rebuilding: `devx rebuild`
3. Check logs: `docker logs $(docker ps -lq)`

### GitHub CLI auth not persisting

The gh volume may need ownership fix:

```bash
sudo chown -R $(id -u):$(id -g) ~/.config/gh
```

### Python/uv not working

Python is managed via uv:

```bash
uv run script.py              # Run a script
uv add package                # Add project dependency
uv run --with requests py.py  # Ad-hoc dependency
```

## Development

Build the image manually:

```bash
devcontainer build --workspace-folder .
```

Test the container:

```bash
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . zsh
```
