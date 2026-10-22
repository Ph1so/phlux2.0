"""Tests for phlux/adapters/paycor.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
from phlux.adapters.paycor import fetch

URL = "https://recruitingbypaycor.com/career/CareerHome.action?clientId=abc&m=t"
HTML = """
<div class="gnewtonCareerGroupRowClass"><div class="gnewtonCareerGroupJobTitleClass">
  <a href="https://recruitingbypaycor.com/career/JobIntroduction.action?clientId=abc&amp;id=8a78839f&amp;m=t&amp;source=&amp;lang=en">
    Senior Strategic   Account Executive</a></div><div>Waltham, MA</div></div>
<div class="gnewtonCareerGroupRowClass"><div class="gnewtonCareerGroupJobTitleClass">
  <a href="JobIntroduction.action?clientId=abc&amp;id=8a7887a8&amp;m=t">Robotics Intern</a></div></div>
"""


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def test_registered():
    assert ADAPTERS["paycor"] is fetch


def test_reads_job_links_with_ids():
    with patch("phlux.adapters.paycor.get", return_value=response(HTML)) as get:
        postings = fetch(URL)
    assert [(p.id, p.title) for p in postings] == [
        ("paycor:8a78839f", "Senior Strategic Account Executive"),
        ("paycor:8a7887a8", "Robotics Intern"),
    ]
    get.assert_called_once_with(URL)


def test_empty_board():
    with patch("phlux.adapters.paycor.get", return_value=response("<table></table>")):
        assert fetch(URL) == []
