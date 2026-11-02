"""Tests for phlux/discovery/names.py — name keys, domains and slug guesses."""
import pytest

from phlux.discovery.names import (
    bare_label,
    core_key,
    display_name,
    domain_label,
    legal_key,
    name_key,
    name_variants,
    names_match,
    registrable_domain,
    slug_guesses,
    slug_key,
)


@pytest.mark.parametrize("name, key", [
    ("Welch’s ", "welchs"),
    ("Welch's", "welchs"),
    ("Pony.ai", "ponyai"),
    ("Ambi Robotics, Inc.", "ambiroboticsinc"),
    ("Café Robotique", "caferobotique"),
    ("R&D Labs", "randdlabs"),
])
def test_name_key(name, key):
    assert name_key(name) == key


@pytest.mark.parametrize("name, core", [
    ("Relativity Space", "relativity"),
    ("Relativity", "relativity"),
    ("Machina Labs, Inc.", "machina"),
    ("Path Robotics", "path"),
    ("Robotics", "robotics"),  # nothing else left: keep it
    ("The Bot Company", "bot"),
])
def test_core_key_drops_generic_trailing_words(name, core):
    assert core_key(name) == core


def test_legal_key_drops_only_the_legal_form():
    assert legal_key("Ambi Robotics, Inc.") == "ambirobotics"
    assert legal_key("Acme Co") == "acme"
    assert legal_key("Inc") == "inc"


def test_names_match_needs_a_long_core():
    assert names_match("Relativity Space", "Relativity")
    assert names_match("Acme Robotics, Inc.", "Acme Robotics")  # short core, but only "Inc" differs
    assert names_match("Welch’s ", "Welch's")
    # "path" is too short a core: Path Robotics and PathAI are different companies.
    assert not names_match("Path Robotics", "PathAI")


def test_name_variants_split_aliases():
    assert name_variants("Flirtey (SkyDrop)") == ["Flirtey", "SkyDrop"]
    assert name_variants("Acme") == ["Acme"]


@pytest.mark.parametrize("name, shown", [
    ("Applied Electrodynamics, Inc.", "Applied Electrodynamics"),
    ("Galactic Resource Utilization Space, Inc. (GRU Space)", "Galactic Resource Utilization Space"),
    ("Volta Labs, Inc.", "Volta Labs"),
    ("Acme Co", "Acme"),
    ("EPIC AEROSPACE", "EPIC AEROSPACE"),
])
def test_display_name(name, shown):
    assert display_name(name) == shown


@pytest.mark.parametrize("url, domain", [
    ("https://careers.irobot.com/search-jobs", "irobot.com"),
    ("http://www.Relativityspace.com", "relativityspace.com"),
    ("relativityspace.com/careers", "relativityspace.com"),
    ("https://jobs.acme.co.uk/x", "acme.co.uk"),
    ("https://www.1x.tech:443/", "1x.tech"),
    ("", ""),
])
def test_registrable_domain(url, domain):
    assert registrable_domain(url) == domain


def test_domain_label_and_slug_key():
    assert domain_label("relativityspace.com") == "relativityspace"
    assert slug_key("ispace-inc") == "ispaceinc"
    assert slug_key("Superhuman%20Platform%20Inc") == "superhumanplatforminc"


def test_bare_label_strips_startup_affixes():
    assert bare_label("getacme") == "acme"
    assert bare_label("acmehq") == "acme"
    assert bare_label("getty") == "getty"  # too little left after the prefix
    assert bare_label("acme") == "acme"


def test_slug_guesses_most_specific_first():
    assert slug_guesses("Relativity Space", ["relativityspace.com"]) == [
        "relativityspace", "relativity-space", "relativity"]


def test_slug_guesses_use_the_domain():
    assert slug_guesses("Navier", ["navierboat.com"]) == ["navier", "navierboat"]
    assert "acme" in slug_guesses("Acme Robotics", ["getacme.com"], limit=10)
