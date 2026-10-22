"""Tests for phlux/adapters/meta.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters import meta
from phlux.adapters.meta import fetch, search_input

URL = "https://www.metacareers.com/jobsearch/?roles[0]=Internship"
SCRIPT = "https://static.xx.fbcdn.net/rsrc.php/v4/yA/r/abc.js"
PAGE = (f'<script src="https://static.xx.fbcdn.net/rsrc.php/v4/yB/r/first.js"></script>'
        f'<script src="{SCRIPT}"></script>'
        '<script>requireLazy(["Bootloader"],function(){["LSD",[],{"token":"TOKEN1"},323]});</script>')


def response(text="", url=URL):
    mock = MagicMock()
    mock.text = text
    mock.url = url
    return mock


def results(*jobs):
    return json.dumps({"data": {"job_search_with_featured_jobs": {
        "all_jobs": [{"id": i, "title": t, "locations": []} for i, t in jobs],
        "featured_jobs": [{"id": "999", "title": "Featured, not a result"}],
    }}}) + '\n{"extensions":{"is_final":true}}'


@pytest.fixture(autouse=True)
def known_doc_id(monkeypatch):
    monkeypatch.setattr(meta, "_doc_id", meta.DOC_ID)


def test_registered():
    assert ADAPTERS["meta"] is fetch


def test_search_input_from_url():
    got = search_input("https://www.metacareers.com/jobsearch/?roles[0]=Internship&roles[1]=Full%20time"
                       "&offices[]=Menlo%20Park%2C%20CA&q=robotics&is_remote_only=true&teams=")
    assert got["roles"] == ["Internship", "Full time"]
    assert got["offices"] == ["Menlo Park, CA"]
    assert got["teams"] == []
    assert got["q"] == "robotics" and got["is_remote_only"] is True and got["is_leadership"] is False
    assert got["results_per_page"] is None


def test_reads_results_not_featured_jobs():
    with patch("phlux.adapters.meta.get", return_value=response(PAGE)), \
            patch("phlux.adapters.meta.post", return_value=response(results(("1", "Software  Engineer Intern")))) as post:
        postings = fetch(URL)
    assert [(p.id, p.title) for p in postings] == [("meta:1", "Software Engineer Intern")]
    form = post.call_args.kwargs["data"]
    assert form["lsd"] == "TOKEN1" and form["doc_id"] == meta.DOC_ID
    assert json.loads(form["variables"])["search_input"]["roles"] == ["Internship"]
    assert post.call_args.kwargs["headers"]["X-FB-LSD"] == "TOKEN1"
    assert post.call_args.kwargs["headers"]["Sec-Fetch-Mode"] == "cors"


def test_stale_doc_id_is_found_again_in_the_page_scripts():
    stale = json.dumps({"errors": [{"message": "The GraphQL document with ID 1 was not found.", "severity": "CRITICAL"}]})
    module = ('__d("CareersJobSearchResultsDataQuery_candidate_portalRelayOperation",[],'
              '(function(t,n,r,o,a,i){a.exports="4242"}),null);')

    def get(url, **kwargs):
        if url == URL:
            return response(PAGE)
        return response(module if url == SCRIPT else "/* other code */")

    with patch("phlux.adapters.meta.get", side_effect=get), \
            patch("phlux.adapters.meta.post", side_effect=[response(stale), response(results(("2", "Intern")))]) as post:
        postings = fetch(URL)
    assert [p.id for p in postings] == ["meta:2"]
    assert post.call_args.kwargs["data"]["doc_id"] == "4242"
    assert meta._doc_id == "4242"


def test_other_graphql_errors_raise():
    error = json.dumps({"errors": [{"message": "Rate limited"}]})
    with patch("phlux.adapters.meta.get", return_value=response(PAGE)), \
            patch("phlux.adapters.meta.post", return_value=response(error)):
        with pytest.raises(RuntimeError, match="Rate limited"):
            fetch(URL)


def test_page_without_token_raises():
    with patch("phlux.adapters.meta.get", return_value=response("<html></html>")):
        with pytest.raises(RuntimeError):
            fetch(URL)
