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

# The index robots.txt names, as citadel.com served it in Nov 2026.
INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://www.citadel.com/sitemap/page.xml</loc></sitemap>
  <sitemap><loc>https://www.citadel.com/sitemap/post.xml</loc></sitemap>
  <sitemap><loc>https://www.citadel.com/sitemap/career.xml</loc></sitemap>
  <sitemap><loc>https://www.citadel.com/sitemap/career-perspectives.xml</loc></sitemap>
  <sitemap><loc>https://www.citadel.com/sitemap/leadership.xml</loc></sitemap>
</sitemapindex>"""

SEARCH = "https://www.citadel.com/careers/open-opportunities"
PAGES = {"https://www.citadel.com/sitemap.xml": INDEX, "https://www.citadel.com/sitemap/career.xml": SITEMAP}


def fetch(url, pages=PAGES):
    with patch("phlux.adapters.citadel.get", side_effect=lambda u: MagicMock(text=pages[u])) as get:
        postings = citadel.fetch(url)
    assert [c.args[0] for c in get.call_args_list] == list(pages)
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
        assert postings[0].url == "https://www.citadel.com/careers/details/software-engineer-intern-us/"

    def test_internships_in_american_offices(self):
        postings = fetch(SEARCH + "?experience-filter=internships&location-filter=americas,chicago,new-york")
        # A slug with no region (the associate program) is kept: its region is unknown.
        assert [p.title for p in postings] == [
            "Software Engineer Intern (US)",
            "Equities Citadel Associate Program Summer Internship 2028",
        ]

    def test_new_graduates_keeps_graduate_slugs(self):
        postings = fetch(SEARCH + "?experience-filter=new-graduates&location-filter=americas")
        assert [p.id for p in postings] == ["citadel:quantitative-researcher-phd-graduate-us"]

    def test_office_names_map_to_regions(self):
        assert citadel.wanted_regions("london,hong-kong") == {"Europe", "Asia"}
        assert citadel.wanted_regions("") == set()


class TestCareerSitemaps:
    def test_found_in_the_index_without_career_stories(self):
        with patch("phlux.adapters.citadel.get", return_value=MagicMock(text=INDEX)):
            assert citadel.career_sitemaps("www.citadel.com") == ["https://www.citadel.com/sitemap/career.xml"]

    def test_old_name_still_found(self):
        index = "<sitemapindex><sitemap><loc>https://www.citadel.com/career-sitemap.xml</loc></sitemap></sitemapindex>"
        with patch("phlux.adapters.citadel.get", return_value=MagicMock(text=index)):
            assert citadel.career_sitemaps("www.citadel.com") == ["https://www.citadel.com/career-sitemap.xml"]

    def test_missing_career_sitemap_is_an_error(self):
        index = "<sitemapindex><sitemap><loc>https://www.citadel.com/sitemap/page.xml</loc></sitemap></sitemapindex>"
        with patch("phlux.adapters.citadel.get", return_value=MagicMock(text=index)):
            with pytest.raises(ValueError, match="No career sitemap"):
                citadel.career_sitemaps("www.citadel.com")


def test_location_is_the_slugs_region():
    postings = fetch(SEARCH)
    assert [p.location for p in postings] == ["US", "Europe", "US", "", ""]
