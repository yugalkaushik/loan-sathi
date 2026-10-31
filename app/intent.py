"""Work out what the merchant asked for, from typed or spoken text.

Deliberately a deterministic parser and not an LLM call. Three reasons: it is instant, it works
with no API key, and the only thing we need out of a question like "अगर बिक्री तीस परसेंट गिरी तो?"
is a small integer. Handing that to a model would add latency and a failure mode for no gain.

Handles Hindi number words, Devanagari digits and ASCII digits, in Hindi, English or a mix,
because that is how merchants actually talk.
"""

from __future__ import annotations

import re

# Spoken Hindi/Hinglish numbers we might hear in a sales-drop question.
_WORD_NUMBERS = {
    "दस": 10, "पंद्रह": 15, "बीस": 20, "पच्चीस": 25, "तीस": 30, "पैंतीस": 35,
    "चालीस": 40, "पैंतालीस": 45, "पचास": 50, "पचपन": 55, "साठ": 60,
    "आधी": 50, "आधा": 50, "आधे": 50,          # "half"
    "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "half": 50,
}

_RIGHTSIZE_HINTS = (
    "छोटा", "कम", "घटा", "घटाओ", "सुझा", "छोटी",
    "smaller", "reduce", "lower", "less", "right size", "rightsize",
)

_COACH_HINTS = (
    "अलर्ट", "चेतावनी", "गिर रही", "कैसा चल", "हाल",
    "alert", "warn", "coach", "trend", "how am i doing",
)

# "Explain" needs BOTH an asking verb and a loan-domain word. A bare "what is..." or
# "बताओ" must not match, or "what is the weather in Mumbai" gets answered as a loan question
# instead of honestly returning "I don't have that information".
_ASK_HINTS = (
    "समझा", "बताओ", "क्या", "कितना", "कैसे",
    "explain", "what", "tell me", "how much", "how many", "?",
)

_DOMAIN_HINTS = (
    "लोन", "ऑफ़र", "ऑफर", "किस्त", "कर्ज़", "कर्ज", "ब्याज", "सेटलमेंट", "राशि",
    "चुकाना", "चुकता", "भुगतान", "अवधि", "बिक्री",
    "loan", "offer", "installment", "instalment", "emi", "interest", "repay",
    "settlement", "tenure", "payable", "principal", "fee",
)

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def parse(text: str) -> dict:
    """Return ``{"intent": ..., "shock_pct": float|None, "matched": str|None}``.

    Intents: ``"shock"`` (run a stress test), ``"rightsize"``, ``"coach"``, ``"explain"``,
    or ``"unknown"``, for which the UI should say it doesn't have that and offer a handoff.
    """
    raw = (text or "").strip()
    low = raw.lower().translate(_DEVANAGARI_DIGITS)

    drop, matched = _extract_drop(low)

    # A stated drop is the strongest signal: "30% गिरी" is unambiguously a stress test,
    # even when the sentence also contains the word "offer".
    if drop is not None:
        return {"intent": "shock", "shock_pct": -drop / 100, "matched": matched}

    for hints, name in ((_RIGHTSIZE_HINTS, "rightsize"), (_COACH_HINTS, "coach")):
        if any(h in low for h in hints):
            return {"intent": name, "shock_pct": None, "matched": None}

    if any(d in low for d in _DOMAIN_HINTS) and any(a in low for a in _ASK_HINTS):
        return {"intent": "explain", "shock_pct": None, "matched": None}

    return {"intent": "unknown", "shock_pct": None, "matched": None}


def _extract_drop(low: str) -> tuple[int | None, str | None]:
    """Pull a percentage drop out of the text, as a positive integer (30 means a 30% fall)."""
    # "30%", "30 percent", "30 परसेंट", or a bare "30" next to a fall verb.
    m = re.search(r"(\d{1,2})\s*(?:%|percent|परसेंट|प्रतिशत|फ़ीसदी|फीसदी)", low)
    if m:
        return _clamp(int(m.group(1))), m.group(0)

    for word, value in _WORD_NUMBERS.items():
        if word in low:
            return _clamp(value), word

    # Last resort: a bare number in a sentence that clearly describes a fall.
    if any(v in low for v in ("गिर", "घट", "कम", "drop", "fall", "down")):
        m = re.search(r"\b(\d{1,2})\b", low)
        if m:
            return _clamp(int(m.group(1))), m.group(0)

    return None, None


def _clamp(pct: int) -> int:
    """Keep the shock inside the slider's range, so UI and voice can never disagree."""
    return max(0, min(60, pct))
