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
