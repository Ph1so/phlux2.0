"""Tests for phlux/adapters/workday.py (the Workday API is mocked)."""
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from phlux.adapters import ADAPTERS
from phlux.adapters import workday
from phlux.adapters.workday import MAX_PAGES, fetch, job_id, parse_board
from phlux.boards import BOARDS
from phlux.scraping import board_of, get_board_jobs

US = "bc33aa3152ec42d4995f4791a106ed09"
INTERN = "0c40f6bd1d8f10adf6dae42e46d44a17"
NVIDIA_API = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"


def job(n, title=None):
    return {
        "title": title or f"Job {n}",
        "externalPath": f"/job/US-CA-Santa-Clara/Job-{n}_JR{n:04d}",
        "locationsText": "US, CA, Santa Clara",
        "postedOn": "Posted Today",
        "bulletFields": [f"JR{n:04d}"],
    }


def page(jobs, total, facets=None):
    return {"total": total, "jobPostings": jobs, "facets": facets or []}


def board(jobs, total=None, later_total=None, page_size=20):
    """Return a fake ``post`` serving *jobs* 20 at a time, and its list of calls.

    Pages after the first report *later_total* (the API's habit of sending 0).
    """
    calls = []
    total = len(jobs) if total is None else total

    def post(url, json=None, headers=None, **kwargs):
        calls.append((url, json, headers))
        offset = json["offset"]
        chunk = jobs[offset:offset + page_size]
        response = MagicMock()
        response.json.return_value = page(chunk, total if offset == 0 or later_total is None else later_total)
        return response

    return patch("phlux.adapters.workday.post", side_effect=post), calls


class TestParseBoard:
    @pytest.mark.parametrize("url, api", [
        ("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/jobs?workerSubType=1",
         NVIDIA_API),
        ("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite", NVIDIA_API),
        ("https://NVIDIA.wd5.myworkdayjobs.com/fr-CA/NVIDIAExternalCareerSite/", NVIDIA_API),
        ("https://redhat.wd5.myworkdayjobs.com/jobs/?a=1&d=2",
         "https://redhat.wd5.myworkdayjobs.com/wday/cxs/redhat/jobs/jobs"),
        ("https://boseallaboutme.wd503.myworkdayjobs.com/Bose_Careers/jobs?workerSubType=1",
         "https://boseallaboutme.wd503.myworkdayjobs.com/wday/cxs/boseallaboutme/Bose_Careers/jobs"),
        ("https://wd5.myworkdaysite.com/en-US/recruiting/acme/External",
         "https://wd5.myworkdaysite.com/wday/cxs/acme/External/jobs"),
    ])
    def test_api_endpoint(self, url, api):
        assert parse_board(url).api == api

    def test_repeated_params_become_one_facet_with_several_ids(self):
        url = (f"https://cat.wd5.myworkdayjobs.com/en-US/CaterpillarCareers"
               f"?workerSubType=a&workerSubType=b&locationCountry={US}")
        assert parse_board(url).facets == {"workerSubType": ["a", "b"], "locationCountry": [US]}

    def test_q_is_the_search_text_not_a_facet(self):
        result = parse_board(f"https://leidos.wd5.myworkdayjobs.com/External?q=intern&locationCountry={US}")
        assert result.search == "intern"
        assert result.facets == {"locationCountry": [US]}

    def test_tracking_and_blank_params_are_dropped(self):
        url = ("https://workday.wd5.myworkdayjobs.com/Workday_Early_Career/"
               "?source=Careers_Website_ec&utm_medium=x&jobFamily=&timeType=1")
        result = parse_board(url)
        assert result.facets == {"timeType": ["1"]}
        assert result.search == ""

    @pytest.mark.parametrize("url", [
        "https://www.blueorigin.com/careers/search?search=undergraduate",
        "https://nvidia.wd5.myworkdayjobs.com/",
        "https://wd5.myworkdaysite.com/en-US/acme",
    ])
    def test_rejects_other_urls(self, url):
        with pytest.raises(ValueError):
            parse_board(url)


class TestJobId:
    @pytest.mark.parametrize("path, expected", [
        ("/job/US-WA-Redmond/PhD-Research-Intern---2027_JR2027089", "JR2027089"),
        ("/job/Tokyo/Strategic-Accounts-Manager---FSI_R-059788-2", "R-059788-2"),
        ("/job/Lowell-MA/Co-Op-Student-Engineering_JR002974", "JR002974"),
        ("/job/Somewhere/No-Id-Here", "/job/Somewhere/No-Id-Here"),
    ])
    def test_takes_the_id_after_the_last_underscore(self, path, expected):
        assert job_id({"externalPath": path}) == expected

    def test_none_without_a_path(self):
        assert job_id({"title": "Intern"}) is None


class TestFetch:
    URL = (f"https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/jobs"
           f"?workerSubType={INTERN}&locationHierarchy1={US}")

    def test_sends_the_url_facets_and_reads_ids_and_titles(self):
        mock, calls = board([job(1, "PhD  Research\nIntern"), job(2)])
        with mock:
            postings = fetch(self.URL)
        assert [(p.id, p.title) for p in postings] == [
            ("workday:JR0001", "PhD Research Intern"),
            ("workday:JR0002", "Job 2"),
        ]
        url, body, headers = calls[0]
        assert url == NVIDIA_API
        assert body == {
            "appliedFacets": {"workerSubType": [INTERN], "locationHierarchy1": [US]},
            "limit": 20, "offset": 0, "searchText": "",
        }
        assert headers["Referer"] == self.URL
        assert len(calls) == 1

    def test_pages_by_twenty_until_the_first_total(self):
        mock, calls = board([job(n) for n in range(45)])
        with mock:
            postings = fetch(self.URL)
        assert len(postings) == 45
        assert [body["offset"] for _, body, _ in calls] == [0, 20, 40]

    def test_later_pages_reporting_zero_total_do_not_stop_paging(self):
        mock, calls = board([job(n) for n in range(45)], later_total=0)
        with mock:
            postings = fetch(self.URL)
        assert len(postings) == 45
        assert len(calls) == 3

    def test_without_a_total_pages_until_an_empty_page(self):
        mock, calls = board([job(n) for n in range(25)], total=0)
        with mock:
            postings = fetch(self.URL)
        assert len(postings) == 25
        assert [body["offset"] for _, body, _ in calls] == [0, 20, 40]

    def test_search_text_is_sent(self):
        mock, calls = board([job(1)])
        with mock:
            fetch(f"https://leidos.wd5.myworkdayjobs.com/External?q=intern&locationCountry={US}")
        assert calls[0][1]["searchText"] == "intern"
        assert calls[0][1]["appliedFacets"] == {"locationCountry": [US]}

    def test_untitled_postings_are_skipped(self):
        mock, _ = board([job(1), {"bulletFields": ["R-1"]}, job(2)])
        with mock:
            postings = fetch(self.URL)
        assert [p.id for p in postings] == ["workday:JR0001", "workday:JR0002"]

    def test_repeated_postings_are_kept_once(self):
        mock, _ = board([job(1), job(1), job(2)])
        with mock:
            postings = fetch(self.URL)
        assert [p.id for p in postings] == ["workday:JR0001", "workday:JR0002"]

    def test_caps_requests_and_warns(self, caplog):
        mock, calls = board([job(n) for n in range(MAX_PAGES * 20 + 100)])
        with mock, caplog.at_level(logging.WARNING):
            postings = fetch(self.URL)
        assert len(calls) == MAX_PAGES
        assert len(postings) == MAX_PAGES * 20
        assert "read only the first" in caplog.text

    def test_unknown_param_is_dropped_after_a_400(self, caplog):
        calls = []
        facets = [{"facetParameter": "locationMainGroup", "values": [
            {"facetParameter": "locationCountry", "values": [{"id": US, "count": 1}]},
        ]}, {"facetParameter": "workerSubType", "values": [{"id": INTERN, "count": 1}]}]

        def post(url, json=None, headers=None, **kwargs):
            calls.append(json)
            response = MagicMock()
            if "trk" in json["appliedFacets"]:
                response.status_code = 400
                raise requests.HTTPError("400", response=response)
            response.json.return_value = page([job(1)], 1, facets)
            return response

        url = f"https://acme.wd1.myworkdayjobs.com/Careers?trk=abc&locationCountry={US}"
        with patch("phlux.adapters.workday.post", side_effect=post), caplog.at_level(logging.WARNING):
            postings = fetch(url)
        assert [p.id for p in postings] == ["workday:JR0001"]
        assert [c["appliedFacets"] for c in calls] == [
            {"trk": ["abc"], "locationCountry": [US]},
            {},
            {"locationCountry": [US]},
        ]
        assert "Ignoring trk" in caplog.text

    def test_other_errors_propagate(self):
        response = MagicMock(status_code=500)
        error = requests.HTTPError("500", response=response)
        with patch("phlux.adapters.workday.post", side_effect=error):
            with pytest.raises(requests.HTTPError):
                fetch(self.URL)

    def test_a_400_for_known_facets_propagates(self):
        bad = MagicMock(status_code=400)
        good = MagicMock()
        good.json.return_value = page([], 0, [{"facetParameter": "workerSubType", "values": []},
                                              {"facetParameter": "locationHierarchy1", "values": []}])

        def post(url, json=None, headers=None, **kwargs):
            if json["appliedFacets"]:
                raise requests.HTTPError("400", response=bad)
            return good

        with patch("phlux.adapters.workday.post", side_effect=post):
            with pytest.raises(requests.HTTPError):
                fetch(self.URL)


class TestRegistration:
    def test_registered_as_a_board(self):
        assert ADAPTERS["workday"] is workday.fetch
        assert "workday" in BOARDS
        assert board_of("@workday->FILTER:intern") == "workday"

    def test_scraper_applies_filter_and_stars(self):
        mock, _ = board([job(1, "Software Intern"), job(2, "Recruiter")])
        with mock:
            titles, ids = get_board_jobs("Acme", TestFetch.URL, "@workday->FILTER:intern")
        assert titles == ["⭐️ Software Intern"]
        assert ids == ["workday:JR0001"]
