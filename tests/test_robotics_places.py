"""Tests for phlux/robotics/places.py and phlux/robotics/geo.py."""
import pytest

from phlux.robotics import geo
from phlux.robotics.build import Mapper
from phlux.robotics.places import Gazetteer, parse

TOWNS = {
    "CA": {"santa clara": [40, 273], "san francisco": [30, 260], "sunnyvale": [41, 272], "south san francisco": [31, 262]},
    "MA": {"cambridge": [908, 167], "wilmington": [907, 160]},
    "NY": {"new york": [871, 217]},
    "DC": {"washington": [840, 260]},
    "TX": {"austin": [464, 497], "sunnyvale": [470, 430]},
    "ND": {"munich": [450, 60]},
    "HI": {"urban honolulu": [300, 560]},
}
GAZ = Gazetteer(TOWNS)


def where(text):
    found = parse(text, GAZ)
    places = [(state, town) for state, town in found.places]
    flags = [f for f in ("remote", "abroad", "vague") if getattr(found, f)]
    return places, flags, found.more


@pytest.mark.parametrize("text, places", [
    ("Santa Clara, CA", [("CA", "Santa Clara")]),
    ("US, CA, Santa Clara", [("CA", "Santa Clara")]),
    ("Santa Clara, California, United States of America", [("CA", "Santa Clara")]),
    ("Sunnyvale, California USA", [("CA", "Sunnyvale")]),
    ("Cambridge, MA USA", [("MA", "Cambridge")]),
    ("USA Wilmington, MA - HQ", [("MA", "Wilmington")]),
    ("Washington, DC", [("DC", "Washington")]),
    ("New York, NY", [("NY", "New York")]),
    ("Honolulu, HI", [("HI", "Honolulu")]),
    ("Austin, Texas, United States; South San Francisco, California, United States",
     [("TX", "Austin"), ("CA", "South San Francisco")]),
    ("San Francisco Bay Area (San Mateo) or Boston (Somerville)", [("CA", "San Francisco"), ("MA", "")]),
    ("Sunnyvale", [("CA", "Sunnyvale")]),  # a hub, though Texas has one too
])
def test_us_places(text, places):
    assert where(text)[0] == places


def test_counts_and_flags():
    assert where("Santa Clara, CA +2") == ([("CA", "Santa Clara")], [], 2)
    assert where("3 Locations") == ([], ["vague"], 3)
    assert where("Remote - US")[1] == ["remote"]
    assert where("Munich")[1] == ["abroad"]  # not Munich, North Dakota
    assert where("Munich, Germany")[1] == ["abroad"]
    assert where("東京都中央区")[1] == ["abroad"]
    assert where("Flexible - Any SpaceX Site")[1] == ["vague"]
    assert where("") == ([], [], 0)


def test_mapper_numbers_towns_and_keeps_bare_states():
    mapper = Mapper(GAZ)
    assert mapper.where("Santa Clara, CA") == [0]
    assert mapper.where("Paso Robles, CA") == ["CA"]
    assert mapper.where("Cambridge, MA USA; Remote") == [1, "remote"]
    assert mapper.where("US, CA, Santa Clara") == [0]
    assert mapper.where("Somewhere odd") == ["vague"]
    assert mapper.towns == [["Santa Clara", "CA", 40, 273], ["Cambridge", "MA", 908, 167]]


def test_projection_puts_places_in_their_insets():
    sf = geo.albers_usa(-122.42, 37.77)
    boston = geo.albers_usa(-71.06, 42.36)
    anchorage = geo.albers_usa(-149.9, 61.2)
    assert sf[0] < 100 and boston[0] > 850  # west coast left, east coast right
    assert anchorage[0] < 300 and anchorage[1] > 450  # Alaska's inset, bottom left
    assert geo.albers_usa(2.35, 48.86) is None  # Paris


def test_place_names_and_state_paths():
    assert geo.place_name("Austin city") == "austin"
    assert geo.place_name("Urban Honolulu CDP") == "urban honolulu"
    topology = {
        "transform": {"scale": [1, 1], "translate": [0, 0]},
        # Delta-encoded; the second arc carries on from where the first ended.
        "arcs": [[[0, 0], [10, 0], [0, 10], [-10, 0]], [[0, 10], [0, -10]]],
        "objects": {"states": {"geometries": [
            {"type": "Polygon", "id": "06", "arcs": [[0, 1]]},
            {"type": "Polygon", "id": "72", "arcs": [[0]]},  # Puerto Rico isn't drawn
        ]}},
    }
    assert geo.state_paths(topology) == {"CA": "M0,0L10,0L10,10L0,10L0,0Z"}


def test_committed_map_data_is_complete():
    states, places = geo.load_states(), geo.load_places()
    assert len(states) == 51 and all(d.startswith("M") for d in states.values())
    assert places["PA"]["pittsburgh"] and places["CA"]["santa clara"]
