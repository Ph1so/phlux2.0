"""Tests for phlux/adapters/paycom.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.paycom import fetch, session

URL = "https://www.paycomonline.net/v4/ats/web.php/portal/32B3464F7837FF4F95871E123F85C49C/career-page"
HOST = "https://portal-applicant-tracking.us-east.paycomonline.net"
HTML = (
    f'<link href="{HOST}/career-portal/sprawl.json">'
    '<script>    var configsFromHost = {"sessionJWT":"eyJ.abc.def","i18n":"en-US"};</script>'
)


def response(payload=None, text=""):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.text = text
    return mock


def test_registered():
    assert ADAPTERS["paycom"] is fetch


def test_session_reads_token_and_api_host():
    assert session(HTML) == ("eyJ.abc.def", HOST)


def test_session_without_config_raises():
    with pytest.raises(ValueError):
        session("<html></html>")


def test_searches_with_token_and_pages():
    first = {"jobPostingPreviewsCount": 3, "jobPostingPreviews": [
        {"jobId": 299627, "jobTitle": "Enterprise Account Executive"},
        {"jobId": 334846, "jobTitle": "Robot Software Engineer II"},
    ]}
    second = {"jobPostingPreviewsCount": 3, "jobPostingPreviews": [{"jobId": 1, "jobTitle": "Intern"}]}
    with patch("phlux.adapters.paycom.get", return_value=response(text=HTML)), \
         patch("phlux.adapters.paycom.PAGE_SIZE", 2), \
         patch("phlux.adapters.paycom.post", side_effect=[response(first), response(second)]) as post:
        postings = fetch(URL)
    assert [(p.id, p.title) for p in postings] == [
        ("paycom:299627", "Enterprise Account Executive"),
        ("paycom:334846", "Robot Software Engineer II"),
        ("paycom:1", "Intern"),
    ]
    call = post.call_args_list[0]
    assert call.args == (HOST + "/api/ats/job-posting-previews/search",)
    assert call.kwargs["headers"] == {"Authorization": "eyJ.abc.def", "Portal-Host-Referrer": URL}
    assert [c.kwargs["json"]["skip"] for c in post.call_args_list] == [0, 2]


def test_empty_portal():
    with patch("phlux.adapters.paycom.get", return_value=response(text=HTML)), \
         patch("phlux.adapters.paycom.post", return_value=response({"jobPostingPreviewsCount": 0,
                                                                     "jobPostingPreviews": []})) as post:
        assert fetch(URL) == []
    assert post.call_count == 1
