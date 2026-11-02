"""Tests for phlux/discovery/sources.py — YC dataset and seed file (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.discovery.sources import YC_API, SeedFile, YCSource, gather


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def company(id_, name, status="Active", website="https://example.com", **extra):
    return {"id": id_, "name": name, "status": status, "website": website, "one_liner": f"{name} things",
            "tags": ["Robotics"], "batch": "Winter 2024", "all_locations": "SF", "isHiring": True,
            "url": f"https://www.ycombinator.com/companies/{name.lower()}", "former_names": [name], **extra}


LISTS = {
    YC_API.format(path="tags/robotics"): [
        company(1, "Acme", website="https://acme.com"),
        company(2, "Gone", status="Inactive"),
        company(3, "Bolt", website="https://bolt.dev", former_names=["Bolt", "Old Bolt", "Inc"]),
    ],
    YC_API.format(path="tags/hard-tech"): [company(1, "Acme", website="https://acme.com"), company(4, "Rocket")],
}


def test_yc_keeps_active_companies_once():
    source = YCSource(robotics=["tags/robotics"], adjacent=["tags/hard-tech"])
    with patch("phlux.discovery.sources.get", side_effect=lambda url: response(LISTS[url])):
        found = {c.name: c for c in source.candidates()}
    assert sorted(found) == ["Acme", "Bolt", "Rocket"]
    acme = found["Acme"]
    assert (acme.focus, acme.matched, acme.website, acme.source) == (
        "robotics", ["robotics", "hard-tech"], "https://acme.com", "yc")
    assert (acme.one_liner, acme.batch, acme.hiring, acme.yc_url) == (
        "Acme things", "Winter 2024", True, "https://www.ycombinator.com/companies/acme")
    assert found["Rocket"].focus == "adjacent"
    assert found["Bolt"].former_names == ["Old Bolt"]


def test_default_yc_lists_are_robotics_related():
    paths = [path for path, _ in YCSource().lists]
    assert "tags/robotics" in paths and "industries/manufacturing-and-robotics" in paths
    assert "tags/robotic-process-automation" not in paths  # office software, not robots


def test_seed_file(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("# Name,website\n\nAcme,https://acme.com\n\"Bolt, Inc.\",bolt.dev\nNoSite\n", encoding="utf-8")
    found = SeedFile(seeds).candidates()
    assert [(c.name, c.website, c.source) for c in found] == [
        ("Acme", "https://acme.com", "seeds"), ("Bolt, Inc.", "bolt.dev", "seeds"), ("NoSite", "", "seeds")]
    assert SeedFile(tmp_path / "missing.txt").candidates() == []


class Static:
    def __init__(self, name, candidates):
        self.name, self._candidates = name, candidates

    def candidates(self):
        return self._candidates


def test_gather_merges_a_company_listed_twice(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("ACME,https://www.acme.com/about\nZed,https://zed.io\nBolt,\n", encoding="utf-8")
    yc = Static("yc", [YCSource._candidate(company(1, "Acme", website="http://acme.com"), "robotics"),
                       YCSource._candidate(company(3, "Bolt", website="https://bolt.dev"), "robotics")])
    found = {c.name: c for c in gather([yc, SeedFile(seeds)])}
    assert sorted(found) == ["Acme", "Bolt", "Zed"]
    assert found["Acme"].source == "yc+seeds"  # same domain
    assert found["Bolt"].source == "yc+seeds"  # same name
