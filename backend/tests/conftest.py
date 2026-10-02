import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import brain  # noqa: E402
import essential  # noqa: E402


@pytest.fixture(autouse=True)
def reset_module_state():
    brain._llm_down_until = 0.0
    essential._memory.clear()
    yield
    brain._llm_down_until = 0.0
    essential._memory.clear()
