"""Tests for phlux/adapters/citadel.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import citadel

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.citadel.com/careers/details/software-engineer-intern-us/</loc></url>
  <url><loc>https://www.citadel.com/careers/details/software-engineer-intern-europe/</loc></url>
  <url><loc>https://www.citadel.com/careers/details/quantitative-researcher-phd-graduate-us/</loc></url>
  <url><loc>https://www.citadel.com/careers/details/equities-citadel-associate-program-summer-internship-2028/</loc></url>
  <url><loc>https://www.citadel.com/careers/details/commodities-analyst/</loc></url>
</urlset>"""

SEARCH = "https://www.citadel.com/careers/open-opportunities"


def fetch(url):
    response = MagicMock(text=SITEMAP)
    with patch("phlux.adapters.citadel.get", return_value=response) as get:
        postings = citadel.fetch(url)
    get.assert_called_once_with("https://www.citadel.com/career-sitemap.xml")
    return postings


class TestSlugTitle:
    @pytest.mark.parametrize("slug, title", [
        ("software-engineer-intern-us", "Software Engineer Intern (US)"),
        ("machine-learning-researcher-phd-intern-asia", "Machine Learning Researcher PhD Intern (Asia)"),
        ("human-resources-mba-intern-us", "Human Resources MBA Intern (US)"),
        ("commodities-analyst", "Commodities Analyst"),
    ])
    def test_slug_title(self, slug, title):
        assert citadel.slug_title(slug) == title


class TestFetch:
    def test_whole_board_without_filters(self):
        postings = fetch(SEARCH)
        assert [p.id for p in postings] == [
            "citadel:software-engineer-intern-us",
            "citadel:software-engineer-intern-europe",
            "citadel:quantitative-researcher-phd-graduate-us",
            "citadel:equities-citadel-associate-program-summer-internship-2028",
            "citadel:commodities-analyst",
        ]

    def test_internships_in_american_offices(self):
        postings = fetch(SEARCH + "?experience-filter=internships&location-filter=americas,chicago,new-york")
        # A slug with no region (the associate program) is kept: its region is unknown.
        assert [p.title for p in postings] == [
            "Software Engineer Intern (US)",
            "Equities Citadel Associate Program Summer Internship 2028",
        ]

    def test_office_names_map_to_regions(self):
        assert citadel.wanted_regions("london,hong-kong") == {"Europe", "Asia"}
        assert citadel.wanted_regions("") == set()
