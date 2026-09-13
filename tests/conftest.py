"""Shared pytest fixtures and configuration for the test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the project root importable so tests can `import custom_components...`.
sys.path.append(str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the local custom_components directory in every test."""
    yield
