# Verified external API reference

**All facts below were fetched from official docs on 30 Oct 2026.** This file exists because the pitch
deck is a *pitch*, not an API reference, it is stale on three model names. When deck and this file
disagree, **this file wins**. Re-verify before the final round if more than a few days pass.

This closes the project brief's §7 open items on Sarvam model names and pricing, and the RBI circular.

---

## Sarvam AI, Speech-to-Text

Source: <https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe>

- `POST https://api.sarvam.ai/speech-to-text`
- Auth: header **`api-subscription-key`**
- Audio formats: WAV, MP3, AAC, AIFF, OGG, OPUS, FLAC, MP4/M4A, AMR, WMA, WebM, PCM

| Param | Values |
|---|---|
| `model` | **`saaras:v4`** (default, recommended) · `saaras:v3` |
| `language_code` | `unknown`, `hi-IN`, `en-IN`, `bn-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`, `pa-IN`, `ta-IN`, `te-IN`, `gu-IN`, `as-IN`, `ur-IN`, `ne-IN`, `kok-IN`, `ks-IN`, `sd-IN`, `sa-IN`, `sat-IN`, `mni-IN`, `brx-IN`, `mai-IN`, `doi-IN`, **24 total** |
| `mode` | `transcribe` (default), `translate`, `verbatim`, `translit`, `codemix`, **v3 only** |
| `with_timestamps` | boolean |
| `keyterms` | up to 50 strings, **v4 only**. Use for `किस्त`, `सेटलमेंट`, lender names |

Response: `{request_id, transcript, language_code, timestamps?, language_probability?}`

>  **The deck says "Saaras v3 (22 languages)". v4 is current and the list is 24 codes.**
>  `mode` and `keyterms` are mutually exclusive across versions, picking v4 loses `translate` mode.

## Sarvam AI, Text-to-Speech

Source: <https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert>

- `POST https://api.sarvam.ai/text-to-speech`, `Content-Type: application/json`
- Auth: header **`api-subscription-key`**

| Param | Values |
|---|---|
| `model` | `bulbul:v2` (legacy) · `bulbul:v3` (stable, the API default if `model` is omitted) · **`bulbul:v4-flash` (recommended for new integrations, and what we use)** |
| `text` | required; code-mixed English + Indic supported |
| `language_code` | `hi-IN`, `en-IN`, `bn-IN`, `gu-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`, `pa-IN`, `ta-IN`, `te-IN`, **only 11, vs STT's 24** |
| `speaker` | `shubh` (default), `aditya`, `ritu`, `priya`, `neha`, `rahul`, `pooja`, `rohan`, `simran`, `kavya`, `amit`, `dev`, `ishita`, `shreya`, … 37 total |
| `speech_sample_rate` | 8000, 16000, **22050 (default)**, 24000, 32000, 44100, 48000 |
| `output_audio_codec` | **`wav` (default)**, `mp3`, `aac`, `flac`, `linear16`, `mulaw`, `alaw` |
| `pace` | 0.5–2.0 (v3/v4-flash) · 0.3–3.0 (v2) |
| `temperature` | 0.01–1.0, default 0.6 (v3/v4-flash only) |

- **Char limit: 2500** (v3 / v4-flash) · 1500 (v2)
- Response: `{request_id, audios: ["<base64 WAV>"]}`, base64, so decode before writing to disk

>  TTS covers **11** languages, not the 22/24 of STT. The deck's "11 languages" for Soundbox and
> "22 languages" for STT are both right but refer to different things, do not conflate them on stage.

## Sarvam AI, Chat Completions

Source: <https://docs.sarvam.ai/api-reference-docs/chat/completions>

- `POST https://api.sarvam.ai/v1/chat/completions`
- Auth: header **`Authorization: Bearer <token>`**
- Models: `sarvam-105b` (128K context) · `sarvam-105b-conversations` (32K, real-time voice-agent workloads)

> ⚠️ **Verified against the live API, 31 Oct 2026. Use `sarvam-105b-conversations` for short answers.**
>
> | Model | Behaviour on a 2-sentence grounded answer |
> |---|---|
> | `sarvam-105b` | Takes a reasoning pass that expands to fill whatever budget you give it. At `max_tokens=400` it returned `reasoning_tokens=399`, `finish_reason="length"`, **`content=None`**. At `max_tokens=1200`: `reasoning_tokens=1199`, same result. Unusable here. |
> | `sarvam-105b-conversations` | No reasoning pass, `finish_reason="stop"`, real content in ~10 tokens. |
>
> **`reasoning_effort`**: the live API accepts only `'low'`, `'medium'`, `'high'`. The SDK type
> hints also advertise `'none'` and `'max'`; both return a 400. We omit the parameter entirely.

>  **Auth differs from STT/TTS.** `api-subscription-key` for speech, `Authorization: Bearer` for chat.
> A single `SARVAM_API_KEY` env var feeds both, but the header name changes. Budget zero time for this
> bug: it is written down here.

## Sarvam AI, Pricing

Source: <https://docs.sarvam.ai/api/getting-started/pricing> · pay-as-you-go column

| Item | Rate |
|---|---|
| STT standard | **₹0.49 / min**, billed per second (≈ ₹29.4/hour) |
| STT with diarization | ₹0.59 / min |
| TTS `bulbul:v3` | **₹3.00 / 1,000 chars** (= ₹30 / 10,000 chars) |
| TTS `bulbul:v4-flash` | **₹1.00 / 1,000 chars**, 3× cheaper than v3 |
| `sarvam-105b` | ₹15 / M input · ₹60 / M output · ₹5 / M cached input |
| Free credits | **₹100** for verified users on signup, no expiry, usable across all APIs |

> This **confirms** the brief's §7 estimates (₹30/hour STT, ₹30/10k chars TTS), they were right.
> `bulbul:v4-flash` at ₹1.00/1k is the answer if a judge asks about unit economics at scale.

---

## Anthropic, Claude

Source: bundled `claude-api` skill, cached 2026-06-24. SDK `anthropic` **2.3.0** (verified on PyPI).

- Model **`claude-opus-5`** · 1M context · $5/M input, $25/M output
- `thinking: {"type": "adaptive"}`, **`budget_tokens` is removed and returns 400** on Opus 5
- Effort: `output_config: {"effort": "low"|"medium"|"high"|"xhigh"|"max"}` (default `high`)
- Structured output: `output_config: {"format": {...}}`, the old `output_format` param is deprecated
- **Assistant prefill returns 400** on Opus 5, use structured outputs or system prompt instead
- Always check `stop_reason == "refusal"` before reading `content`; `stop_details` is populated only then
- Recommended: `betas: ["server-side-fallback-2026-07-01"]` + `fallbacks: "default"`

Used for: narration (JSON → Hindi prose) and voice intent extraction (transcript → `{intent, shock_pct}`)
via structured outputs. **Never for arithmetic.**

---

## RBI, Key Facts Statement

Source: [RBI/2024-25/18, DOR.STR.REC.13/13.03.00/2024-25, **15 Apr 2024**](https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12663&Mode=0)
Applies to commercial banks, cooperative banks and NBFCs.

Verbatim quotes safe to use on stage:

> "The KFS shall be written in a language understood by such borrowers."

> "Annual Percentage Rate (APR) is the annual cost of credit to the borrower which includes interest
> rate and all other charges associated with the credit facility."

> "Regulated Entities shall provide a KFS to all prospective borrowers to help them take an informed
> view before executing the loan contract, as per the standardised format given in the Annex A."

- **Annex A** = standardised KFS format · **Annex B** = APR computation illustration ·
  **Annex C** = repayment schedule. All three are **separate PDFs**, not in the circular's HTML page.
-  **Outstanding:** fetch Annex A for exact KFS row labels, and Annex B to validate `app/engine/apr.py`.
  Until Annex B is checked, describe our APR as *"APR including all charges, per the circular's
  definition"*, not *"RBI Annex B compliant"*.

> This **closes** the brief's §3.4 CHECK item: the circular and date are now confirmed.

---

## Local toolchain (verified 30 Oct 2026)

Present: Python **3.14.5**, Node, npm, Docker, git. Absent: `uv`, `psql`, `ffmpeg`.

Binary wheels confirmed to resolve on **cp314**, so no older Python is needed:
`fastapi 0.162.0` · `uvicorn 0.54.0` · `pydantic 2.14.2` · `pydantic_core 2.50.2 (cp314 native)` ·
`anthropic 2.3.0` · `python-multipart 0.0.32` · `pytest 9.2.0` · `httpx 0.28.1`

> `ffmpeg` is absent, Sarvam accepts WAV directly and returns WAV, so no transcoding is needed.
> Do not add an ffmpeg dependency.

---

## Sarvam AI, official Python SDK (use this, not raw httpx)

Source: <https://docs.sarvam.ai/api/getting-started/quickstart> + introspection of the installed package.

```bash
pip install -U sarvamai      # installed: 0.1.41
```

```python
from sarvamai import SarvamAI, AsyncSarvamAI
client = SarvamAI(api_subscription_key="...")       # AsyncSarvamAI for async
client.speech_to_text.transcribe(...)               # -> SpeechToTextResponse
client.text_to_speech.convert(...)                  # -> TextToSpeechResponse
```

**The SDK solves the two-auth-header problem**, one `api_subscription_key` arg covers speech *and*
`client.chat`, so we never hand-build the `Authorization: Bearer` header. Prefer the SDK over `httpx`.

Available sub-clients: `speech_to_text`, `speech_to_text_streaming`,
**`speech_to_text_realtime_streaming`**, `speech_to_text_translate_streaming`, `text_to_speech`,
`text_to_speech_streaming`, `chat`, `chat_completion`, `responses`, `text`, `doc_ai`,
`document_translation`, `dubbing`, `voice_cloning`, `pronunciation_dictionary`, plus `*_job` batch variants.

> **`speech_to_text_realtime_streaming` may remove the need for LiveKit entirely.** The deck promises a
> "LiveKit voice pipeline"; Sarvam's own realtime streaming is a far smaller bet. Still **cut for the
> MVP** (rule 5: voice is optional), but this is the honest answer if a judge asks how duplex would work,
> better than naming a third-party dependency we never wired up.

### Parameters the docs page did NOT list (found by introspection)

| Param | Why it matters |
|---|---|
| `enable_preprocessing: bool` | **Do not rely on it.** The docs state it applies to `bulbul:v2` only (default false) and is *not supported* on v3 or v4-flash. An earlier note here claimed it was load-bearing for reading `₹700`. That was wrong. |
| `enable_cached_responses: bool` | Caches repeated TTS. Free win for a demo that replays the same lines. |
| `dict_id: str` | Pronunciation dictionary id, via `client.pronunciation_dictionary`. Use to pin `किस्त`, `सेटलमेंट`, lender names. |
| `pitch`, `loudness` | Alongside `pace` / `temperature`. |

### Speakers are per model, and the families do not mix

> **Correction, 31 Oct 2026.** An earlier version of this file implied the ~250 persona
> voices worked on any model. They do not. Sending `ishita_hi_numbers` with `bulbul:v3`
> returns a 400. Confirmed against the live API and the docs.

| Model | Speakers |
|---|---|
| `bulbul:v2` | `anushka` (default), `manisha`, `vidya`, `arya`, `abhilash`, `karun`, `hitesh` |
| `bulbul:v3` | `shubh` (default), `aditya`, `ritu`, `priya`, `neha`, `ishita`, ... 37 short names |
| **`bulbul:v4-flash`** | **200+ persona voices, `<name>_<language>_<style>`.** Default `shubh_enhi_ads`. Short v3 names are rejected. |

We use **`bulbul:v4-flash` + `ishita_hi_numbers`**. Still useful:

The docs page lists generic speakers only. The SDK exposes task-tuned voices. Relevant ones:

| Use | Speaker |
|---|---|
| **Reading rupee amounts and percentages** | **`ishita_hi_numbers`** · `ishita_en_numbers` · `shubh_en_numbers`, voices tuned for numerals. Pick one of these for the KFS/burden narration. |
| **Banking tone, Hindi** | `ishita_hi_banking` · `ritu_hi_banking` · `sanchita_hi_banking` |
| **Banking tone, code-mixed Hinglish** | `shubh_enhi_banking` · `simran_enhi_banking_expressive` |
| KYC / consent moments | `sanchita_hi_kyc` · `aparna_hi_kyc` |
| Customer-support tone | `ritu_hi_customer_warm` · `shubh_hi_customer` · `aparna_hi_customer` |

>  **Deliberately avoid the `*_recovery` voices** (`priya_hi_recovery`, `shubh_hi_recovery`,
> `roopa_hi_recovery`, `simran_hi_recovery`, …). They are collections-agent voices. Loan Saathi is
> positioned *against* voice-led pressure selling (brief §3.3, §4), using a debt-collection voice would
> contradict the pitch. If asked, this is a deliberate product choice worth stating.

> **Listen before you trust it.** Whether `ishita_hi_numbers` reads "₹700" as "saat sau
> rupaye" or spells the digits out is an empirical question, and `enable_preprocessing`
> is not available to fix it on v4-flash. If it reads wrong, change the Hindi in
> `app/narrate.py` to spell the amount out, then re-render.

### Confirmed by the SDK's own type hints

- STT `model`: `'saaras:v3' | 'saaras:v4'`, **confirms v4 exists; the deck's "v3" is stale**
- TTS `model`: `'bulbul:v2' | 'bulbul:v3' | 'bulbul:v4-flash'`
- TTS `language_code`: exactly 11 codes · STT `language_code`: 24 codes
- STT `input_audio_codec` includes `pcm_s16le`, `pcm_l16`, `pcm_raw` for raw mic capture


---

## Paytm Soundbox: two different devices

Worth keeping straight, because the product page and the launch coverage describe different
hardware and an earlier version of these notes conflated them.

| | Standard Soundbox range | **Paytm AI Soundbox** |
|---|---|---|
| Listed on `business.paytm.com/soundbox` | yes, 11 models | not listed there |
| Speaks payment confirmations | yes, 11 regional languages | yes |
| **Microphone / merchant speaks to it** | **no**, the page never mentions one | **yes**, integrated mic |
| Voice assistant | no | yes, 11 Indian languages plus English |
| Answers sales and collection questions | no | yes, by voice or touch |
| Screen | Display model only | dual: front touchscreen plus top display |

Launched at Global Fintech Festival, October 2025. Paytm's own blog about the device is more
reserved than the launch coverage, describing voice-led merchant assistance as something the
Soundbox is *"evolving to support"*, and giving no language count.

**What to say on stage:** describe the AI Soundbox as having a microphone and a voice
assistant, which the product coverage supports. Do not claim it does lending conversations
today, and do not attribute a mic to the standard Soundbox range, because Paytm's own product
page does not list one.

**Why it matters architecturally:** Loan Saathi is an HTTP service. On a device with its own
speech stack we drop Saaras and Bulbul and keep the engine, so the integration gets *smaller*,
not bigger. Consent stays in the app regardless, since voice must never record consent.
