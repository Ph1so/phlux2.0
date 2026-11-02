"""Tests for phlux/discovery crawl.py, identify.py and detect.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from phlux.discovery.crawl import Crawler, site_name, wall_of
from phlux.discovery.detect import FILTER_ABOVE, Detection, detect
from phlux.discovery.fingerprints import Hit
from phlux.discovery.identify import (
    ASHBY_GRAPHQL,
    CONFIRMED,
    NAME_ONLY,
    REJECTED,
    Identity,
    ashby_identity,
    corroborate,
    greenhouse_identity,
    batch_code,
    lever_identity,
    resolve_careerpuck,
    resolve_lead,
    resolve_workable_account,
)
from phlux.models import Posting

GH = "https://boards-api.greenhouse.io/v1/boards/"
JOBS = "/jobs?content=true"


def response(body="", status=200, url="", headers=None, history=(), payload=None):
    mock = MagicMock()
    mock.status_code = status
    mock.text = body
    mock.url = url
    mock.headers = headers if headers is not None else {"Content-Type": "text/html; charset=utf-8"}
    mock.history = [MagicMock(url=u) for u in history]
    mock.json.return_value = payload
    return mock


def api(payload, status=200):
    return response(json.dumps(payload), status, payload=payload, headers={"Content-Type": "application/json"})


class FakeWeb:
    """Answers requests from tables; an unknown URL is a 404, like a board that doesn't exist.

    ``orgs`` answers Ashby's organization query by slug; ``boards`` answers
    ``board_postings`` by (board, link) with titles, or an exception to raise.
    """

    def __init__(self):
        self.routes = {}
        self.orgs = {}
        self.boards = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        answer = self.routes.get(url, response("Not Found", 404))
        if isinstance(answer, Exception):
            raise answer
        answer.url = answer.url or url
        if answer.status_code >= 400:
            raise requests.HTTPError(f"{answer.status_code} for {url}", response=answer)
        return answer

    def post(self, url, json=None, **kwargs):
        assert url == ASHBY_GRAPHQL
        slug = json["variables"]["organizationHostedJobsPageName"]
        self.calls.append(f"ashby-org:{slug}")
        return api({"data": {"organization": self.orgs.get(slug)}})

    def board_postings(self, board, link, arg=""):
        self.calls.append(f"read:{board}:{link}")
        titles = self.boards.get((board, link))
        if titles is None:
            raise requests.HTTPError(f"404 Client Error for {link}")
        if isinstance(titles, Exception):
            raise titles
        return [Posting(f"{board}:{i}", t) for i, t in enumerate(titles)]


@pytest.fixture
def web():
    fake = FakeWeb()
    with patch("phlux.discovery.crawl.get", fake.get), patch("phlux.discovery.identify.get", fake.get), \
            patch("phlux.discovery.identify.post", fake.post), \
            patch("phlux.discovery.detect.board_postings", fake.board_postings):
        yield fake


# ── Crawl ─────────────────────────────────────────────────────────────────────

HOME = """<html><body>
<a href="/about">About</a><a href="mailto:hi@acme.com">Mail</a>
<a href="https://other.com/careers">Their careers</a>
<a href="/careers">Careers</a><a href="/blog/we-are-hiring">We're hiring!</a>
</body></html>"""


def test_crawl_reads_career_links_before_guessing(web):
    web.routes["https://acme.com/"] = response(HOME)
    web.routes["https://acme.com/careers"] = response("<p>Join us</p>")
    crawler = Crawler("acme.com", max_pages=4)
    assert [page.url for page in crawler.pages()] == ["https://acme.com/", "https://acme.com/careers"]
    # Links that say careers first (best first), then the usual places; never other sites.
    assert web.calls == ["https://acme.com/", "https://acme.com/careers", "https://acme.com/blog/we-are-hiring",
                         "https://acme.com/jobs"]


def test_crawl_stops_at_the_page_cap(web):
    web.routes["https://acme.com/"] = response(HOME)
    crawler = Crawler("https://acme.com", max_pages=2)
    list(crawler.pages())
    assert len(web.calls) == 2


def test_crawl_stops_at_a_bot_wall(web):
    challenge = "<html><title>Just a moment...</title><script src='/cdn-cgi/challenge-platform/x'></script></html>"
    web.routes["https://acme.com/"] = response(challenge, status=403)
    crawler = Crawler("https://acme.com")
    assert list(crawler.pages()) == []
    assert crawler.blocked == "Cloudflare bot wall on https://acme.com/"
    assert web.calls == ["https://acme.com/"]


def test_crawl_reports_an_unreachable_home_page(web):
    web.routes["https://acme.com/"] = requests.ConnectionError("no such host")
    crawler = Crawler("https://acme.com")
    assert list(crawler.pages()) == []
    assert crawler.error == "https://acme.com/ unreachable (ConnectionError)"


def test_crawl_follows_a_home_page_that_moved_domain(web):
    web.routes["https://acme.com/"] = response('<a href="https://www.acme.ai/jobs">Jobs</a>',
                                               url="https://www.acme.ai/", history=["https://acme.com/"])
    web.routes["https://www.acme.ai/jobs"] = response("<p>jobs</p>")
    crawler = Crawler("https://acme.com", max_pages=2)
    assert [p.url for p in crawler.pages()] == ["https://www.acme.ai/", "https://www.acme.ai/jobs"]
    assert crawler.domains == {"acme.com", "acme.ai"}


def test_wall_of():
    assert wall_of(200, "<html>fine</html>") == ""
    assert wall_of(403, '<div id="px-captcha"></div>') == "PerimeterX"
    assert wall_of(404, "<html>Not found</html>") == ""


def test_site_name():
    assert site_name('<meta property="og:site_name" content="Relativity Space">') == "Relativity Space"
    assert site_name("<title>Acme Robotics | Robots for farms</title>") == "Acme Robotics"
    assert site_name("<p>no title</p>") == ""


# ── Whose board is it ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("identity, verdict, why", [
    (Identity(job_ids={"7"}), CONFIRMED, "a job linked from the company's site is on it"),
    (Identity(name="Something Else", mentions={"acme.com"}), CONFIRMED, "it names acme.com"),
    (Identity(name="Acme", sites={"acme-boats.com"}), REJECTED, "it belongs to acme-boats.com"),
    (Identity(mentions={"acmecloud.com"}), REJECTED, "it names acmecloud.com, not acme.com"),
    (Identity(name="Acme", text="Acme (YC S24) builds farm robots."), CONFIRMED, "it says YC S24"),
    (Identity(name="Acme Robotics", text="Acme (YC W21) builds farm robots."), NAME_ONLY,
     "only its name, 'Acme Robotics', matches"),
    (Identity(name="Acme Robotics, Inc."), NAME_ONLY, "only its name, 'Acme Robotics, Inc.', matches"),
    (Identity(name="Acme Pharmacy"), REJECTED, "it is 'Acme Pharmacy'"),
    (Identity(text="Acme Robotics builds robots for farms."), NAME_ONLY,
     "only the company's name appears in its postings"),
    (Identity(text="We build robots."), REJECTED, "nothing on it names the company"),
])
def test_corroborate(identity, verdict, why):
    job_ids = {"7"} if identity.job_ids else ()
    assert corroborate(identity, "Acme Robotics", {"acme.com"}, job_ids, batch="Summer 2024") == (verdict, why)


def test_batch_code():
    assert [batch_code(b) for b in ("Summer 2024", "Winter 2016", "Spring 2025", "Fall 2026", "IK12", "")] == [
        "S24", "W16", "X25", "F26", "", ""]


def test_greenhouse_identity(web):
    web.routes[GH + "relativity"] = api({"name": "Relativity Space", "content": "<p>See relativityspace.com</p>"})
    web.routes[GH + "relativity" + JOBS] = api({"jobs": [
        {"id": 1, "absolute_url": "https://boards.greenhouse.io/relativity/jobs/1",
         "content": "&lt;p&gt;Questions? careers@relativity-help.com&lt;/p&gt;"},
        {"id": 2, "absolute_url": "https://www.relativityspace.com/careers?gh_jid=2"},
    ]})
    identity = greenhouse_identity("relativity")
    assert identity.name == "Relativity Space"
    assert identity.sites == {"relativityspace.com"}
    assert {"relativityspace.com", "relativity-help.com"} <= identity.mentions
    assert "<p>Questions?" in identity.text
    assert identity.job_ids == {"1", "2"}
    assert greenhouse_identity("nobody") is None


def test_ashby_identity_reads_the_organization(web):
    web.orgs["1x"] = {"name": "1X", "publicWebsite": "https://www.1x.tech/"}
    web.routes["https://api.ashbyhq.com/posting-api/job-board/1x"] = api({"jobs": [{"id": "a", "descriptionPlain": "x"}]})
    identity = ashby_identity("1x")
    assert (identity.name, identity.sites, identity.job_ids) == ("1X", {"1x.tech"}, {"a"})
    assert ashby_identity("nobody") is None
    assert "ashby-org:nobody" not in web.calls  # GraphQL is only asked about boards that exist


def test_lever_identity_has_only_text(web):
    web.routes["https://api.lever.co/v0/postings/acme"] = api(
        [{"id": "p1", "descriptionPlain": "Join Acme at acme.com", "additionalPlain": ""}])
    identity = lever_identity("acme")
    assert identity.name == "" and identity.mentions == {"acme.com"} and identity.job_ids == {"p1"}
    assert lever_identity("nobody") is None


def careerpuck(platform="greenhouse", token="welchsinc", jobs=1):
    job = {"atsSourceId": "4957366008", "jobBoard": {"permalink": "welchs", "atsSourceId": token}}
    return api({"atsSourcePlatform": platform, "jobs": [job] * jobs,
                "employerProfile": {"name": "Welch's", "emailDomain": "welchs.com"}})


def test_careerpuck_names_the_greenhouse_token_it_mirrors(web):
    web.routes["https://api.careerpuck.com/v1/public/job-boards/welchs"] = careerpuck()
    assert resolve_careerpuck("welchs") == (
        Hit("greenhouse", "welchsinc", "https://job-boards.greenhouse.io/welchsinc"), "")


def test_careerpuck_without_a_token_is_matched_by_job_id(web):
    web.routes["https://api.careerpuck.com/v1/public/job-boards/welchs"] = careerpuck(token=None)
    web.routes[GH + "welchsinc"] = api({"name": "Welch’s "})
    web.routes[GH + "welchsinc" + JOBS] = api({"jobs": [{"id": 4957366008, "absolute_url": ""}]})
    hit, _ = resolve_careerpuck("welchs")
    assert hit == Hit("greenhouse", "welchsinc", "https://job-boards.greenhouse.io/welchsinc")


def test_careerpuck_on_a_system_phlux_cannot_read(web):
    web.routes["https://api.careerpuck.com/v1/public/job-boards/acme"] = careerpuck(platform="jobvite", token="x")
    assert resolve_careerpuck("acme") == (None, "CareerPuck board 'acme' mirrors jobvite, which phlux cannot read")


def test_dover_apply_link_resolves_to_the_board_slug(web):
    client = "1245667f-ffd9-49a8-a2b5-5ae49535a7b4"
    web.routes[f"https://app.dover.com/api/v1/careers-page/{client}"] = api({"id": client, "slug": "seabound"})
    assert resolve_lead(Hit("dover-client", client, "")) == (
        Hit("dover", "seabound", "https://app.dover.com/jobs/seabound"), "")
    assert resolve_lead(Hit("dover-client", "0" * 8 + client[8:], ""))[0] is None


def test_workable_embed_resolves_through_a_job_link(web):
    web.routes["https://apply.workable.com/api/v1/widget/accounts/249892"] = api(
        {"name": "pony.ai", "jobs": [{"shortcode": "EF5F79EB04"}]})
    web.routes["https://apply.workable.com/j/EF5F79EB04"] = response(
        status=301, headers={"Location": "https://apply.workable.com/pony-dot-ai/j/EF5F79EB04"})
    assert resolve_workable_account("249892") == (
        Hit("workable", "pony-dot-ai", "https://apply.workable.com/pony-dot-ai/"), "")


def test_workable_embed_without_jobs_matches_the_account_id(web):
    web.routes["https://apply.workable.com/api/v1/widget/accounts/77"] = api({"name": "Realtime Robotics", "jobs": []})
    web.routes["https://apply.workable.com/api/v1/accounts/realtime-robotics"] = api({"id": 77})
    hit, _ = resolve_workable_account("77")
    assert hit == Hit("workable", "realtime-robotics", "https://apply.workable.com/realtime-robotics/")


# ── Detection ─────────────────────────────────────────────────────────────────


def test_board_linked_from_the_careers_page(web):
    web.routes["https://acme.com/"] = response('<a href="/careers">Careers</a>')
    web.routes["https://acme.com/careers"] = response('<a href="https://jobs.ashbyhq.com/acme">Open roles</a>')
    web.boards[("ashby", "https://jobs.ashbyhq.com/acme")] = [
        "Robotics Software Intern", "Mechanical Engineer", "Internal Tools Engineer", "Controls Co-op"]
    found = detect("Acme Robotics", "https://acme.com")
    assert (found.board, found.slug, found.link) == ("ashby", "acme", "https://jobs.ashbyhq.com/acme")
    assert (found.postings, found.internships) == (4, 2)
    assert found.internship_titles == ["Robotics Software Intern", "Controls Co-op"]
    assert found.evidence == "linked from https://acme.com/careers"
    assert found.row("Acme Robotics, Inc.") == "Acme Robotics,https://jobs.ashbyhq.com/acme,@ashby"
    assert found.pages == 2


def test_a_board_url_needs_no_crawl(web):
    web.boards[("lever", "https://jobs.lever.co/acme")] = ["Intern"]
    found = detect("Acme", "https://jobs.lever.co/acme/")
    assert found.board == "lever" and found.pages == 0
    assert web.calls == ["read:lever:https://jobs.lever.co/acme"]


def test_careerpuck_board_becomes_its_greenhouse_row(web):
    web.routes["https://www.welchs.com/"] = response("<p>Juice</p>")
    web.routes["https://www.welchs.com/careers"] = response(
        "<div id=app></div>", url="https://welchs.careerpuck.com/page/welchs-careers",
        history=["https://www.welchs.com/careers"])
    web.routes["https://api.careerpuck.com/v1/public/job-boards/welchs"] = careerpuck()
    web.boards[("greenhouse", "https://job-boards.greenhouse.io/welchsinc")] = ["Brand Manager"]
    found = detect("Welch's", "https://www.welchs.com")
    assert found.row("Welch's") == "Welch's,https://job-boards.greenhouse.io/welchsinc,@greenhouse"
    assert found.evidence == "careerpuck 'welchs' reads from it; linked from https://www.welchs.com/careers"


def test_a_gone_bamboohr_account_is_not_a_board(web):
    web.routes["https://richtech.com/"] = response('<a href="https://richtech.bamboohr.com/careers">Jobs</a>')
    web.boards[("bamboohr", "https://richtech.bamboohr.com/careers")] = RuntimeError(
        "BambooHR board 'richtech' is gone (redirects to https://www.bamboohr.com/)")
    found = detect("RichTech Robotics", "https://richtech.com")
    assert not found.found
    assert found.reason == ("bamboohr 'richtech' could not be read: "
                            "BambooHR board 'richtech' is gone (redirects to https://www.bamboohr.com/)")


def test_a_guessed_slug_is_kept_when_the_board_names_the_company_site(web):
    web.routes["https://acmerobotics.com/"] = response("<p>We build robots.</p>")
    web.routes[GH + "acmerobotics"] = api({"name": "ACME", "content": "<p>Visit https://acmerobotics.com</p>"})
    web.routes[GH + "acmerobotics" + JOBS] = api({"jobs": []})
    web.boards[("greenhouse", "https://job-boards.greenhouse.io/acmerobotics")] = ["Engineer"]
    found = detect("Acme Robotics", "https://acmerobotics.com")
    assert found.link == "https://job-boards.greenhouse.io/acmerobotics"
    assert found.evidence == "guessed greenhouse slug 'acmerobotics'; it names acmerobotics.com"


def test_a_same_name_board_of_another_company_is_rejected(web):
    # Navier the boat maker is navierboat.com; Greenhouse "navier" belongs to navier.com.
    web.routes["https://navierboat.com/"] = response("<p>Hydrofoil boats</p>")
    web.routes[GH + "navier"] = api({"name": "Navier", "content": ""})
    web.routes[GH + "navier" + JOBS] = api({"jobs": [{"id": 1, "absolute_url": "https://www.navier.com/careers?gh_jid=1"}]})
    web.orgs["navier"] = {"name": "Navier", "publicWebsite": "https://navier.ai"}
    web.routes["https://api.ashbyhq.com/posting-api/job-board/navier"] = api({"jobs": []})
    found = detect("Navier", "https://navierboat.com")
    assert not found.found
    assert "guessed greenhouse 'navier' rejected: it belongs to navier.com" in found.notes
    assert "guessed ashby 'navier' rejected: it belongs to navier.ai" in found.notes
    assert not any(call.startswith("read:") for call in web.calls)


def test_a_board_matching_only_by_name_is_kept_unverified(web):
    # Greenhouse "preload" is a tank builder; nothing on it says so, or says it is Preload at preload.ai.
    web.routes["https://preload.ai/"] = response("<p>Sensorimotor context for physical AI</p>")
    web.routes[GH + "preload"] = api({"name": "Preload", "content": ""})
    web.routes[GH + "preload" + JOBS] = api({"jobs": [{"id": 1, "absolute_url": "", "content": "Drafter"}]})
    web.boards[("greenhouse", "https://job-boards.greenhouse.io/preload")] = ["Drafter"]
    found = detect("Preload", "https://preload.ai")
    assert found.found and not found.verified
    assert found.evidence == "guessed greenhouse slug 'preload'; only its name, 'Preload', matches"


def test_a_confirmed_guess_beats_a_name_only_one(web):
    web.routes["https://spaceium.com/"] = response("<p>In-space refueling</p>")
    web.routes[GH + "spaceium"] = api({"name": "Spaceium", "content": ""})
    web.routes[GH + "spaceium" + JOBS] = api({"jobs": []})
    web.orgs["spaceium"] = {"name": "Spaceium", "publicWebsite": None}
    web.routes["https://api.ashbyhq.com/posting-api/job-board/spaceium"] = api(
        {"jobs": [{"id": "a", "descriptionPlain": "Spaceium (YC S24) refuels spacecraft."}]})
    web.boards[("greenhouse", "https://job-boards.greenhouse.io/spaceium")] = ["Engineer"]
    web.boards[("ashby", "https://jobs.ashbyhq.com/spaceium")] = ["Electrical Intern (Fall 26)"]
    found = detect("Spaceium Inc", "https://spaceium.com", batch="Summer 2024")
    assert (found.board, found.verified) == ("ashby", True)
    assert found.evidence == "guessed ashby slug 'spaceium'; it says YC S24"


def test_a_job_id_on_the_site_proves_a_guessed_slug(web):
    web.routes["https://acme.com/"] = response('<a href="/careers">Careers</a>')
    web.routes["https://acme.com/careers"] = response('<a href="/careers/job?gh_jid=555">Robotics Intern</a>')
    web.routes[GH + "acmeinc"] = api({"name": "Totally Different Name"})
    web.routes[GH + "acmeinc" + JOBS] = api({"jobs": [{"id": 555, "absolute_url": "https://acme.com/careers/job?gh_jid=555"}]})
    web.boards[("greenhouse", "https://job-boards.greenhouse.io/acmeinc")] = ["Robotics Intern"]
    found = detect("Acme", "https://acme.com")
    assert found.link == "https://job-boards.greenhouse.io/acmeinc"
    assert "a job linked from the company's site is on it" in found.evidence
    # The hint keeps the guesses on Greenhouse.
    assert not any(c.startswith("ashby-org:") or "lever" in c for c in web.calls)


def test_a_blocked_site_is_reported_not_worked_around(web):
    web.routes["https://acme.com/"] = response("<script src='https://captcha-delivery.com/c.js'></script>", 403)
    found = detect("Acme", "https://acme.com")
    assert found.reason == "site blocked: DataDome bot wall on https://acme.com/"
    assert [c for c in web.calls if "acme.com/" in c and "api" not in c] == ["https://acme.com/"]


def test_an_unsupported_job_system_is_the_reason(web):
    web.routes["https://acme.com/"] = response('<a href="https://jobs.jobvite.com/acme">Careers</a>')
    found = detect("Acme", "https://acme.com")
    assert found.reason == "uses Jobvite, which phlux has no reader for"


def test_a_board_with_postings_beats_an_empty_one(web):
    web.routes["https://acme.com/"] = response('<a href="https://jobs.lever.co/acme-old">Jobs</a><a href="/careers">Careers</a>')
    web.routes["https://acme.com/careers"] = response('<a href="https://jobs.ashbyhq.com/acme">Open roles</a>')
    web.boards[("lever", "https://jobs.lever.co/acme-old")] = []
    web.boards[("ashby", "https://jobs.ashbyhq.com/acme")] = ["Engineer"]
    assert detect("Acme", "https://acme.com").board == "ashby"


def test_no_website_and_no_board_by_name(web):
    found = detect("Mantle", "")
    assert found.reason == "no website, and no board found under its name"


def test_rows_quote_names_and_filter_big_boards():
    small = Detection(board="lever", link="https://jobs.lever.co/acme", postings=FILTER_ABOVE)
    big = Detection(board="lever", link="https://jobs.lever.co/acme", postings=FILTER_ABOVE + 1)
    assert small.row("Acme, Robots") == '"Acme, Robots",https://jobs.lever.co/acme,@lever'
    assert big.row("Acme") == "Acme,https://jobs.lever.co/acme,@lever->FILTER:intern"
