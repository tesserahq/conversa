"""Tests for app.main helpers."""

from app.main import parse_cors_allowed_origins


def test_parse_cors_allowed_origins_none_means_no_origins():
    assert parse_cors_allowed_origins(None) == []


def test_parse_cors_allowed_origins_empty_string_means_no_origins():
    assert parse_cors_allowed_origins("") == []


def test_parse_cors_allowed_origins_splits_and_strips():
    raw = "https://app.example.com, https://staging.example.com ,https://other.com"
    assert parse_cors_allowed_origins(raw) == [
        "https://app.example.com",
        "https://staging.example.com",
        "https://other.com",
    ]


def test_parse_cors_allowed_origins_drops_blank_entries():
    assert parse_cors_allowed_origins("https://a.com,,  ,https://b.com") == [
        "https://a.com",
        "https://b.com",
    ]


def test_parse_cors_allowed_origins_single_origin():
    assert parse_cors_allowed_origins("https://a.com") == ["https://a.com"]
