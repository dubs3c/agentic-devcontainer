import sys
from pathlib import Path


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
