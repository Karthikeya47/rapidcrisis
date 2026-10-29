import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Tests must never call the real model or write the real audit file
os.environ.pop("NEBIUS_API_KEY", None)
os.environ["AUDIT_LOG_PATH"] = os.devnull


@pytest.fixture(autouse=True)
def _fresh_state():
    from staff_finder import reset_availability
    from dispatcher import clear_inboxes
    from logger import clear_events
    reset_availability()
    clear_inboxes()
    clear_events()
    yield
