# Loan Saathi, hackathon MVP

Voice-first Hindi copilot for Paytm merchant loans. Paytm Build for India AI Hackathon, Delhi, Track 2.
Team MegaByte · Yugal Kaushik · build day 31 Oct 2026, Noida. **Stage 1 cleared, this is the finals.**

Three things it does: **explain** a loan offer in Hindi · **stress-test** it against the merchant's own
settlement history · **coach** on a sales dip.

**Keep it simple. A working 3-minute demo beats everything else.**

- **What we're building and how to pitch it: `mvp.md`** (includes fresh Paytm Q2 FY27 numbers)
- **What to build, hour by hour: `docs/BUILD-ORDER.md`**

## The app (built, 51 tests passing)

```
app/engine.py      simulate / rightsize / coach      stdlib only, no I/O
app/narrate.py     Hindi + English templates         holds the sentences, not the numbers
app/intent.py      question -> intent + shock %      deterministic, no LLM
app/voice.py       Sarvam TTS/STT                    optional, caches WAVs, never raises
app/document.py    Sarvam Doc AI: PDF -> loan terms  validates before trusting; never raises
app/config.py      env settings                      every value has a working default
app/main.py        FastAPI: 9 routes + static        one process, one port
data/demo.json     90 settlements + offer + KFS      regenerate: scripts/gen_data.py
web/               index.html, styles.css, app.js    no framework, no build step
tests/test_engine.py  51 tests                       pins deck slide 6
```

Do not add: Postgres, SQLite, repo Protocols, LiveKit, APR/IRR maths, integer-paise money types,
React/Vite, auth, extra languages. If it isn't in the 6 files above, it isn't in the MVP.

## Rules (from the brief, these actually matter)

1. **The LLM never does maths and never decides credit.** Numbers come from `engine.py`. The LLM only
   turns them into a sentence. If a field is missing it says "I don't have that information".
2. **All data is synthetic**, say so in the UI. Never present it as Paytm data.
3. **Consent needs a tap, not a voice.** Any money/consent action gets a PIN or button confirm.
4. **Voice is optional.** Text flow first; voice after it works; text stays the fallback.
5. **`shock_pct` is negative.** -0.30 = a 30% drop. Formula: `E / (A * (1 + shock_pct))`.
6. **`A` is the mean** of 90 days of settlement. The UI says "average day".

## API strings (verified, the deck is wrong, see docs/API-REFERENCE.md)

| | Use | Note |
|---|---|---|
| Sarvam SDK | `pip install sarvamai` → `SarvamAI(api_subscription_key=...)` | Already installed. Use it, not raw HTTP. |
| STT | `saaras:v4` | Deck says v3. v4 is current. |
| TTS | **`bulbul:v4-flash`**, speaker `ishita_hi_numbers` | Persona voices like `*_hi_numbers` work on v4-flash only, never on v3. v4-flash is also 3x cheaper (Rs 1.00 vs Rs 3.00 per 1000 chars). |
| Doc AI | `client.doc_ai.extract(file=[(name, bytes, mime)], schema=json.dumps(...), output_format="json")` | Async job: submit, `get_status` poll, `get_results`. **No `language` arg** despite the docs, SDK 0.1.41 raises TypeError. ~5s for 1 page, about Rs 1/page. |
| LLM | **`sarvam-105b-conversations`** | NOT plain `sarvam-105b`: it reasons until `max_tokens` and returns `content=None`. Only used for off-script questions. |
| `reasoning_effort` | **omit it** | Live API accepts only `low`/`medium`/`high` (SDK hints also list `none`/`max`, which 400). On reasoning models any value runs away. |

`claude-opus-5` works too (`anthropic` SDK is installed) but Sarvam is the better demo story here.

## Commands

```bash
cp .env.example .env            # paste SARVAM_API_KEY
. .venv/Scripts/activate
uvicorn app.main:app --reload --port 8080   # http://127.0.0.1:8080
# NOTE: port 8000 is blocked on this machine (WinError 10013). 8080 / 8088 / 9000 work.
pytest -q                                   # 78 tests: 51 engine + 27 API

python scripts/gen_data.py                  # regenerate the synthetic dataset
python scripts/prerender.py                 # dry run: shows TTS cost, spends nothing
python scripts/prerender.py --go            # renders the Hindi demo audio, about Rs 3.34
```

**Credits are limited.** `prerender.py` never spends without `--go`, skips anything already
cached, and the cached WAVs make every later replay free. One spend covers the whole demo.

Python 3.14.5, venv ready, all deps installed. Runs fully offline with no `.env` and no API
keys, `LS_NARRATOR=template` plus on-screen text is the default path. Set `SARVAM_API_KEY`
to add voice; set `LS_NARRATOR=sarvam` to add the LLM fluency pass.
