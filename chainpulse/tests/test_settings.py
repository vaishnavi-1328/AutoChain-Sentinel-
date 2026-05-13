"""Settings loads + CORS list parses."""
from __future__ import annotations

from chainpulse.backend.config.settings import Settings


def test_cors_list_parses():
    s = Settings(CORS_ORIGINS="http://a.com, http://b.com ,http://c.com")
    assert s.cors_origins_list == ["http://a.com", "http://b.com", "http://c.com"]


def test_defaults_present():
    s = Settings()
    assert s.llm_backend == "anthropic"
    assert s.app_env == "development"
