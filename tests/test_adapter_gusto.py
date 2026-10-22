"""Tests for phlux/adapters/gusto.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
from phlux.adapters.gusto import fetch

URL = "https://jobs.gusto.com/boards/acme-e7cbbd33-db1c-470e-93b3-020992d24e20"
HTML = """
<a href="/postings/acme-deployment-engineer-4c883caa-7a7e-445b-9241-c01fcf60bd3f">
  <div><h3>Deployment   Engineer</h3><p>San Jose, CA</p></div></a>
<a href="/postings/acme-mechatronic-intern-65e8e232-5331-44b9-bed1-181e1d9eddd6">
  <div><h3>Mechatronic Intern</h3></div></a>
<a href="/postings/acme-mechatronic-intern-65e8e232-5331-44b9-bed1-181e1d9eddd6">View</a>
"""


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def test_registered():
    assert ADAPTERS["gusto"] is fetch


def test_reads_postings_with_uuid_ids():
    with patch("phlux.adapters.gusto.get", return_value=response(HTML)) as get:
        postings = fetch(URL)
    assert [(p.id, p.title) for p in postings] == [
        ("gusto:4c883caa-7a7e-445b-9241-c01fcf60bd3f", "Deployment Engineer"),
        ("gusto:65e8e232-5331-44b9-bed1-181e1d9eddd6", "Mechatronic Intern"),
    ]
    assert get.call_args.args == (URL,)


def test_empty_board():
    with patch("phlux.adapters.gusto.get", return_value=response("<p>No open positions</p>")):
        assert fetch(URL) == []
