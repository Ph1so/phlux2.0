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
    # Relative links are made absolute; display and source parameters are dropped.
    assert [p.url for p in postings] == [
        "https://recruitingbypaycor.com/career/JobIntroduction.action?clientId=abc&id=8a78839f",
        "https://recruitingbypaycor.com/career/JobIntroduction.action?clientId=abc&id=8a7887a8",
    ]


def test_a_link_without_an_id_is_kept_whole():
    html = '<a href="JobIntroduction.action?clientId=abc&amp;job=9">Intern</a>'
    with patch("phlux.adapters.paycor.get", return_value=response(html)):
        postings = fetch(URL)
    link = "https://recruitingbypaycor.com/career/JobIntroduction.action?clientId=abc&job=9"
    assert [(p.id, p.url) for p in postings] == [(f"paycor:{link}", link)]


def test_empty_board():
    with patch("phlux.adapters.paycor.get", return_value=response("<table></table>")):
        assert fetch(URL) == []


def test_location_from_the_rows_description():
    html = """
    <div class="gnewtonCareerGroupRowClass"><div class="gnewtonCareerGroupJobTitleClass">
      <a href="JobIntroduction.action?clientId=abc&amp;id=1">A</a></div>
      <div class="gnewtonCareerGroupJobDescriptionClass">
        Detroit, MI
      </div></div>
    <div class="gnewtonCareerGroupRowClass"><div class="gnewtonCareerGroupJobTitleClass">
      <a href="JobIntroduction.action?clientId=abc&amp;id=2">B</a></div>
      <div class="gnewtonCareerGroupJobDescriptionClass">Remote</div></div>
    <div class="gnewtonCareerGroupRowClass"><div class="gnewtonCareerGroupJobTitleClass">
      <a href="JobIntroduction.action?clientId=abc&amp;id=3">C</a></div>
      <div class="gnewtonCareerGroupJobDescriptionClass">Waltham, Massachusetts</div></div>
    <a href="JobIntroduction.action?clientId=abc&amp;id=4">D</a>
    """
    with patch("phlux.adapters.paycor.get", return_value=response(html)):
        postings = fetch(URL)
    assert [p.location for p in postings] == ["Detroit, MI", "Remote", "Waltham, MA", ""]
