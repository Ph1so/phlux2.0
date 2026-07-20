"""Tests for phlux/config.py."""
import json

import pytest

from phlux.config import load_config


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
