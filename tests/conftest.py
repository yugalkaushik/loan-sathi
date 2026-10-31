"""Test configuration.

**The test suite must never spend Sarvam or Anthropic credits.**

`app.config` reads `.env`, so once a real `SARVAM_API_KEY` is present every narrated endpoint
would synthesise speech for real during `pytest`, and the voice-endpoint test would upload audio
to Sarvam. A dozen lines of TTS per run, every run, against a limited hackathon allowance.

The fixture below blanks the credentials on the live settings object before any test runs.
`app.voice._client()` and `app.narrate.polish()` both read `settings` at call time rather than at
import time, so this holds regardless of import order, and `voice.speak()` returns `None` the
moment it sees an empty key.
"""

from __future__ import annotations

import pytest

from app.config import settings


@pytest.fixture(autouse=True, scope="session")
def _never_spend_credits():
    """Blank every credential for the whole session. Restored afterwards."""
    saved = (
        settings.sarvam_api_key,
        settings.anthropic_api_key,
        settings.ls_narrator,
        settings.ls_open_qa,
    )

    settings.sarvam_api_key = ""
    settings.anthropic_api_key = ""
    settings.ls_narrator = "template"
    # Pinned off so the suite behaves the same whatever .env happens to say. Tests that want
    # it on turn it on with monkeypatch and a stubbed client.
    settings.ls_open_qa = False

    yield

    (
        settings.sarvam_api_key,
        settings.anthropic_api_key,
        settings.ls_narrator,
        settings.ls_open_qa,
    ) = saved


@pytest.fixture(autouse=True)
def _assert_no_audio_was_billed(tmp_path_factory):
    """Fail loudly if a test ever manages to render audio."""
    before = {p.name for p in settings.audio_dir.glob("*.wav")} if settings.audio_dir.exists() else set()
    yield
    after = {p.name for p in settings.audio_dir.glob("*.wav")} if settings.audio_dir.exists() else set()
    new = after - before
    assert not new, f"a test called Sarvam TTS and spent credits: {sorted(new)}"
