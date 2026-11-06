"""Tests for phlux/early_career.py."""
import pytest

from phlux.early_career import early_career_line, early_career_lines, html_text


@pytest.mark.parametrize("description, expected", [
    ("You will build robots. Recent graduates are encouraged to apply. Python required.",
     "Recent graduates are encouraged to apply."),
    ("Requirements:\n- BS in CS\n- 0-2 years of experience in software engineering\n- C++",
     "0-2 years of experience in software engineering"),
    ("This role is ideal for early-career engineers. 1+ years of experience with ROS.",
     "This role is ideal for early-career engineers."),
])
def test_qualifying_lines(description, expected):
    assert early_career_line(description) == expected


@pytest.mark.parametrize("description", [
    "This is not an entry-level role. You will lead the team.",
    "We are hiring our first new graduate class! For this role: 5+ years of experience in C++.",
    "1+ years of experience in embedded software.",
    "3-5 years of professional experience building perception systems.",
    "",
])
def test_lines_that_do_not_qualify(description):
    assert early_career_line(description) == ""


def test_boilerplate_shared_with_senior_postings_does_not_count():
    blurb = "We hire across levels, from entry level engineers to staff engineers."
    board = [
        ("a:1", "Controls Engineer", "Build controllers. " + blurb),
        ("a:2", "Senior Controls Engineer", "Lead controllers. " + blurb),
        ("a:3", "Robotics Engineer", "Build robots. Recent graduates are encouraged to apply."),
        ("a:4", "Staff Robotics Engineer", "Recent graduates are encouraged to apply."),  # senior: never listed
    ]
    assert early_career_lines(board) == {}  # a:3's line is also on a senior posting
    assert early_career_lines(board[:3]) == {"a:3": "Recent graduates are encouraged to apply."}


def test_long_lines_are_trimmed():
    line = early_career_line("Ideal for recent graduates " + "who love robots " * 30 + ".")
    assert len(line) <= 220 and line.endswith("…")


def test_html_text_reads_twice_escaped_markup():
    assert html_text("&lt;p&gt;Recent graduates &amp;amp; interns&lt;/p&gt;") == "Recent graduates & interns"
