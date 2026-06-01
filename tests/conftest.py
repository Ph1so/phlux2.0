"""Shared fixtures and environment setup for the test suite."""
import os

import pytest

# Set required env vars before any module is imported during collection.
os.environ.setdefault("GMAIL_APP_PASSWORD", "test_placeholder")
os.environ.setdefault("ICONS_ID", "test_placeholder")
os.environ.setdefault("GH_TOKEN", "test_placeholder")


@pytest.fixture
def intern_message():
    return {
        "companies": {
            "Acme": {
                "jobs": [{"title": "Software Engineer Intern", "date": "5/1"}],
                "link": "https://acme.com/careers",
            }
        }
    }


@pytest.fixture
def fulltime_message():
    return {
        "companies": {
            "Acme": {
                "jobs": [{"title": "Software Engineer", "date": "5/1"}],
                "link": "https://acme.com/careers",
            }
        }
    }


@pytest.fixture
def mixed_message():
    return {
        "companies": {
            "Acme": {
                "jobs": [
                    {"title": "Software Engineer Intern", "date": "5/1"},
                    {"title": "Software Engineer", "date": "5/1"},
                ],
                "link": "https://acme.com/careers",
            }
        }
    }
