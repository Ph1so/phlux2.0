"""Tests for phlux/adapters/tencent.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.tencent import fetch, location, parse_query

URL = "https://join.qq.com/post.html?query=p_2,w_407,w_401,2_75,b_956&c_t=2"
MAPPING = {"status": 0, "data": [
    {"id": 1, "subProjectList": [{"mappingId": 1, "projectName": "2027校园招聘"}]},
    {"id": 2, "subProjectList": [{"mappingId": 2, "projectName": "应届实习"}, {"mappingId": 104}]},
]}


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def job(i, title="Marketing Intern 108206", cities="US-California-Palo Alto", source="workday"):
    url = f"https://tencent.wd1.myworkdayjobs.com/Tencent_Careers/job/US-California-Palo-Alto/X_R{i}" if source == "workday" else None
    return {"id": int(i), "postId": str(i), "positionTitle": title, "workCities": cities,
            "positionUrl": url, "positionSource": source, "projectId": 2}


def page(jobs, count):
    return response({"status": 0, "data": {"positionList": jobs, "count": count}})


def test_registered():
    assert ADAPTERS["tencent"] is fetch


def test_parse_query():
    assert parse_query(URL) == {"p": ["2"], "w": ["407", "401"], "r": [], "b": ["956"], "family": ["75"]}


@pytest.mark.parametrize("text, expected", [
    ("US-California-Palo Alto", "Palo Alto, CA"),
    ("US-Washington-Bellevue", "Bellevue, WA"),
    ("United Kingdom-London", "London, United Kingdom"),
    ("深圳总部 北京 上海 ", "深圳总部 +2"),
    ("北京 ", "北京"),
    ("", ""),
])
def test_location(text, expected):
    assert location(text) == expected


def test_reads_the_url_search():
    with patch("phlux.adapters.tencent.get", return_value=response(MAPPING)), \
            patch("phlux.adapters.tencent.post", return_value=page([job(2097419740439031808)], 1)) as post:
        [p] = fetch(URL)
    assert p.id == "tencent:2097419740439031808"
    assert p.title == "Marketing Intern 108206" and p.location == "Palo Alto, CA"
    assert p.url.startswith("https://tencent.wd1.myworkdayjobs.com/Tencent_Careers/job/")
    body = post.call_args.kwargs["json"]
    assert body["projectMappingIdList"] == [2]
    assert body["workCountryType"] == 2 and body["workCityList"] == ["407", "401"]
    assert body["positionFidList"] == ["75"] and body["bgList"] == ["956"]
    assert body["pageIndex"] == 1 and body["keyword"] == ""


def test_jobs_in_china_open_on_the_site():
    with patch("phlux.adapters.tencent.get", return_value=response(MAPPING)), \
            patch("phlux.adapters.tencent.post", return_value=page([job(9, "AI应用工程师", "深圳总部 北京 ", "oa")], 1)):
        [p] = fetch(URL)
    assert p.url == "https://join.qq.com/post_detail.html?postid=9" and p.location == "深圳总部 +1"


def test_unlisted_project_searches_all_projects():
    with patch("phlux.adapters.tencent.get", return_value=response(MAPPING)), \
            patch("phlux.adapters.tencent.post", return_value=page([], 0)) as post:
        fetch("https://join.qq.com/post.html?query=p_99")
    body = post.call_args.kwargs["json"]
    assert body["projectMappingIdList"] == [1, 2, 104]
    # Cities without c_t are not applied, as on the page.
    assert body["workCountryType"] == 0 and body["workCityList"] == []


def test_every_city_abroad():
    cities = {"status": 0, "data": {"1": [{"code": "1"}], "2": [{"code": "401"}, {"code": "1401"}]}}
    with patch("phlux.adapters.tencent.get", side_effect=[response(cities), response(MAPPING)]), \
            patch("phlux.adapters.tencent.post", return_value=page([], 0)) as post:
        fetch("https://join.qq.com/post.html?query=p_2&f_c=all")
    body = post.call_args.kwargs["json"]
    assert body["workCountryType"] == 2 and body["workCityList"] == ["401", "1401"]


def test_pages_until_the_count_is_read():
    pages = [page([job(i) for i in range(100)], 120), page([job(i) for i in range(100, 120)], 120)]
    with patch("phlux.adapters.tencent.get", return_value=response(MAPPING)), \
            patch("phlux.adapters.tencent.post", side_effect=pages) as post, \
            patch("phlux.adapters.tencent.time.sleep"):
        postings = fetch(URL)
    assert len({p.id for p in postings}) == 120
    assert [c.kwargs["json"]["pageIndex"] for c in post.call_args_list] == [1, 2]


def test_api_error_raises():
    with patch("phlux.adapters.tencent.get", return_value=response({"status": 500, "message": "busy"})):
        with pytest.raises(ValueError):
            fetch(URL)
