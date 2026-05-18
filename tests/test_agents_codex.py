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
