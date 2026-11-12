"""Tests for phlux/site/logos.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

from phlux.site import logos

ICONS = {
    "Acme Robotics": {"readme": "https://cdn.brandfetch.io/acme.com/w/400/h/400?c=abc", "email": "x"},
    "Beta": "https://www.google.com/s2/favicons?domain=beta.ai&sz=128",
    "Gamma": "",
}


def image(content=b"RIFF....WEBP", mime="image/webp"):
    response = MagicMock()
    response.content = content
    response.headers = {"content-type": mime}
    return response


def test_sized_asks_for_a_small_logo():
    assert logos.sized("https://cdn.brandfetch.io/acme.com/w/400/h/400?c=abc") == \
        "https://cdn.brandfetch.io/acme.com/w/64/h/64?c=abc"
    assert logos.sized("https://www.google.com/s2/favicons?domain=beta.ai&sz=128") == \
        "https://www.google.com/s2/favicons?domain=beta.ai&sz=64"


def test_fetches_each_logo_once_and_embeds_it(tmp_path):
    with patch("phlux.site.logos.get", return_value=image()) as get:
        assert logos.fetch_missing(["Acme Robotics", "Beta", "Gamma"], ICONS, tmp_path) == 2
        assert logos.fetch_missing(["Acme Robotics", "Beta", "Gamma"], ICONS, tmp_path) == 0
    assert get.call_count == 2
    assert (tmp_path / "acme-robotics.webp").read_bytes() == b"RIFF....WEBP"
    assert json.loads((tmp_path / "sources.json").read_text())["beta"] == ICONS["Beta"]
    assert logos.data_uri("Acme Robotics", tmp_path) == "data:image/webp;base64,UklGRi4uLi5XRUJQ"
    assert logos.data_uri("Gamma", tmp_path) == ""


def test_a_changed_icon_replaces_the_old_file(tmp_path):
    with patch("phlux.site.logos.get", return_value=image()):
        logos.fetch_missing(["Beta"], ICONS, tmp_path)
    with patch("phlux.site.logos.get", return_value=image(b"\x89PNG", "image/png")):
        logos.fetch_missing(["Beta"], {"Beta": "https://cdn.brandfetch.io/beta.ai/w/400/h/400"}, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["beta.png", "sources.json"]


def test_a_failed_or_odd_download_is_skipped(tmp_path):
    with patch("phlux.site.logos.get", side_effect=RuntimeError("403")):
        assert logos.fetch_missing(["Beta"], ICONS, tmp_path) == 0
    with patch("phlux.site.logos.get", return_value=image(b"<html>", "text/html")):
        assert logos.fetch_missing(["Beta"], ICONS, tmp_path) == 0
    assert logos.data_uri("Beta", tmp_path) == ""
