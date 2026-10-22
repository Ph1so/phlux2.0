"""Tests for phlux/adapters/jazzhr.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
from phlux.adapters.jazzhr import fetch

HTML = """
<a href="https://acme.applytojob.com/apply">Home</a>
<ul class="list-group">
  <li class="list-group-item"><h3><a href="https://acme.applytojob.com/apply/xWoufwUdo4/Join-Team">
    Join   Team Acme</a></h3><ul><li>Los Angeles, CA</li></ul></li>
  <li class="list-group-item"><h3><a href="/apply/KmTWfIjRFt/Mechanical-Engineer">Mechanical Engineer</a></h3>
    <a href="/apply/KmTWfIjRFt/Mechanical-Engineer">Apply</a></li>
</ul>
"""


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def test_registered():
    assert ADAPTERS["jazzhr"] is fetch


def test_reads_job_links_with_codes_as_ids():
    with patch("phlux.adapters.jazzhr.get", return_value=response(HTML)) as get:
        postings = fetch("https://acme.applytojob.com/apply")
    assert [(p.id, p.title) for p in postings] == [
        ("jazzhr:xWoufwUdo4", "Join Team Acme"),
        ("jazzhr:KmTWfIjRFt", "Mechanical Engineer"),
    ]
    get.assert_called_once_with("https://acme.applytojob.com/apply")


def test_empty_board():
    with patch("phlux.adapters.jazzhr.get", return_value=response("<p>No openings</p>")):
        assert fetch("https://acme.applytojob.com/") == []
