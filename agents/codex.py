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
