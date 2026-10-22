"""Tests for phlux/boards.py (board APIs are mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux import boards
from phlux.boards import (
    ashby_postings,
    board_postings,
    greenhouse_postings,
    greenhouse_slug,
    lever_postings,
)


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.raise_for_status.return_value = None
    return mock


def fake_get(routes):
    """Patch requests.get to answer each URL prefix in *routes* with its payload."""
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        for prefix, payload in routes.items():
            if url.startswith(prefix):
                return response(payload)
        raise AssertionError(f"unexpected GET {url}")

    return patch("phlux.boards.requests.get", side_effect=get), calls


GH_JOBS = {"jobs": [
    {"id": 1, "title": "Software Engineer Intern"},
    {"id": 2, "title": "Recruiter"},
    {"id": 3, "title": "Winter Co-op, Robotics"},
]}
GH = "https://boards-api.greenhouse.io/v1/boards/acme/"


class TestGreenhouse:
    @pytest.mark.parametrize("url", [
        "https://job-boards.greenhouse.io/embed/job_board?for=acme&keyword=intern",
        "https://job-boards.greenhouse.io/acme/",
        "https://job-boards.eu.greenhouse.io/acme",
        "https://job-boards.greenhouse.io/acme?departments%5B%5D=9",
    ])
    def test_slug(self, url):
        assert greenhouse_slug(url) == "acme"

    def test_whole_board_with_ids(self):
        mock, _ = fake_get({GH + "jobs": GH_JOBS})
        with mock:
            postings = greenhouse_postings("https://job-boards.greenhouse.io/acme")
        assert [(p.id, p.title) for p in postings] == [
            ("greenhouse:1", "Software Engineer Intern"),
            ("greenhouse:2", "Recruiter"),
            ("greenhouse:3", "Winter Co-op, Robotics"),
        ]

    def test_keyword_matches_titles_case_insensitively(self):
        mock, _ = fake_get({GH + "jobs": GH_JOBS})
        with mock:
            postings = greenhouse_postings("https://job-boards.greenhouse.io/acme?keyword=INTERN")
        assert [p.title for p in postings] == ["Software Engineer Intern"]

    def test_department_filter_includes_children(self):
        departments = {"departments": [
            {"id": 10, "name": "Engineering", "child_ids": [11], "jobs": [{"id": 1}]},
            {"id": 11, "name": "Robotics", "child_ids": [], "jobs": [{"id": 3}]},
            {"id": 12, "name": "People", "child_ids": [], "jobs": [{"id": 2}]},
        ]}
        mock, _ = fake_get({GH + "jobs": GH_JOBS, GH + "departments": departments})
        with mock:
            postings = greenhouse_postings("https://job-boards.greenhouse.io/acme?departments%5B%5D=10")
        assert [p.id for p in postings] == ["greenhouse:1", "greenhouse:3"]

    def test_office_filter_reads_jobs_under_its_departments(self):
        offices = {"offices": [
            {"id": 20, "name": "Pittsburgh", "child_ids": [], "departments": [{"id": 10, "jobs": [{"id": 2}]}]},
            {"id": 21, "name": "Remote", "child_ids": [], "departments": [{"id": 10, "jobs": [{"id": 1}]}]},
        ]}
        mock, _ = fake_get({GH + "jobs": GH_JOBS, GH + "offices": offices})
        with mock:
            postings = greenhouse_postings("https://job-boards.greenhouse.io/acme?offices%5B%5D=20")
        assert [p.id for p in postings] == ["greenhouse:2"]


class TestLever:
    JOBS = [
        {"id": "a", "text": "Robotics Intern", "categories": {"commitment": "Internship"}},
        {"id": "b", "text": "Controls Engineer", "categories": {"commitment": "Full-time"}},
    ]

    def test_reads_board_with_ids(self):
        mock, calls = fake_get({"https://api.lever.co/v0/postings/acme": self.JOBS})
        with mock:
            postings = lever_postings("https://jobs.lever.co/acme")
        assert [(p.id, p.title) for p in postings] == [("lever:a", "Robotics Intern"), ("lever:b", "Controls Engineer")]
        assert calls[0][1]["params"] == {"mode": "json"}

    def test_commitment_filter(self):
        mock, _ = fake_get({"https://api.lever.co/v0/postings/acme": self.JOBS})
        with mock:
            postings = lever_postings("https://jobs.lever.co/acme?commitment=internship")
        assert [p.id for p in postings] == ["lever:a"]

    def test_eu_board_uses_eu_api(self):
        mock, calls = fake_get({"https://api.eu.lever.co/v0/postings/acme": self.JOBS})
        with mock:
            lever_postings("https://jobs.eu.lever.co/acme")
        assert calls[0][0].startswith("https://api.eu.lever.co/")


class TestAshby:
    JOBS = {"jobs": [
        {"id": "x", "title": "Perception Intern", "isListed": True},
        {"id": "y", "title": "Hidden Role", "isListed": False},
        {"id": "z", "title": "Planner", "isListed": True},
    ]}

    def test_skips_unlisted_postings(self):
        # The slug is URL-decoded; requests re-encodes the space.
        mock, _ = fake_get({"https://api.ashbyhq.com/posting-api/job-board/Acme Inc": self.JOBS})
        with mock:
            postings = ashby_postings("https://jobs.ashbyhq.com/Acme%20Inc")
        assert [p.id for p in postings] == ["ashby:x", "ashby:z"]

    def test_location_filter_matches_primary_or_secondary(self):
        graph = response({"data": {"jobBoard": {"jobPostings": [
            {"id": "x", "locationId": "loc1", "secondaryLocations": []},
            {"id": "z", "locationId": "loc2", "secondaryLocations": [{"locationId": "loc1"}]},
        ]}}})
        mock, _ = fake_get({"https://api.ashbyhq.com/posting-api/job-board/acme": self.JOBS})
        with mock, patch("phlux.boards.requests.post", return_value=graph) as post:
            postings = ashby_postings("https://jobs.ashbyhq.com/acme?locationId=loc1")
        assert [p.id for p in postings] == ["ashby:x", "ashby:z"]
        assert post.call_args.kwargs["json"]["variables"] == {"organizationHostedJobsPageName": "acme"}


class TestBoardPostings:
    def test_several_urls_are_unioned_without_duplicates(self):
        mock, _ = fake_get({GH + "jobs": GH_JOBS})
        urls = ("https://job-boards.greenhouse.io/embed/job_board?for=acme&keyword=intern"
                "->https://job-boards.greenhouse.io/embed/job_board?for=acme&keyword=co-op"
                "->https://job-boards.greenhouse.io/embed/job_board?for=acme&keyword=software")
        with mock:
            postings = board_postings("greenhouse", urls)
        assert [p.id for p in postings] == ["greenhouse:1", "greenhouse:3"]

    def test_http_errors_propagate(self):
        error = MagicMock()
        error.raise_for_status.side_effect = boards.requests.HTTPError("404")
        with patch("phlux.boards.requests.get", return_value=error):
            with pytest.raises(boards.requests.HTTPError):
                board_postings("greenhouse", "https://job-boards.greenhouse.io/gone")


class TestKeywordIn:
    @pytest.mark.parametrize("title, keyword, expected", [
        ("Software Engineer Intern", "intern", True),
        ("Robotics Internship", "intern", True),
        ("Senior Software Engineer, Internal Tooling", "intern", False),
        ("International Expansion Lead", "intern", False),
        ("Internet Services Engineer", "INTERN", False),
        ("Internal Tools Intern", "intern", True),
        ("Spring 2027 Engineering Internship/Co-op", "internship", True),
        ("Winter Co-op", "co-op", True),
        ("Early Career Engineer", "early career", True),
        ("Painter", "intern", False),
    ])
    def test_keyword_in(self, title, keyword, expected):
        assert boards.keyword_in(title, keyword) is expected

    def test_greenhouse_keyword_skips_internal(self):
        jobs = {"jobs": [{"id": 1, "title": "Internal Audit Manager"}, {"id": 2, "title": "Audit Intern"}]}
        mock, _ = fake_get({GH + "jobs": jobs})
        with mock:
            postings = greenhouse_postings("https://job-boards.greenhouse.io/acme?keyword=intern")
        assert [p.id for p in postings] == ["greenhouse:2"]
