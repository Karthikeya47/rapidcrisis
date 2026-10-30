import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Tests must never call the real model or write the real audit file.
# Set (not pop) the key: load_dotenv() in main.py would otherwise reload it from a local .env.
os.environ["NEBIUS_API_KEY"] = ""
os.environ["AUDIT_LOG_PATH"] = os.devnull


@pytest.fixture(autouse=True)
def _fresh_state():
    from staff_finder import reset_availability
    from dispatcher import clear_inboxes
    from logger import clear_events
    from review import clear_reviews
    from main import dispatch_limiter, review_limiter
    dispatch_limiter.reset()
    review_limiter.reset()
    reset_availability()
    clear_inboxes()
    clear_events()
    clear_reviews()
    yield
