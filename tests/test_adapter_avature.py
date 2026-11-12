"""Tests for phlux/adapters/avature.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.avature import avature_place, fetch, job_id, job_url, parse_results

URL = "https://jobs.acme.com/en_US/careers/SearchJobs/?542=13100&542_format=486&listFilterMode=1"


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def article(job, title, location="", href=None):
    href = href or f"https://jobs.acme.com/en_US/careers/JobDetail/{title.replace(' ', '-')}/{job}"
    where = f'<span class="list-item-location">{location}</span>' if location else ""
    return (f'<article class="article article--result"><h3><a class="link" href="{href}">\n  {title}\n</a></h3>'
            f'<div class="article__header__text__subtitle">{where}<span class="list-item-id">Role ID {job}</span></div>'
            f'<a class="button" href="{href}">More Information</a></article>')


def page(articles, legend="", next_href=None):
    nxt = f'<a class="list-controls__pagination__item paginationNextLink" href="{next_href}">Next</a>' if next_href else ""
    return (f'<div class="list-controls__text"><span class="list-controls__text__legend">{legend}</span></div>'
            f'{"".join(articles)}<div class="list-controls__pagination">{nxt}</div>')


def test_registered():
    assert ADAPTERS["avature"] is fetch


@pytest.mark.parametrize("href, expected", [
    ("https://jobs.acme.com/en_US/careers/JobDetail/Software-Engineer-Intern/216250", "216250"),
    ("https://jobs.acme.com/en_US/careers/JobDetail?jobId=22984&source=External%2BCareer%2BSite", "22984"),
    ("/careers/JobDetail/New-York-AI-Intern/14096/", "14096"),
])
def test_job_id(href, expected):
    assert job_id(href) == expected


def test_job_url_drops_tracking_but_keeps_job_id():
    assert (job_url("/en_US/careers/JobDetail?jobId=22984&source=External%2BCareer%2BSite", URL, "22984")
            == "https://jobs.acme.com/en_US/careers/JobDetail?jobId=22984")
    assert (job_url("/en_US/careers/JobDetail/VFX-Intern/216273?src=x", URL, "216273")
            == "https://jobs.acme.com/en_US/careers/JobDetail/VFX-Intern/216273")


@pytest.mark.parametrize("raw, expected", [
    ("Austin, United States of America", "Austin"),
    ("Los Angeles - Del Rey, United States of America", "Los Angeles - Del Rey"),
    ("Rosslyn, Virginia, United States", "Rosslyn, VA"),
    ("USA-Arizona", "Arizona"),
    ("United States - NY New York", "New York, NY"),
    ("Taiwan-Hsinchu", "Hsinchu, Taiwan"),
    ("Taiwan", "Taiwan"),
    ("Bucharest, Romania", "Bucharest, Romania"),
    ("Multiple Locations", "Multiple Locations"),
    ("", ""),
])
def test_avature_place(raw, expected):
    assert avature_place(raw) == expected


def test_parse_results_titles_ids_locations_and_total():
    html = page([article(216186, "Business Intern", "Austin, United States of America"),
                 article(22984, "AZ Internship", "USA-Arizona",
                         href="https://jobs.acme.com/en_US/careers/JobDetail?jobId=22984&source=x")],
                legend="1-10 of 22 results", next_href=URL + "&jobOffset=10")
    postings, nxt, total = parse_results(html, URL)
    assert [(p.id, p.title, p.location) for p in postings] == [
        ("avature:216186", "Business Intern", "Austin"),
        ("avature:22984", "AZ Internship", "Arizona"),
    ]
    assert postings[1].url == "https://jobs.acme.com/en_US/careers/JobDetail?jobId=22984"
    assert nxt == URL + "&jobOffset=10" and total == 22


def test_location_selector_argument():
    html = ('<article class="article--result" data-total="1"><h3><a class="link" '
            'href="https://jobs.acme.com/careers/JobDetail/X/7">Quant Intern</a></h3>'
            '<div class="article__header__content__text"><span>United States - NY New York</span>'
            '<div class="sub"><span>Quantitative Research</span></div></div></article>')
    postings, nxt, total = parse_results(html, URL, ".article__header__content__text > span")
    assert [(p.title, p.location) for p in postings] == [("Quant Intern", "New York, NY")]
    assert nxt is None and total == 1
    # Without the selector the template names no location.
    assert parse_results(html, URL)[0][0].location == ""


def test_several_location_elements_are_counted():
    html = article(1, "Intern", "Orlando, United States of America").replace(
        '<span class="list-item-id">', '<span class="list-item-location">Vancouver, Canada</span><span class="list-item-id">')
    postings, _, _ = parse_results(html, URL)
    assert postings[0].location == "Orlando +1"


def test_follows_next_links_until_none():
    pages = [page([article(1, "A Intern"), article(2, "B Intern")], "1-2 of 3 results", URL + "&jobOffset=2"),
             page([article(3, "C Intern")], "3-3 of 3 results")]
    with patch("phlux.adapters.avature.get", side_effect=[response(p) for p in pages]) as get, \
            patch("phlux.adapters.avature.time.sleep"):
        postings = fetch(URL)
    assert [p.id for p in postings] == ["avature:1", "avature:2", "avature:3"]
    assert [c.args[0] for c in get.call_args_list] == [URL, URL + "&jobOffset=2"]


def test_stops_when_a_page_repeats():
    same = page([article(1, "A Intern")], "1 results", URL + "&jobOffset=1")
    with patch("phlux.adapters.avature.get", side_effect=[response(same), response(same)]) as get, \
            patch("phlux.adapters.avature.time.sleep"):
        assert [p.id for p in fetch(URL)] == ["avature:1"]
    assert get.call_count == 2


def test_no_results():
    with patch("phlux.adapters.avature.get", return_value=response(page([], "0 results"))):
        assert fetch(URL) == []
