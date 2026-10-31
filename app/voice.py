"""Sarvam speech: text-to-speech out, speech-to-text in.

Sarvam AI is the hackathon's official AI partner, and this uses their official Python SDK
(``sarvamai``) rather than hand-rolled HTTP, which also sidesteps a real trap: the speech
endpoints authenticate with an ``api-subscription-key`` header while chat uses
``Authorization: Bearer``. The SDK takes one key and handles both.

Three deliberate choices:

* **Caching to disk.** :func:`speak` hashes its input and reuses an existing WAV. Repeating a
  demo line costs nothing and plays instantly, and the files survive a dead network.
* **Model is ``bulbul:v4-flash``.** The docs state the persona voices (the
  ``<name>_<language>_<style>`` family, e.g. ``ishita_hi_numbers``) are valid only on
  v4-flash; the short v3 names are not valid on v4 and vice versa. v4-flash is also the
  model Sarvam recommends for new integrations, and at Rs 1.00 per 1000 characters it is
  a third the price of v3. We pick a numerals-tuned voice because this product reads
  rupee amounts and percentages aloud.
* **Never raises for the caller.** Voice is optional (brief rule 5). Every function returns
  ``None`` on failure so the UI silently falls back to text.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from app.config import settings

log = logging.getLogger("loan_saathi.voice")

# Sarvam TTS accepts 11 language codes (vs 24 for STT), see docs/API-REFERENCE.md.
_LANG = {"hi": "hi-IN", "en": "en-IN"}

# v4-only. Nudges the recogniser toward the words this product actually hears.
_KEYTERMS = ["किस्त", "सेटलमेंट", "लोन", "बिक्री", "ब्याज", "installment", "settlement"]

_MAX_TTS_CHARS = 2500   # bulbul:v3 limit


def _client():
    if not settings.sarvam_api_key:
        return None
    from sarvamai import SarvamAI

    return SarvamAI(api_subscription_key=settings.sarvam_api_key)


def speak(text: str, lang: str = "hi") -> str | None:
    """Render `text` to a WAV under ``data/audio/`` and return its public URL path.

    Returns ``None`` if voice is unavailable, so callers can fall back to on-screen text.
    """
    text = (text or "").strip()
    if not text:
        return None

    # Cache key covers everything that changes the audio, so a model or voice change re-renders.
    key = hashlib.sha256(
        f"{settings.sarvam_tts_model}|{settings.sarvam_tts_speaker}|{lang}|{text}".encode()
    ).hexdigest()[:20]

    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    path = settings.audio_dir / f"{key}.wav"
    url = f"/audio/{path.name}"

    if path.exists() and path.stat().st_size > 0:
        return url

    client = _client()
    if client is None:
        return None

    if len(text) > _MAX_TTS_CHARS:
        log.warning("text of %d chars exceeds the %d limit; truncating", len(text), _MAX_TTS_CHARS)
        text = text[:_MAX_TTS_CHARS]

    try:
        resp = client.text_to_speech.convert(
            text=text,
            language_code=_LANG.get(lang, "hi-IN"),
            model=settings.sarvam_tts_model,
            speaker=settings.sarvam_tts_speaker,
            # NOTE: enable_preprocessing is deliberately NOT passed. The docs state it is
            # supported on bulbul:v2 only, not on v3 or v4-flash, where it is ignored.
            speech_sample_rate=22050,
            output_audio_codec="wav",
            pace=0.95,                   # a touch slower: these are numbers people act on
        )
        audio_b64 = resp.audios[0]
    except Exception as exc:
        log.warning("Sarvam TTS failed (%s); falling back to text", exc)
        return None

    try:
        path.write_bytes(base64.b64decode(audio_b64))
    except Exception as exc:
        log.warning("could not write %s: %s", path, exc)
        return None

    return url


def transcribe(
    audio: bytes,
    filename: str = "clip.webm",
    lang: str = "hi",
    content_type: str | None = None,
) -> str | None:
    """Transcribe recorded audio. Returns the transcript, or ``None`` on any failure.

    The browser records WebM/Opus, so we pass the filename and content type explicitly as a
    tuple rather than a bare buffer: Sarvam sniffs the format from the multipart part, and a
    nameless stream gets rejected.
    """
    client = _client()
    if client is None or not audio:
        return None

    # Strip any codec suffix: "audio/webm;codecs=opus" -> "audio/webm".
    ctype = (content_type or "audio/webm").split(";")[0].strip()

    try:
        resp = client.speech_to_text.transcribe(
            file=(filename, audio, ctype),
            model=settings.sarvam_stt_model,
            language_code=_LANG.get(lang, "hi-IN"),
            keyterms=_KEYTERMS,
        )
        return (resp.transcript or "").strip() or None
    except Exception as exc:
        log.warning("Sarvam STT failed (%s); use the text box instead", exc)
        return None
