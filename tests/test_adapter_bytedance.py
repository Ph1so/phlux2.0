"""Tests for phlux/adapters/bytedance.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.bytedance import fetch, location, search_body, site_of

TIKTOK = ("https://lifeattiktok.com/search?keyword=&recruitment_id_list=202%2C301&job_category_id_list="
          "&subject_id_list=111%2C222&location_code_list=CT_157%2CCT_94&limit=12&offset=0")
BYTEDANCE = "https://joinbytedance.com/search?keyword=intern&limit=12&offset=0&recruitment_id_list=202"

SEATTLE = {"code": "CT_157", "location_type": 3, "en_name": "Seattle", "parent": {
    "code": "ST_54", "location_type": 2, "en_name": "Washington", "parent": {
        "code": "CN_6", "location_type": 1, "en_name": "United States of America", "parent": None}}}


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def job(i, title="SRE Intern", city=SEATTLE):
    return {"id": str(i), "title": title, "description": "About the team", "requirement": "Pursuing a BS",
            "city_info": city, "recruit_type": {"id": "202", "en_name": "Intern"}}


def page(jobs, count):
    return response({"code": 0, "data": {"job_post_list": jobs, "count": count}})


def test_registered():
    assert ADAPTERS["bytedance"] is fetch


def test_site_of():
    assert site_of(TIKTOK).website_path == "tiktok"
    assert site_of("https://www.joinbytedance.com/search").api.startswith("https://jobs.bytedance.com/")
    with pytest.raises(ValueError):
        site_of("https://careers.example.com/search")


def test_search_body_reads_the_url_filters():
    assert search_body(TIKTOK) == {
        "keyword": "", "recruitment_id_list": ["202", "301"], "subject_id_list": ["111", "222"],
        "location_code_list": ["CT_157", "CT_94"], "job_category_id_list": [], "tag_id_list": [],
    }
    assert search_body(BYTEDANCE)["keyword"] == "intern"


@pytest.mark.parametrize("city, expected", [
    (SEATTLE, "Seattle, WA"),
    ({"location_type": 3, "en_name": "London", "parent": {"location_type": 1, "en_name": "United Kingdom"}},
     "London, United Kingdom"),
    ({"location_type": 3, "en_name": "Singapore", "parent": {"location_type": 1, "en_name": "Singapore"}},
     "Singapore"),
    (None, ""),
])
def test_location(city, expected):
    assert location(city) == expected


def test_reads_postings_with_ids_links_places_and_text():
    with patch("phlux.adapters.bytedance.post", return_value=page([job(7670874691332212997)], 1)) as post:
        postings = fetch(TIKTOK)
    [p] = postings
    assert p.id == "bytedance:7670874691332212997"
    assert p.title == "SRE Intern" and p.location == "Seattle, WA"
    assert p.url == "https://lifeattiktok.com/search/7670874691332212997"
    assert p.description == "About the team\n\nPursuing a BS"
    args, kwargs = post.call_args
    assert args[0] == "https://api.lifeattiktok.com/api/v1/public/supplier/search/job/posts"
    assert kwargs["headers"]["website-path"] == "tiktok"
    assert kwargs["headers"]["origin"] == "https://lifeattiktok.com"
    assert kwargs["json"]["recruitment_id_list"] == ["202", "301"]
    assert kwargs["json"]["offset"] == 0 and kwargs["json"]["limit"] == 100


def test_bytedance_site_links_to_its_own_pages():
    with patch("phlux.adapters.bytedance.post", return_value=page([job(5)], 1)) as post:
        [p] = fetch(BYTEDANCE)
    assert p.url == "https://joinbytedance.com/search/5"
    assert post.call_args.kwargs["headers"]["website-path"] == "en"


def test_pages_until_the_count_is_read():
    pages = [page([job(i) for i in range(100)], 150), page([job(i) for i in range(100, 150)], 150)]
    with patch("phlux.adapters.bytedance.post", side_effect=pages) as post, \
            patch("phlux.adapters.bytedance.time.sleep"):
        postings = fetch(TIKTOK)
    assert len(postings) == 150 and len({p.id for p in postings}) == 150
    assert [c.kwargs["json"]["offset"] for c in post.call_args_list] == [0, 100]


def test_stops_on_a_repeated_page():
    pages = [page([job(1), job(2)], 9), page([job(1), job(2)], 9)]
    with patch("phlux.adapters.bytedance.post", side_effect=pages), \
            patch("phlux.adapters.bytedance.time.sleep"):
        assert [p.id for p in fetch(TIKTOK)] == ["bytedance:1", "bytedance:2"]


def test_api_error_raises():
    with patch("phlux.adapters.bytedance.post", return_value=response({"code": 1, "message": "invalid request"})):
        with pytest.raises(ValueError):
            fetch(TIKTOK)
