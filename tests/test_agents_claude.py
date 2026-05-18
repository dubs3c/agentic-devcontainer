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
