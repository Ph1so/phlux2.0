"""Tests for phlux/adapters/amazon.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.amazon import fetch, search_json_params, team_search_body

SEARCH = ("https://www.amazon.jobs/en/search?offset=0&result_limit=10&sort=recent"
          "&country%5B%5D=USA&base_query=intern&loc_query=")
TEAM = "https://www.amazon.jobs/content/en/teams/ftr/amazon-robotics?country%5B%5D=US&employment-type%5B%5D=Intern"


def response(payload=None, text="", url=""):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.text = text
    mock.url = url
    return mock


def job(icims, title):
    return {"id": f"uuid-{icims}", "id_icims": str(icims), "title": title}


def team_page(search_filters, key="KEY123"):
    data = {
        "props": {"pageProps": {"content": {"searchFilters": search_filters}}},
        "runtimeConfig": {"searchKey": key, "searchEndpoint": "/api/jobs/search"},
    }
    return f'<html><script id="jobs-cms-next-data" type="application/json">{json.dumps(data)}</script></html>'


def hit(icims, title):
    return {"fields": {"icimsJobId": [str(icims)], "title": [title]}}


def test_registered():
    assert ADAPTERS["amazon"] is fetch


class TestSearchPage:
    def test_params_renamed_like_the_page(self):
        params = search_json_params(
            "https://www.amazon.jobs/en/search?offset=10&result_limit=10&country%5B%5D=USA"
            "&job_type%5B%5D=Internship&state%5B%5D=Washington&base_query=intern&category%5B%5D=software-development"
        )
        assert params == [
            ("normalized_country_code[]", "USA"),
            ("is_intern[]", "1"),
            ("normalized_state_name[]", "Washington"),
            ("base_query", "intern"),
            ("category[]", "software-development"),
        ]

    def test_unknown_job_type_is_refused(self):
        with pytest.raises(ValueError):
            search_json_params("https://www.amazon.jobs/en/search?job_type%5B%5D=Contractor")

    def test_reads_every_page(self):
        pages = [
            {"error": None, "hits": 150, "jobs": [job(i, f"Intern  {i}") for i in range(100)]},
            {"error": None, "hits": 150, "jobs": [job(i, f"Intern {i}") for i in range(100, 150)]},
        ]
        with patch("phlux.adapters.amazon.get", side_effect=[response(p) for p in pages]) as get:
            postings = fetch(SEARCH)
        assert len(postings) == 150
        assert postings[0].id == "amazon:0" and postings[0].title == "Intern 0"
        assert get.call_args_list[0].args == ("https://www.amazon.jobs/en/search.json",)
        first = get.call_args_list[0].kwargs["params"]
        assert ("normalized_country_code[]", "USA") in first and ("base_query", "intern") in first
        assert ("offset", 0) in first and ("result_limit", 100) in first
        assert ("offset", 100) in get.call_args_list[1].kwargs["params"]

    def test_no_hits(self):
        with patch("phlux.adapters.amazon.get", return_value=response({"error": None, "hits": 0, "jobs": []})):
            assert fetch(SEARCH) == []

    def test_ignored_filter_widening_to_whole_site_is_refused(self):
        with patch("phlux.adapters.amazon.get", return_value=response({"error": None, "hits": 10000, "jobs": [job(1, "x")]})):
            with pytest.raises(RuntimeError, match="ignored"):
                fetch("https://www.amazon.jobs/en/search?base_qery=intern")


class TestTeamPage:
    def test_body_combines_page_scope_and_url_filters(self):
        body = team_search_body(TEAM, [{"teams": [
            {"identifier": "subsidiaries.team-amazon-robotics", "children": [{"identifier": "sub.child", "children": []}]},
        ]}])
        assert body["contentFilterFacets"][0]["values"] == [
            {"name": "sub.child"}, {"name": "subsidiaries.team-amazon-robotics"}]
        assert body["jobTypeFacets"] == [{"name": "employeeClass", "values": [{"name": "Intern"}]}]
        assert body["locationFacets"][0][0]["values"] == [{"name": "US"}]
        assert "values" not in body["locationFacets"][0][1]
        assert body["filterFacets"] == []

    def test_body_job_tags(self):
        body = team_search_body("https://amazon.jobs/content/en/teams/aws/internships?country%5B%5D=US",
                                [{"jobIds": [], "jobTags": ["aws.interns"], "locations": [], "teams": []}])
        assert body["filterFacets"] == [{"name": "optionalSearchLabels", "requestedFacetCount": 9999,
                                         "values": [{"name": "aws.interns"}]}]
        assert "values" not in body["contentFilterFacets"][0]

    def test_unknown_url_filter_is_refused(self):
        with pytest.raises(ValueError):
            team_search_body(TEAM + "&countries%5B%5D=US", [])

    def test_reads_postings_with_key_from_page(self):
        page = response(text=team_page([{"teams": [{"identifier": "t", "children": []}]}]), url=TEAM)
        result = {"found": 2, "searchHits": [hit(11, "Robotics  Intern"), hit(12, "Co-op")], "facets": [], "start": 0}
        with patch("phlux.adapters.amazon.get", return_value=page), \
                patch("phlux.adapters.amazon.post", return_value=response(result)) as post:
            postings = fetch(TEAM)
        assert [(p.id, p.title) for p in postings] == [("amazon:11", "Robotics Intern"), ("amazon:12", "Co-op")]
        assert post.call_args.args == ("https://www.amazon.jobs/api/jobs/search?is_als=true",)
        assert post.call_args.kwargs["headers"]["X-Api-Key"] == "KEY123"

    def test_pages_through_results(self):
        page = response(text=team_page([]), url=TEAM)
        results = [
            {"found": 150, "searchHits": [hit(i, f"Job {i}") for i in range(100)]},
            {"found": 150, "searchHits": [hit(i, f"Job {i}") for i in range(100, 150)]},
        ]
        with patch("phlux.adapters.amazon.get", return_value=page), \
                patch("phlux.adapters.amazon.post", side_effect=[response(r) for r in results]) as post:
            postings = fetch(TEAM)
        assert len(postings) == 150
        assert [c.kwargs["json"]["start"] for c in post.call_args_list] == [0, 100]

    def test_no_hits_answer_is_all_null(self):
        page = response(text=team_page([]), url=TEAM)
        empty = {"found": None, "searchHits": None, "facets": None, "start": None}
        with patch("phlux.adapters.amazon.get", return_value=page), \
                patch("phlux.adapters.amazon.post", return_value=response(empty)):
            assert fetch(TEAM) == []

    def test_whole_site_answer_is_refused(self):
        page = response(text=team_page([]), url=TEAM)
        with patch("phlux.adapters.amazon.get", return_value=page), \
                patch("phlux.adapters.amazon.post", return_value=response({"found": 22436, "searchHits": []})):
            with pytest.raises(RuntimeError):
                fetch(TEAM)


def test_other_pages_are_refused():
    with pytest.raises(ValueError):
        fetch("https://www.amazon.jobs/en/jobs/123/some-job")
