"""Tests for phlux/adapters/gusto.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
from phlux.adapters.gusto import fetch

URL = "https://jobs.gusto.com/boards/acme-e7cbbd33-db1c-470e-93b3-020992d24e20"
HTML = """
<a href="/postings/acme-deployment-engineer-4c883caa-7a7e-445b-9241-c01fcf60bd3f?utm_source=board">
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
    assert [p.url for p in postings] == [
        "https://jobs.gusto.com/postings/acme-deployment-engineer-4c883caa-7a7e-445b-9241-c01fcf60bd3f",
        "https://jobs.gusto.com/postings/acme-mechatronic-intern-65e8e232-5331-44b9-bed1-181e1d9eddd6",
    ]
    assert get.call_args.args == (URL,)


def test_empty_board():
    with patch("phlux.adapters.gusto.get", return_value=response("<p>No open positions</p>")):
        assert fetch(URL) == []


PIN = ('<svg viewBox="0 0 24 24"><path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0z"/>'
       '<path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>')
SALARY = '<p class="text-gray-500 flex items-center"><svg><path d="M0.5 3.31601Z"/></svg> $25 per hour &middot; Intern</p>'


def test_locations_beside_the_map_pin():
    html = f"""
    <a href="/postings/acme-a-4c883caa-7a7e-445b-9241-c01fcf60bd3f"><div><h3>Deployment Engineer</h3>
      <p class="text-gray-500 flex">{PIN}
        Fremont, CA
        </br>
        Remote
        </br>
      </p>{SALARY}</div></a>
    <a href="/postings/acme-b-65e8e232-5331-44b9-bed1-181e1d9eddd6"><div><h3>Intern</h3>
      <p class="text-gray-500 flex">{PIN} San Jose, California </br></p>{SALARY}</div></a>
    <a href="/postings/acme-c-11111111-5331-44b9-bed1-181e1d9eddd6"><div><h3>No location</h3>{SALARY}</div></a>
    """
    with patch("phlux.adapters.gusto.get", return_value=response(html)):
        postings = fetch(URL)
    assert [p.location for p in postings] == ["Fremont, CA +1", "San Jose, CA", ""]
