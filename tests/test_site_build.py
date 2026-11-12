"""Tests for phlux/site/build.py."""
import json
from datetime import date, datetime

import pytest

from phlux.models import Company
from phlux.site.build import TEMPLATE, build_payload, internship_rows, new_grad_rows, render
from phlux.site.forecast import SOON, Forecast, Opening

TODAY = date(2026, 11, 1)


class TestInternshipRows:
    def test_keeps_starred_titles_open_or_closed_lately(self):
        entries = [
            {"title": "⭐️ Perception Intern, PhD - Summer 2027", "date": "2026-10-20", "id": "x:1",
             "url": "https://jobs.example/1", "location": "Boston, MA"},
            {"title": "Senior Perception Engineer", "date": "2026-10-20"},
            {"title": "⭐️ Mechanical Engineering Co-op", "date": "N/A", "closed": "2026-10-25"},
            {"title": "⭐️ Old Intern", "date": "2026-09-30", "closed": "2026-09-01"},
            {"title": "⭐️ Backlog Intern", "date": "N/A", "closed": "N/A"},
            "⭐️ Legacy string",
        ]
        rows = internship_rows("Acme", entries, TODAY)
        assert rows == [
            {"company": "Acme", "title": "Perception Intern, PhD - Summer 2027", "url": "https://jobs.example/1",
             "location": "Boston, MA", "found": "2026-10-20", "closed": "", "season": "summer", "year": 2027,
             "degree": "phd", "field": "ml_ai", "early": ""},
            {"company": "Acme", "title": "Mechanical Engineering Co-op", "url": "", "location": "", "found": "",
             "closed": "2026-10-25", "season": "", "year": 0, "degree": "", "field": "hardware", "early": ""},
        ]


class TestNewGradRows:
    def test_keeps_unstarred_new_grad_engineering_roles(self):
        entries = [
            {"title": "Software Engineer - New Grad (2027)", "date": "2026-10-20", "url": "https://jobs.example/2",
             "location": "Austin, TX"},
            {"title": "Early Career - Mechanical Design Engineer", "date": "N/A", "closed": "2026-10-25"},
            {"title": "New Grad Robotics Engineer", "date": "2026-09-01", "closed": "2026-09-15"},  # closed long ago
            {"title": "Senior Perception Engineer", "date": "2026-10-20"},  # not new grad
            {"title": "Product Designer, New Grad", "date": "2026-10-20"},  # not engineering
            {"title": "Junior IT Support Engineer", "date": "2026-10-20"},  # support role
            {"title": "⭐️ Software Engineer Intern", "date": "2026-10-20"},  # internship
            "Legacy New Grad Engineer",
        ]
        rows = new_grad_rows("Acme", entries, TODAY)
        assert [(r["title"], r["found"], r["closed"]) for r in rows] == [
            ("Software Engineer - New Grad (2027)", "2026-10-20", ""),
            ("Early Career - Mechanical Design Engineer", "", "2026-10-25"),
        ]
        assert rows[0]["url"] == "https://jobs.example/2" and rows[0]["year"] == 2027
        assert rows[0]["field"] == "software"

    def test_description_line_lists_an_unlabeled_role(self):
        line = "Recent graduates are encouraged to apply."
        entries = [
            {"title": "Controls Engineer", "date": "2026-10-20", "early": line},
            {"title": "Senior Controls Engineer", "date": "2026-10-20", "early": line},  # senior title
            {"title": "Account Executive", "date": "2026-10-20", "early": line},  # not engineering
            {"title": "Perception Engineer", "date": "2026-10-20"},  # no line
        ]
        rows = new_grad_rows("Acme", entries, TODAY)
        assert [(r["title"], r["early"]) for r in rows] == [("Controls Engineer", line)]


class TestBuildPayload:
    def payload(self):
        storage = {
            "companies": {"Acme": [{"title": "⭐️ Robotics Intern", "date": "2026-10-30"},
                                   {"title": "Controls Engineer, Early Career", "date": "2026-10-31"}],
                          "Quant Co": []},
            "checked": {"Acme": "2026-11-01"},
        }
        companies = [
            Company("Acme", "https://job-boards.greenhouse.io/acme?keyword=intern", "@greenhouse"),
            Company("Quant Co", "https://jobs.lever.co/quant", "@lever"),
        ]
        forecasts = {"Acme": Forecast("Acme", SOON, 2027, last=Opening(2026, date(2025, 11, 20), False),
                                      expected=date(2026, 11, 20))}
        industries = {"Acme": {"robotics_tier": "core", "robotics_segment": "humanoids"},
                      "Quant Co": {"sector": "quant_finance", "robotics_tier": "none", "robotics_segment": ""}}
        icons = {"Acme": "data:image/webp;base64,AAAA"}
        now = datetime(2026, 11, 1, 17, 5)
        return build_payload(storage, companies, forecasts, industries, icons, now)

    def test_companies_carry_tagging_links_and_forecasts(self):
        acme, quant = self.payload()["companies"]
        assert acme["robotics"] is True and quant["robotics"] is False
        assert (acme["segment"], quant["segment"]) == ("humanoids", "quant_finance")
        assert acme["careers"] == "https://job-boards.greenhouse.io/acme"  # keyword search dropped
        assert acme["icon"] == "data:image/webp;base64,AAAA"
        assert acme["checked"] == "2026-11-01"
        assert acme["forecast"]["expected"] == "2026-11-20"
        assert quant["forecast"] is None
        assert acme["health"]["status"] == "ok"
        assert quant["health"] == {"status": "stale", "since": None, "detail": "never checked"}

    def test_robotics_tab_is_the_company_list_not_the_tags(self):
        storage = {"companies": {}}
        companies = [Company("Acme", "https://jobs.lever.co/acme", "@lever"),
                     Company("Quant Co", "https://jobs.lever.co/quant", "@lever")]
        industries = {"Acme": {"robotics_tier": "adjacent", "robotics_segment": "space_hardware"},
                      "Quant Co": {"sector": "quant_finance", "robotics_tier": "none", "robotics_segment": ""}}
        acme, quant = build_payload(storage, companies, {}, industries, {}, datetime(2026, 11, 1),
                                    listed=["Quant Co"])["companies"]
        assert acme["robotics"] is False and quant["robotics"] is True
        # The segment picker still groups by the tags.
        assert acme["roboticsSegment"] is True and quant["roboticsSegment"] is False
        assert (acme["segment"], quant["segment"]) == ("space_hardware", "quant_finance")

    def test_postings_are_rows_of_the_listed_fields(self):
        payload = self.payload()
        assert payload["cycle"] == 2027
        assert payload["today"] == "2026-11-01"
        [row] = payload["postings"]
        posting = dict(zip(payload["fields"], row))
        assert posting["company"] == 0
        assert posting["title"] == "Robotics Intern"

    def test_new_grad_roles_are_rows_of_the_same_fields(self):
        payload = self.payload()
        [row] = payload["newGrad"]["postings"]
        posting = dict(zip(payload["fields"], row))
        assert posting["company"] == 0
        assert posting["title"] == "Controls Engineer, Early Career"
        assert posting["found"] == "2026-10-31"
        assert payload["newGrad"]["since"] >= payload["seasonStart"]


class TestMapData:
    def test_postings_carry_where_and_the_page_gets_the_map(self):
        from phlux.site.places import Gazetteer
        storage = {"companies": {"Acme": [
            {"title": "⭐️ Robotics Intern", "date": "2026-10-30", "location": "Santa Clara, CA +1"},
            {"title": "⭐️ Controls Intern", "date": "2026-10-30", "location": "Remote"},
            {"title": "⭐️ Perception Intern", "date": "2026-10-30"},
        ]}}
        payload = build_payload(storage, [Company("Acme", "https://jobs.lever.co/acme", "@lever")], {}, {}, {},
                                datetime(2026, 11, 1, 17, 5), gazetteer=Gazetteer({"CA": {"santa clara": [40, 273]}}),
                                state_paths={"CA": "M0,0Z"})
        where = [dict(zip(payload["fields"], row))["where"] for row in payload["postings"]]
        assert where == [[0], ["remote"], []]
        assert payload["map"]["towns"] == [["Santa Clara", "CA", 40, 273]]
        assert payload["map"]["states"] == {"CA": "M0,0Z"} and payload["map"]["names"]["CA"] == "California"

    def test_no_map_without_its_data(self):
        payload = build_payload({"companies": {}}, [], {}, {}, {}, datetime(2026, 11, 1))
        assert payload["map"] is None


class TestRender:
    def test_wraps_the_body_in_a_document_with_the_data_inside(self):
        page = render({"title": "Intern </script><script>alert(1)</script>"}, "<p>__DATA__</p>")
        assert page.startswith("<!doctype html>")
        assert "<\\/script>" in page and "</script><script>" not in page
        assert "viewport-fit=cover" in page

    def test_fragment_for_artifact_previews(self):
        body = render({"a": 1}, "<p>__DATA__</p>", document=False)
        assert body == '<p>{"a":1}</p>'

    def test_refuses_nan(self):
        with pytest.raises(ValueError):
            render({"season": float("nan")}, "<p>__DATA__</p>")

    def test_template_needs_the_marker(self):
        with pytest.raises(ValueError):
            render({}, "<p>no marker</p>")

    def test_real_template_has_one_marker_and_a_title(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        assert template.count("__DATA__") == 1
        assert template.startswith("<title>Phlux</title>")
        json.loads(render({"x": 1}, template, document=False).split('id="phlux-data">')[1].split("</script>")[0])
