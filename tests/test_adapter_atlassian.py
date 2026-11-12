"""Tests for phlux/adapters/atlassian.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.atlassian import fetch, gallery, location

SF = "San Francisco - United States -   San Francisco, California 94104 United States"
SEATTLE = "Seattle - United States -   Seattle, Washington  United States"
SYDNEY = "Sydney - Australia -   Sydney,  2000 Australia"


def job(number, title, category, *locations):
    return {"sys": {"id": f"sys{number}"}, "fields": {
        "id": str(number), "title": title, "category": category, "locations": list(locations) or None,
        "applyUrl": f"https://careers-americas.icims.com/jobs/{number}/x/job?mode=apply", "type": None,
    }}


def page(*jobs):
    data = json.dumps(list(jobs))
    return MagicMock(text=(
        '<html><script>window.__x={"type":"careersGallery","parameters":{"data":{"type":"json","value":'
        f'{data}}},"filters":{{"type":"$block"}}}}</script></html>'
    ))


JOBS = [
    job(26266, "Software Engineer Intern, 2027 Summer U.S.", "Interns", SF, SEATTLE),
    job(26275, "Software Engineer Intern, 2027 Canada", "Interns", "Canada -     Canada"),
    job(27223, "Social Media Intern, 2027 Summer U.S.", "Marketing", SF),
    job(28369, "Principal Architect", "Sales", SYDNEY, "Remote - Remote"),
]


def test_registered():
    assert ADAPTERS["atlassian"] is fetch


def test_reads_whole_page_without_filters():
    with patch("phlux.adapters.atlassian.get", return_value=page(*JOBS)) as get:
        postings = fetch("https://www.atlassian.com/company/careers/all-jobs")
    assert [(p.id, p.title, p.location, p.url) for p in postings] == [
        ("atlassian:26266", "Software Engineer Intern, 2027 Summer U.S.", "San Francisco, CA +1",
         "https://www.atlassian.com/company/careers/details/26266"),
        ("atlassian:26275", "Software Engineer Intern, 2027 Canada", "Canada",
         "https://www.atlassian.com/company/careers/details/26275"),
        ("atlassian:27223", "Social Media Intern, 2027 Summer U.S.", "San Francisco, CA",
         "https://www.atlassian.com/company/careers/details/27223"),
        ("atlassian:28369", "Principal Architect", "Sydney, Australia +1",
         "https://www.atlassian.com/company/careers/details/28369"),
    ]
    get.assert_called_once_with("https://www.atlassian.com/company/careers/all-jobs")


@pytest.mark.parametrize("url, ids", [
    ("https://www.atlassian.com/company/careers/all-jobs?team=Interns&location=&search=", ["26266", "26275"]),
    ("https://www.atlassian.com/company/careers/all-jobs?team=interns&location=Canada", ["26275"]),
    ("https://www.atlassian.com/company/careers/all-jobs?location=United%20States&search=social", ["27223"]),
])
def test_filters_like_the_page(url, ids):
    with patch("phlux.adapters.atlassian.get", return_value=page(*JOBS)):
        assert [p.id.split(":")[1] for p in fetch(url)] == ids


def test_missing_gallery_raises():
    with pytest.raises(ValueError, match="careersGallery"):
        gallery("<html>No jobs here</html>")


@pytest.mark.parametrize("locations, expected", [
    ([SF], "San Francisco, CA"),
    ([SEATTLE], "Seattle, WA"),
    (["Mountain View - United States or Remote -   Mountain View, California 94041 United States"],
     "Mountain View, CA"),
    (["Washington DC - United States -   Washington DC, Washington, DC  United States"], "Washington, DC"),
    (["London - United Kingdom -   London,  EC1V United Kingdom"], "London, United Kingdom"),
    (["Singapore - Singapore -   Central Singapore  Singapore"], "Singapore"),
    (["Seoul - South Korea -     Korea, South"], "Seoul, South Korea"),
    (["Remote - UK - Remote"], "Remote"),
    (["Remote - Remote", SF], "Remote +1"),
    ([], ""),
])
def test_location(locations, expected):
    assert location({"locations": locations}) == expected
