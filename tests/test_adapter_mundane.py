"""Tests for phlux/adapters/mundane.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters import mundane
from phlux.adapters.mundane import fetch, job_posting, location, role_links

CAREERS = """
<nav><a href="/careers">Careers</a></nav>
<section id="roles">
  <details><summary><h2>Development</h2></summary><ul class="roles">
    <li><a href="/careers/controls-engineer"><span class="role-cell"><h3>Controls Engineer, Haptics</h3>
      <span class="role-summary">Own the control stack.</span></span><span class="mono">Full time</span></a></li>
    <li><a href="/careers/mechanical-engineering-co-op"><span class="role-cell">
      <h3>Mechanical Engineering Co‑op, Robot Hardware<span class="role-chip mono">Co‑op</span></h3>
      </span></a></li>
  </ul></details>
  <details><summary><h2>Research</h2></summary><ul class="roles">
    <li><a href="/careers/controls-engineer"><h3>Controls Engineer, Haptics</h3></a></li>
  </ul></details>
</section>
"""


def role_page(title, city="Palo Alto", region="CA", country="US"):
    posting = {
        "@context": "https://schema.org", "@type": "JobPosting", "title": title, "employmentType": "INTERN",
        "description": "<p>Build <b>robots</b>.</p>",
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": city,
                                                       "addressRegion": region, "addressCountry": country}},
    }
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []}
    return (f'<script type="application/ld+json">{json.dumps(crumbs)}</script>'
            f'<script type="application/ld+json">{json.dumps(posting)}</script>')


def test_registered():
    assert ADAPTERS["mundane"] is fetch


def test_role_links_skip_the_chip_and_careers_link():
    assert role_links(CAREERS, "https://mundane.co/careers") == [
        ("https://mundane.co/careers/controls-engineer", "Controls Engineer, Haptics"),
        ("https://mundane.co/careers/mechanical-engineering-co-op", "Mechanical Engineering Co-op, Robot Hardware"),
        ("https://mundane.co/careers/controls-engineer", "Controls Engineer, Haptics"),
    ]


def test_reads_each_role_page_once():
    pages = {
        "https://mundane.co/careers": CAREERS,
        "https://mundane.co/careers/controls-engineer": role_page("Controls Engineer, Haptics"),
        "https://mundane.co/careers/mechanical-engineering-co-op": role_page("Mechanical Engineering Co‑op"),
    }
    with patch.object(mundane, "get", side_effect=lambda url: MagicMock(text=pages[url])) as get, \
            patch.object(mundane.time, "sleep"):
        postings = fetch("https://mundane.co/careers")
    assert [(p.id, p.title, p.location, p.url) for p in postings] == [
        ("mundane:https://mundane.co/careers/controls-engineer", "Controls Engineer, Haptics", "Palo Alto, CA",
         "https://mundane.co/careers/controls-engineer"),
        ("mundane:https://mundane.co/careers/mechanical-engineering-co-op", "Mechanical Engineering Co-op",
         "Palo Alto, CA", "https://mundane.co/careers/mechanical-engineering-co-op"),
    ]
    assert postings[0].description == "Build robots ."
    assert get.call_count == 3


def test_role_page_without_posting_keeps_list_title():
    pages = {
        "https://mundane.co/careers": CAREERS,
        "https://mundane.co/careers/controls-engineer": "<html></html>",
        "https://mundane.co/careers/mechanical-engineering-co-op": "<html></html>",
    }
    with patch.object(mundane, "get", side_effect=lambda url: MagicMock(text=pages[url])), \
            patch.object(mundane.time, "sleep"):
        postings = fetch("https://mundane.co/careers")
    assert [(p.title, p.location) for p in postings] == [
        ("Controls Engineer, Haptics", ""), ("Mechanical Engineering Co-op, Robot Hardware", ""),
    ]


def test_job_posting_skips_bad_json():
    assert job_posting('<script type="application/ld+json">{not json</script>') is None


@pytest.mark.parametrize("posting, expected", [
    ({"jobLocation": {"address": {"addressLocality": "Palo Alto", "addressRegion": "CA", "addressCountry": "US"}}},
     "Palo Alto, CA"),
    ({"jobLocation": [{"address": {"addressLocality": "Boston", "addressRegion": "MA", "addressCountry": "US"}},
                      {"address": {"addressLocality": "Munich", "addressCountry": "DE"}}]}, "Boston, MA +1"),
    ({"jobLocationType": "TELECOMMUTE"}, "Remote"),
    ({}, ""),
])
def test_location(posting, expected):
    assert location(posting) == expected
