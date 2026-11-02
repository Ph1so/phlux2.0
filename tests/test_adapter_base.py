"""Tests for the location helpers in phlux/adapters/base.py."""
import pytest

from phlux.adapters.base import country_name, format_place, is_us, place, tidy_place, us_state


@pytest.mark.parametrize("primary, others, expected", [
    ("Austin, TX", [], "Austin, TX"),
    ("Austin, TX", ["Dallas, TX", "Austin, TX", " Dallas,  TX"], "Austin, TX +1"),
    (None, ["", "Remote"], "Remote"),
    ("", [], ""),
])
def test_place(primary, others, expected):
    assert place(primary, others) == expected


def test_boards_use_the_same_place():
    from phlux import boards
    assert boards.place is place


@pytest.mark.parametrize("city, region, country, expected", [
    ("Santa Clara", "California", "United States of America", "Santa Clara, CA"),
    ("Florence", "KY", "us", "Florence, KY"),
    ("New York City", "New York", "USA", "New York City, NY"),
    ("Washington", "District of Columbia", "US", "Washington, DC"),
    ("Fremont", "California", "", "Fremont, CA"),
    ("Springfield", "", "US", "Springfield"),
    ("", "Texas", "US", "Texas"),
    ("", "", "United States", "United States"),
    ("Munich", "Bavaria", "Germany", "Munich, Germany"),
    ("Munich", "BY", "DE", "Munich, Germany"),
    ("Toronto", "ON", "CA", "Toronto, Canada"),
    ("Toronto", "ON", "CAN", "Toronto, Canada"),
    ("Tokyo", "", "JP", "Tokyo, Japan"),
    ("Singapore", "", "SG", "Singapore"),
    ("Vancouver", "BC", "", "Vancouver"),
    ("", "", "Germany", "Germany"),
    (None, None, None, ""),
])
def test_format_place(city, region, country, expected):
    assert format_place(city, region, country) == expected


@pytest.mark.parametrize("text, expected", [
    ("Santa Clara, California, United States of America", "Santa Clara, CA"),
    ("San Diego, CA, US", "San Diego, CA"),
    ("Mountain View, CA, USA", "Mountain View, CA"),
    ("Austin, Texas, United States (USA)", "Austin, TX"),
    ("San Francisco, California", "San Francisco, CA"),
    ("Washington, District of Columbia", "Washington, DC"),
    ("York, PA 17402", "York, PA"),
    ("NJ,US", "New Jersey"),
    ("MI, United States", "Michigan"),
    ("Atlanta, Georgia, United States", "Atlanta, GA"),
    # Without a country, Georgia may be the country.
    ("Tbilisi, Georgia", "Tbilisi, Georgia"),
    ("Tokyo, Tokyo", "Tokyo"),
    ("Mexico City, Mexico City, Mexico", "Mexico City, Mexico"),
    ("Gurugram, Haryana, India", "Gurugram, Haryana, India"),
    ("Toronto, ON", "Toronto, ON"),
    ("Remote, United States", "Remote, United States"),
    ("Remote (United States)", "Remote (United States)"),
    ("United States", "United States"),
    ("  Los   Angeles ,CA ", "Los Angeles, CA"),
    (None, ""),
])
def test_tidy_place(text, expected):
    assert tidy_place(text) == expected


def test_lookups():
    assert is_us("United States of America") and is_us(" usa ") and not is_us("CA")
    assert us_state("California") == us_state("ca") == "CA" and us_state("Ontario") == ""
    assert country_name("GB") == "United Kingdom" and country_name("Slovensko") == "Slovensko"
