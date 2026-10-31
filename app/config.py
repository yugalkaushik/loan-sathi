"""Settings, read from the environment / .env.

Everything here has a working default, so the app boots and the whole demo runs with no
`.env` file and no API keys at all. That is deliberate: the offline path is the demo's
safety net, not a degraded mode.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- credentials (optional) ---
    sarvam_api_key: str = ""
    anthropic_api_key: str = ""

    # --- behaviour ---
    # "template" = zero network calls, always correct. "sarvam" / "claude" add a fluency pass.
    ls_narrator: str = "template"

    # Demo assumptions, surfaced so they can be defended as assumptions rather than rules.
    ls_rightsize_threshold: float = 0.15
    ls_coach_dip_fraction: float = 0.80

    # --- Sarvam voice ---
    # Verified against docs.sarvam.ai and the installed SDK on 30 Oct 2026. The deck says
    # "Saaras v3"; v4 is current. See docs/API-REFERENCE.md.
    sarvam_stt_model: str = "saaras:v4"
    # v4-flash, not v3: the task-tuned speakers (the _hi_numbers / _hi_banking family) are
    # only compatible with v4-flash, and it is Rs 1.00 per 1000 chars against v3's Rs 3.00.
    # Cheaper and better suited to reading rupee amounts aloud.
    sarvam_tts_model: str = "bulbul:v4-flash"
    # Not the generic default voice: this one is tuned for reading numerals, and this product
    # reads rupee amounts and percentages aloud.
    sarvam_tts_speaker: str = "ishita_hi_numbers"

    # Only used when LS_NARRATOR=sarvam. The same endpoint and the same key also serve
    # open-weight models (deepseek-v4.1-flash, glm-5.3, gemma-4-31b), so there is never a
    # reason to open a second provider account for this project.
    # NOT plain sarvam-105b. That model reasons until it hits max_tokens (1199 reasoning
    # tokens of a 1200 budget, finish_reason="length", content=None) and never answers.
    # The -conversations variant is Sarvam's real-time/voice-agent model: no reasoning pass,
    # finish_reason="stop", short grounded replies. Verified against the live API 31 Oct 2026.
    sarvam_llm_model: str = "sarvam-105b-conversations"

    # Off-script questions (anything app/intent.py does not recognise) go to the LLM instead
    # of returning "I don't have that information". The engine still owns every number, and
    # narrate._numbers_grounded discards any answer containing a figure it did not compute.
    # Off by default: this is the one-line revert if it misbehaves on the day.
    ls_open_qa: bool = False

    # Read an uploaded loan document with Sarvam Doc AI and compute from what it says,
    # instead of the bundled demo offer. Turn off if Doc AI is slow at the venue: the
    # app falls back to the offer in data/demo.json.
    ls_doc_ai: bool = True
    sarvam_doc_language: str = "en-IN"

    # Cash-flow risk model. Pure Python, no API, no cost. Sims is the Monte Carlo
    # sample size: 2000 x 180 days runs in about 0.1s.
    ls_risk_sims: int = 2000
    ls_risk_seed: int = 42
    # Trading-day failed debits we are willing to accept over the whole term. Closure
    # days are excluded because no loan size prevents them.
    ls_max_trading_misses: float = 1.0

    @property
    def voice_enabled(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def data_file(self) -> Path:
        return ROOT / "data" / "demo.json"

    @property
    def audio_dir(self) -> Path:
        return ROOT / "data" / "audio"

    @property
    def web_dir(self) -> Path:
        return ROOT / "web"


settings = Settings()
