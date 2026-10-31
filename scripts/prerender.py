"""Pre-render the demo's Hindi audio to disk, once.

Why pre-render at all: the WAVs land in ``data/audio/`` and ``app/voice.py`` reuses them by
content hash. So the demo plays instantly, costs nothing to repeat, and keeps working if the
venue wifi dies mid-pitch. One spend, permanent benefit.

Credits are limited, so this script **does not spend anything by default**. It prints the exact
character count and rupee cost first:

    python scripts/prerender.py              # dry run, costs nothing
    python scripts/prerender.py --go         # Hindi only, the lines the demo plays
    python scripts/prerender.py --go --en    # add English

Already-cached lines are skipped and never re-billed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import engine, narrate, voice          # noqa: E402
from app.config import settings                 # noqa: E402

# bulbul:v4-flash pay-as-you-go, docs.sarvam.ai/api/getting-started/pricing (checked 30 Oct 2026).
# v3 is Rs 3.00 per 1000; v4-flash is Rs 1.00 and supports the numerals-tuned speakers.
RATE_PER_CHAR = 1.00 / 1000


def demo_lines(langs: list[str]) -> dict[str, tuple[str, str]]:
    """The exact sentences the demo speaks, built from the real engine output."""
    data = json.loads(settings.data_file.read_text(encoding="utf-8"))
    settlements = data["settlements"]["daily"]
    offer = data["offer"]
    installment = offer["daily_installment"]

    base = engine.simulate(settlements, installment)
    shock = engine.simulate(settlements, installment, -0.30)
    right = engine.rightsize(settlements, offer, settings.ls_rightsize_threshold)
    coach = engine.coach(settlements, installment, settings.ls_coach_dip_fraction)

    out: dict[str, tuple[str, str]] = {}
    for lang in langs:
        out[f"1-explain.{lang}"] = (narrate.explain_offer(offer, base, lang), lang)
        out[f"2-shock30.{lang}"] = (narrate.explain_shock(shock, base, lang), lang)
        out[f"3-rightsize.{lang}"] = (narrate.explain_rightsize(right, offer, lang), lang)
        out[f"4-coach.{lang}"] = (narrate.explain_coach(coach, lang), lang)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-render demo audio via Sarvam TTS.")
    ap.add_argument("--go", action="store_true", help="actually call the API and spend credits")
    ap.add_argument("--en", action="store_true", help="also render English (roughly doubles cost)")
    ap.add_argument("--only", metavar="NAME", help="render a single line, e.g. 1-explain.hi")
    args = ap.parse_args()

    langs = ["hi"] + (["en"] if args.en else [])
    lines = demo_lines(langs)
    if args.only:
        if args.only not in lines:
            print(f"unknown line {args.only!r}. available: {', '.join(lines)}")
            return 1
        # Render one line first to hear how the voice handles rupee amounts. If the wording
        # has to change, every content hash changes and the rest would be billed twice.
        lines = {args.only: lines[args.only]}
    total_chars = sum(len(text) for text, _ in lines.values())
    cost = total_chars * RATE_PER_CHAR

    print(f"model   {settings.sarvam_tts_model}")
    print(f"speaker {settings.sarvam_tts_speaker}")
    print(f"output  {settings.audio_dir}\n")

    for name, (text, _) in lines.items():
        print(f"  {name:18} {len(text):4} chars   Rs {len(text) * RATE_PER_CHAR:5.2f}")
    print(f"\n  TOTAL              {total_chars:4} chars   Rs {cost:5.2f}")

    if not args.go:
        print("\nDry run, nothing spent. Add --go to render for real.")
        return 0

    if not settings.voice_enabled:
        print("\nSARVAM_API_KEY is not set. Put it in .env first.")
        return 1

    print("\nRendering...")
    made = skipped = failed = 0
    for name, (text, lang) in lines.items():
        before = {p.name for p in settings.audio_dir.glob("*.wav")}
        url = voice.speak(text, lang)
        if url is None:
            print(f"  FAILED  {name}")
            failed += 1
            continue
        after = {p.name for p in settings.audio_dir.glob("*.wav")}
        if after - before:
            print(f"  cached  {name}  ->  {url}")
            made += 1
        else:
            print(f"  already {name}  ->  {url}  (not re-billed)")
            skipped += 1

    print(f"\n{made} rendered, {skipped} already cached, {failed} failed.")
    if failed:
        print("A failure costs nothing and the UI falls back to on-screen text.")
    else:
        print("The demo now plays from disk and needs no network.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
