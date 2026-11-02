"""Tests for phlux/discovery/fingerprints.py — recognizing job boards in HTML."""
import pytest

from phlux.boards import BOARDS
from phlux.discovery.fingerprints import (
    CAREERPUCK,
    DOVER_CLIENT,
    FINGERPRINTS,
    LEADS,
    WORKABLE_ACCOUNT,
    WORKABLE_JOB,
    Hit,
    find_boards,
    find_hints,
    find_unsupported,
)

UUID = "3a4d8744-ab51-41d9-a0cf-43de316c7dca"


@pytest.mark.parametrize("html, hit", [
    # Greenhouse: embed script, embed iframe, board API in script, hosted boards.
    ('<script src="https://boards.greenhouse.io/embed/job_board/js?for=acmerobotics"></script>',
     Hit("greenhouse", "acmerobotics", "https://job-boards.greenhouse.io/acmerobotics")),
    ('<iframe src="https://job-boards.greenhouse.io/embed/job_board?b=x&amp;for=acme">',
     Hit("greenhouse", "acme", "https://job-boards.greenhouse.io/acme")),
    ('fetch("https://boards-api.greenhouse.io/v1/boards/acme/jobs")',
     Hit("greenhouse", "acme", "https://job-boards.greenhouse.io/acme")),
    ('<a href="https://job-boards.greenhouse.io/acme/jobs/123">',
     Hit("greenhouse", "acme", "https://job-boards.greenhouse.io/acme")),
    ('<a href="https://boards.greenhouse.io/acme">',
     Hit("greenhouse", "acme", "https://job-boards.greenhouse.io/acme")),
    ('<a href="https://jobs.lever.co/acme-inc/8d2c">', Hit("lever", "acme-inc", "https://jobs.lever.co/acme-inc")),
    ('<a href="https://jobs.eu.lever.co/acme">', Hit("lever", "acme", "https://jobs.eu.lever.co/acme")),
    ('{"url":"https:\\/\\/jobs.ashbyhq.com\\/acme\\/embed?version=2"}',
     Hit("ashby", "acme", "https://jobs.ashbyhq.com/acme")),
    ('<a href="https://jobs.ashbyhq.com/Acme%20Inc">', Hit("ashby", "Acme%20Inc", "https://jobs.ashbyhq.com/Acme%20Inc")),
    ('<a href="https://apply.workable.com/realtime-robotics/">',
     Hit("workable", "realtime-robotics", "https://apply.workable.com/realtime-robotics/")),
    ('<a href="https://acme.workable.com">', Hit("workable", "acme", "https://apply.workable.com/acme/")),
    ('<a href="https://ats.rippling.com/en-GB/overland-ai/jobs">',
     Hit("rippling", "overland-ai", "https://ats.rippling.com/overland-ai/jobs")),
    ('<iframe src="https://mujin.bamboohr.com/careers">', Hit("bamboohr", "mujin", "https://mujin.bamboohr.com/careers")),
    ('<a href="https://app.dover.com/jobs/scytherobotics">',
     Hit("dover", "scytherobotics", "https://app.dover.com/jobs/scytherobotics")),
    (f'<a href="https://app.dover.com/acme/careers/{UUID}">', Hit("dover", "acme", f"https://app.dover.com/acme/careers/{UUID}")),
    ('<a href="https://jobs.gem.com/chef-robotics">', Hit("gem", "chef-robotics", "https://jobs.gem.com/chef-robotics")),
    ('<a href="https://misorobotics.applytojob.com/apply/abc/Engineer">',
     Hit("jazzhr", "misorobotics", "https://misorobotics.applytojob.com/apply")),
    ('<a href="https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/x_JR1">',
     Hit("workday", "nvidia", "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")),
    ('<a href="https://wd1.myworkdaysite.com/recruiting/acme/External">',
     Hit("workday", "acme", "https://wd1.myworkdaysite.com/recruiting/acme/External")),
    ('<a href="https://paypal.eightfold.ai/careers?query=intern">',
     Hit("eightfold", "paypal", "https://paypal.eightfold.ai/careers")),
    (f'<a href="https://recruiting.paylocity.com/Recruiting/Jobs/All/{UUID}/Beep-Inc">',
     Hit("paylocity", UUID, f"https://recruiting.paylocity.com/recruiting/jobs/All/{UUID}/Beep-Inc")),
    (f'<a href="https://jobs.gusto.com/boards/anyware-robotics-{UUID}">',
     Hit("gusto", f"anyware-robotics-{UUID}", f"https://jobs.gusto.com/boards/anyware-robotics-{UUID}")),
    ('<a href="https://careers.kula.ai/sanctuary-ai">', Hit("kula", "sanctuary-ai", "https://careers.kula.ai/sanctuary-ai")),
    ('<a href="https://jobs.smartrecruiters.com/BoschGroup/123">',
     Hit("smartrecruiters", "BoschGroup", "https://careers.smartrecruiters.com/BoschGroup")),
    ('<a href="https://careers-jobyaviation.icims.com/jobs/search?ss=1">',
     Hit("icims", "jobyaviation", "https://careers-jobyaviation.icims.com/jobs/search?ss=1")),
    ('<a href="https://www.paycomonline.net/v4/ats/web.php/portal/32B3464F/career-page">',
     Hit("paycom", "32B3464F", "https://www.paycomonline.net/v4/ats/web.php/portal/32B3464F/career-page")),
    ('<a href="https://recruitingbypaycor.com/career/CareerHome.action?clientId=8a7883d0&amp;m=t">',
     Hit("paycor", "8a7883d0", "https://recruitingbypaycor.com/career/CareerHome.action?clientId=8a7883d0")),
    ('<a href="https://phf.tbe.taleo.net/phf01/ats/careers/v2/searchResults?org=ACME&cws=47">',
     Hit("taleo", "ACME", "https://phf.tbe.taleo.net/phf01/ats/careers/v2/searchResults?org=ACME&cws=47")),
    ('<a href="https://efds.fa.em5.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs">',
     Hit("oraclehcm", "efds", "https://efds.fa.em5.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs")),
])
def test_fingerprints(html, hit):
    assert find_boards(html) == [hit]


@pytest.mark.parametrize("html, lead", [
    ('<a href="https://app.careerpuck.com/job-board/welchs">', Hit(CAREERPUCK, "welchs", "")),
    ('<a href="https://welchs.careerpuck.com/page/welchs-careers">', Hit(CAREERPUCK, "welchs", "")),
    ("<script>whr_embed(456789, {detail: 'titles'});</script>", Hit(WORKABLE_ACCOUNT, "456789", "")),
    ('<a href="https://apply.workable.com/j/EF5F79EB04">', Hit(WORKABLE_JOB, "EF5F79EB04", "")),
    (f'<a href="https://app.dover.com/apply/{UUID}/8f9c3334-4d5b-480e-94a2-7bbfa1f4f2ab/?rs=1">',
     Hit(DOVER_CLIENT, UUID, "")),
])
def test_leads_that_need_resolving(html, lead):
    assert find_boards(html) == [lead]


def test_every_board_named_is_one_phlux_reads():
    assert {fp.board for fp in FINGERPRINTS} - set(LEADS) <= set(BOARDS)


def test_teamio_widget_page_is_its_own_link():
    html = '<script>window.__LMC_CAREER_WIDGET__ = {"apiKey": "k", "widgetId": "w"}</script>'
    assert find_boards(html, "https://brightpick.ai/careers/") == [
        Hit("teamio", "brightpick", "https://brightpick.ai/careers/")]


def test_vendor_pages_are_not_boards():
    html = ('<a href="https://www.greenhouse.io">Powered by Greenhouse</a>'
            '<a href="https://www.bamboohr.com/">BambooHR</a><a href="https://apply.workable.com/j/">x</a>'
            '<script src="https://boards.greenhouse.io/embed/job_board/js?for=\' + BOARD"></script>')
    assert find_boards(html) == []


def test_one_hit_per_account_in_page_order():
    html = ('<a href="https://jobs.lever.co/acme">jobs</a>'
            '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>'
            '<a href="https://job-boards.greenhouse.io/acme/jobs/1">job</a>'
            '<a href="https://jobs.lever.co/Acme/123">job</a>')
    assert [h.board for h in find_boards(html)] == ["lever", "greenhouse"]


def test_unsupported_systems():
    html = '<a href="https://jobs.jobvite.com/acme">Jobs</a><a href="https://acme.recruitee.com/">x</a>'
    assert find_unsupported(html) == ["Jobvite", "Recruitee"]
    assert find_unsupported('<a href="https://job-boards.eu.greenhouse.io/acme">') == ["Greenhouse EU"]
    waas = '<a href="https://www.ycombinator.com/companies/acme/jobs">x</a><script src="https://www.workatastartup.com/embed/script.js">'
    assert find_unsupported(waas) == ["YC Work at a Startup"]
    assert find_boards('<a href="https://job-boards.eu.greenhouse.io/acme">') == []


def test_hints_name_a_board_without_a_slug():
    html = "<script>const s = 'https://boards.greenhouse.io/embed/job_board/js?for=' + BOARD;</script>"
    assert find_hints(html) == {"greenhouse": set()}
    links = '<a href="/careers/job?gh_jid=4957366008">x</a><a href="/careers/job?gh_jid=12">y</a>'
    assert find_hints(links) == {"greenhouse": {"4957366008", "12"}}
    ashby = '<a href="/jobs?ashby_jid=a5cb058a-681c-4f72-8b4d-1429b154a182">x</a>'
    assert find_hints(ashby) == {"ashby": {"a5cb058a-681c-4f72-8b4d-1429b154a182"}}
    assert find_hints("<p>no boards here</p>") == {}
