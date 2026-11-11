"""Tests for phlux/config.py."""
import json

import pytest

from phlux.config import load_config, load_email_config


def test_load_config_returns_dict(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"EMAIL": {}}', encoding="utf-8")
    result = load_config(cfg)
    assert isinstance(result, dict)


def test_load_config_returns_expected_keys(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"EMAIL": {"to": "a@b.com"}}),
        encoding="utf-8",
    )
    result = load_config(cfg)
    assert "EMAIL" in result


def test_load_config_accepts_string_path(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"key": "value"}', encoding="utf-8")
    result = load_config(str(cfg))
    assert result == {"key": "value"}


def test_load_config_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.json")


def test_load_config_raises_for_invalid_json(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("not valid json {{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_config(cfg)


# ── all_internships_bcc ───────────────────────────────────────────────────────

def _email_cfg(tmp_path, email):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"EMAIL": email}), encoding="utf-8")
    return load_email_config(cfg)


def test_all_internships_bcc_defaults_to_nobody(tmp_path):
    assert _email_cfg(tmp_path, {})["all_internships_bcc"] == []


def test_all_internships_bcc_accepts_a_comma_separated_string(tmp_path):
    cfg = _email_cfg(tmp_path, {"all_internships_bcc": "a@x.com, b@x.com,"})
    assert cfg["all_internships_bcc"] == ["a@x.com", "b@x.com"]


def test_disabling_internship_bcc_leaves_all_internships_bcc(tmp_path):
    cfg = _email_cfg(tmp_path, {"internship_bcc_enabled": False, "internship_bcc": ["a@x.com"],
                                "all_internships_bcc": ["b@x.com"]})
    assert (cfg["internship_bcc"], cfg["all_internships_bcc"]) == ([], ["b@x.com"])

