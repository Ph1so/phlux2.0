"""Tests for phlux/adapters/html.py (HTTP mocked)."""
import logging
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.html import fetch, postings

URL = "https://www.example.com/careers/internships"


def response(html, url=URL):
    mock = MagicMock()
    mock.text = html
    mock.url = url
    return mock


def test_registered():
    assert ADAPTERS["html"] is fetch


def test_title_link_is_the_id():
    html = """
    <li class="publication-source"><h2 id="OR0330"><a href="#OR0330">OR0330: Internship -
        Power   Systems</a></h2></li>
    <li class="publication-source"><h2><a href="/jobs/2"><span>Robotics Intern</span></a></h2></li>
    """
    found = postings(html, URL, ".publication-source h2 a")
    assert [(p.id, p.title) for p in found] == [
        ("html:https://www.example.com/careers/internships#OR0330", "OR0330: Internship - Power Systems"),
        ("html:https://www.example.com/jobs/2", "Robotics Intern"),
    ]
    # The link that keys a posting is its page too.
    assert [p.url for p in found] == [
        "https://www.example.com/careers/internships#OR0330",
        "https://www.example.com/jobs/2",
    ]


def test_title_inside_a_link():
    html = '<a href="https://jobs.example.com/9"><h3 class="t">Engineer</h3></a>'
    assert postings(html, URL, ".t")[0].id == "html:https://jobs.example.com/9"


def test_container_link_beside_the_title():
    html = """
    <div class="item"><div class="title"><h3>Research Intern: Robust Planning</h3></div>
      <a class="b-button" href="/-/research-intern-robust-planning">View More</a></div>
    <div class="item"><div class="title"><h3>No link</h3></div></div>
    <div class="item"><p>No title</p><a href="/x">x</a></div>
    """
    found = postings(html, URL, ".item >> .title")
    assert [(p.id, p.title) for p in found] == [
        ("html:https://www.example.com/-/research-intern-robust-planning", "Research Intern: Robust Planning"),
        ("html:title:No link", "No link"),
    ]


def test_no_link_falls_back_to_title():
    html = '<h3 class="accordion-item__title"> Inventory  Specialist </h3><h3 class="accordion-item__title"></h3>'
    assert [(p.id, p.title, p.url) for p in postings(html, URL, ".accordion-item__title")] == [
        ("html:title:Inventory Specialist", "Inventory Specialist", "")]


def test_a_mailto_link_is_no_page():
    html = '<a class="j" href="mailto:jobs@example.com">Write to us: Intern</a>'
    found = postings(html, URL, ".j")
    assert [(p.id, p.url) for p in found] == [("html:mailto:jobs@example.com", "")]


def test_repeated_postings_kept_once():
    html = '<a class="j" href="/1">A</a><a class="j" href="/1">A</a>'
    assert len(postings(html, URL, ".j")) == 1


def test_fetch_uses_selector_with_colons():
    html = '<ul><li><a class="job" href="/1">First</a></li><li><a class="job" href="/2">Second</a></li></ul>'
    with patch("phlux.adapters.html.get", return_value=response(html)) as get:
        found = fetch(URL, arg="li:first-child a.job")
    assert [p.title for p in found] == ["First"]
    assert get.call_args.args == (URL,)


def test_fetch_resolves_against_final_url():
    with patch("phlux.adapters.html.get", return_value=response('<a class="j" href="a">A</a>', url="https://new.example.com/c/")):
        assert fetch(URL, arg=".j")[0].id == "html:https://new.example.com/c/a"


def test_fetch_needs_a_selector():
    with pytest.raises(ValueError):
        fetch(URL)


def test_webflow_cap_is_flagged(caplog):
    html = '<html data-wf-site="x">' + "".join(f'<a class="j" href="/careers/jd{i}">Job {i}</a>' for i in range(100))
    with patch("phlux.adapters.html.get", return_value=response(html)), caplog.at_level(logging.WARNING):
        assert len(fetch(URL, arg=".j")) == 100
    assert "Webflow" in caplog.text


def test_location_from_the_container():
    html = """
    <div class="b-job-item"><div class="b-job-item__title"><h3>Research Intern: Polymer Composite</h3></div>
      <div class="b-job-item__location">
        Columbus, OH
      </div><a href="/-/polymer">View More</a></div>
    <div class="b-job-item"><div class="b-job-item__title"><h3>Research Intern: Planning</h3></div>
      <span class="job-location-icon"></span><p class="Location">Location: San Jose, California</p>
      <a href="/-/planning">View More</a></div>
    <div class="b-job-item"><div class="b-job-item__title"><h3>Research Intern: Vision</h3></div>
      <a href="/-/vision">View More</a></div>
    """
    found = postings(html, URL, ".b-job-item >> .b-job-item__title")
    assert [p.location for p in found] == ["Columbus, OH", "San Jose, CA", ""]


def test_no_location_without_a_container():
    html = '<li><h2><a href="/jobs/2">Robotics Intern</a></h2><span class="location">Boston, MA</span></li>'
    assert postings(html, URL, "h2 a")[0].location == ""
