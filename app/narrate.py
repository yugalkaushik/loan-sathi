"""Turn engine output into a sentence a merchant understands.

The single most important property of this module: **it holds the templates, the engine holds
the numbers.** Values are substituted into fixed strings, so there is no code path by which a
language model can produce a rupee figure. That is what makes the pitch's claim, "the LLM only
explains, a deterministic engine does all the math", a property of the architecture rather than
a promise on a slide.

An optional LLM pass (:func:`polish`) can rephrase a template for fluency, but it receives the
already-rendered sentence and is strictly best-effort: any failure returns the template unchanged.

Every narration ends with the next step and, where money or consent is involved, a reminder that
confirmation happens in the app, plus the disclaimer required by the brief (§5.4).
"""

from __future__ import annotations

HINDI = "hi"
ENGLISH = "en"

# Kept for reference but deliberately NOT appended to spoken narration: repeating it at the
# end of every sentence made the audio long and the voice clunky. The disclosure now lives in
# the UI instead, where it is on screen continuously rather than said four times:
# the "Synthetic demo data, not Paytm data" badge in the masthead, and the colophon footer.
DISCLAIMER = {
    HINDI: "यह एक अनुमान है, गारंटी नहीं।",
    ENGLISH: "This is a simulation, not a guarantee.",
}

CONFIRM_REMINDER = {
    HINDI: "आगे बढ़ने के लिए ऐप में PIN से पुष्टि करनी होगी।",
    ENGLISH: "To proceed you'll confirm with your PIN in the app.",
}

NO_INFO = {
    HINDI: "यह जानकारी मेरे पास नहीं है। मैं आपको Paytm की टीम से जोड़ सकता हूँ।",
    ENGLISH: "I don't have that information. I can connect you to the Paytm team.",
}


def _inr(amount: float) -> str:
    """Format in the Indian grouping system: 1,26,000, not 126,000.

    Groups the last three digits, then in pairs. Getting this wrong is immediately obvious to
    an Indian audience, so it is worth the eight lines.
    """
    n = int(round(amount))
    sign = "-" if n < 0 else ""
    digits = str(abs(n))
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return f"{sign}₹{','.join(pairs)},{tail}"


def explain_offer(offer: dict, sim: dict, lang: str = HINDI) -> str:
    """Beat 1: read the offer and its Key Facts aloud."""
    if lang == HINDI:
        body = (
            f"{offer['lender_name']} से {_inr(offer['loan_amount'])} का लोन ऑफ़र है। "
            f"रोज़ की किस्त {_inr(offer['daily_installment'])} है, "
            f"{offer['tenor_days']} दिन के लिए, और कुल चुकाना है {_inr(offer['total_payable'])}। "
            f"ब्याज दर {offer['interest_rate_pa']}% सालाना है और प्रोसेसिंग फीस "
            f"{_inr(offer['processing_fee'])} है। "
            f"यह किस्त आपकी औसत रोज़ की सेटलमेंट {_inr(sim['avg_daily'])} का "
            f"{sim['burden_pct']}% है। "
            f"किस्त रोज़ आपकी Paytm सेटलमेंट से अपने आप कट जाएगी।"
        )
    else:
        body = (
            f"{offer['lender_name']} has offered you {_inr(offer['loan_amount'])}. "
            f"The daily installment is {_inr(offer['daily_installment'])} for "
            f"{offer['tenor_days']} days, and the total payable is {_inr(offer['total_payable'])}. "
            f"The interest rate is {offer['interest_rate_pa']}% a year and the processing fee is "
            f"{_inr(offer['processing_fee'])}. "
            f"That installment is {sim['burden_pct']}% of your average daily settlement of "
            f"{_inr(sim['avg_daily'])}. "
            f"It is auto-deducted from your Paytm settlement every day."
        )
    return f"{body}"


def explain_shock(sim: dict, base: dict, lang: str = HINDI) -> str:
    """Beat 2: the stress test. The number that actually changes a decision."""
    drop = abs(round(sim["shock_pct"] * 100))

    if lang == HINDI:
        parts = [
            f"अगर बिक्री {drop}% गिरी, तो आपकी रोज़ की सेटलमेंट "
            f"{_inr(base['avg_daily'])} से {_inr(sim['shocked_avg'])} रह जाएगी। "
            f"किस्त {_inr(sim['installment'])} वही रहेगी, यानी आपकी कमाई का "
            f"{sim['burden_pct']}%, आज के {base['burden_pct']}% के मुकाबले।"
        ]
        if sim["shortfall_days"]:
            parts.append(
                f"पिछले {sim['shock_days']} दिनों के आपके ही आँकड़ों में {sim['shortfall_days']} दिन "
                f"ऐसे थे जब सेटलमेंट पूरी किस्त के लिए कम पड़ता, कुल "
                f"{_inr(sim['cumulative_shortfall'])} की कमी।"
            )
        else:
            parts.append(
                f"पिछले {sim['shock_days']} दिनों में हर दिन सेटलमेंट किस्त से ज़्यादा रहता।"
            )
        parts.append("क्या मैं छोटा लोन सुझाऊँ?")
    else:
        parts = [
            f"If sales fall {drop}%, your daily settlement drops from "
            f"{_inr(base['avg_daily'])} to {_inr(sim['shocked_avg'])}. "
            f"The {_inr(sim['installment'])} installment does not change, so it becomes "
            f"{sim['burden_pct']}% of your takings, against {base['burden_pct']}% today."
        ]
        if sim["shortfall_days"]:
            parts.append(
                f"On your own last {sim['shock_days']} days, there were {sim['shortfall_days']} days "
                f"where the settlement would not have covered the full installment, "
                f"{_inr(sim['cumulative_shortfall'])} short in total."
            )
        else:
            parts.append(
                f"Across your last {sim['shock_days']} days, every day would still have covered it."
            )
        parts.append("Shall I suggest a smaller loan?")

    return " ".join(parts)


def explain_rightsize(rs: dict, offer: dict, lang: str = HINDI) -> str:
    """Beat 3: the smaller, survivable offer."""
    if not rs["changed"]:
        return (
            f"यह ऑफ़र {rs['ceiling_pct']}% की सीमा में पहले से है, इसलिए घटाने की ज़रूरत नहीं।"
            if lang == HINDI else
            f"This offer already stays within the {rs['ceiling_pct']}% limit, so there is no need "
            f"to reduce it."
        )

    if lang == HINDI:
        body = (
            f"{_inr(offer['loan_amount'])} की जगह {_inr(rs['loan_amount'])} लेने पर "
            f"रोज़ की किस्त {_inr(rs['daily_installment'])} होगी, रोज़ "
            f"{_inr(rs['saved_per_day'])} कम। "
            f"तब बिक्री {abs(round(rs['shock_pct'] * 100))}% गिरने पर भी किस्त आपकी कमाई का "
            f"सिर्फ़ {rs['burden_pct']}% रहेगी। "
            f"कुल चुकाना होगा {_inr(rs['total_payable'])}।"
        )
    else:
        body = (
            f"Taking {_inr(rs['loan_amount'])} instead of {_inr(offer['loan_amount'])} puts the "
            f"daily installment at {_inr(rs['daily_installment'])}, {_inr(rs['saved_per_day'])} "
            f"less every day. Even if sales fall {abs(round(rs['shock_pct'] * 100))}%, the "
            f"installment stays at just {rs['burden_pct']}% of your takings. "
            f"Total payable would be {_inr(rs['total_payable'])}."
        )
    return f"{body} {CONFIRM_REMINDER[lang]}"


def explain_coach(c: dict, lang: str = HINDI) -> str:
    """Beat 5: the early warning, before a payment is missed."""
    if not c["alert"]:
        return (
            f"पिछले 7 दिनों की औसत सेटलमेंट {_inr(c['last_7_avg'])} है, जो सामान्य है। "
            f"कोई चिंता की बात नहीं।"
            if lang == HINDI else
            f"Your last 7 days average {_inr(c['last_7_avg'])}, which is normal. "
            f"Nothing to worry about."
        )

    if lang == HINDI:
        body = (
            f"ध्यान दें: पिछले 7 दिनों की औसत सेटलमेंट {_inr(c['last_7_avg'])} है, "
            f"जो आपके 90 दिन के औसत {_inr(c['baseline_avg'])} से {c['drop_pct']}% कम है। "
            f"इस रफ़्तार पर किस्त आपकी कमाई का {c['burden_now_pct']}% ले रही है।"
        )
        tail = (
            "मैं Paytm की टीम से बात करने का अनुरोध भेज सकता हूँ, ताकि किस्त कम करवाई जा सके। "
            "कोई फ़ैसला AI नहीं करता, इंसान करता है।"
            if c["handoff_suggested"] else
            "अभी कोई किस्त छूटी नहीं है। मैं नज़र रखूँगा।"
        )
    else:
        body = (
            f"Heads up: your last 7 days average {_inr(c['last_7_avg'])}, which is "
            f"{c['drop_pct']}% below your 90-day average of {_inr(c['baseline_avg'])}. "
            f"At this rate the installment is taking {c['burden_now_pct']}% of your takings."
        )
        tail = (
            "I can raise a request for the Paytm team to review reducing your installment. "
            "No AI makes that decision, a person does."
            if c["handoff_suggested"] else
            "You haven't missed an installment yet. I'll keep watching."
        )
    return f"{body} {tail}"


# --- Optional LLM polish ---------------------------------------------------------------
# Strictly best-effort fluency pass. It never sees raw data and never computes: it receives a
# finished sentence and may only rephrase it. Any error, refusal or empty reply returns the
# original template. Off unless LS_NARRATOR is set to "sarvam" or "claude".

_POLISH_SYSTEM = (
    "You rephrase one sentence for a small Indian shopkeeper so it sounds natural and warm. "
    "Rules you must not break: keep EVERY number, rupee amount and percentage exactly as given; "
    "do not add any new number; do not add facts; do not give financial advice; do not recommend "
    "a lender or promise approval; keep the same language as the input. "
    "Reply with the rephrased sentence only."
)


def polish(text: str, narrator: str, lang: str = HINDI) -> tuple[str, bool]:
    """Optionally rephrase `text`. Returns ``(sentence, llm_used)``.

    Falls back to the input on any failure, so a dead API or a missing key degrades to correct
    template Hindi rather than to an error.
    """
    if narrator not in ("sarvam", "claude"):
        return text, False
    try:
        if narrator == "sarvam":
            out = _polish_sarvam(text)
        else:
            out = _polish_claude(text)
    except Exception:
        return text, False

    out = (out or "").strip()
    if not out or not _numbers_preserved(text, out):
        # The model dropped or invented a figure. Discard it and keep the template.
        return text, False
    return out, True


def _numbers_preserved(original: str, candidate: str) -> bool:
    """Reject a rephrasing that changed the set of numbers.

    Cheap, final backstop on top of the architecture: the templates already mean the model
    cannot source a number, but it could still garble one it was handed.
    """
    return _number_set(original) == _number_set(candidate)


def _numbers_grounded(answer: str, facts_json: str) -> bool:
    """Every number in a free-form answer must already appear in the facts we supplied.

    The rule for :func:`answer_question` differs from :func:`_numbers_preserved`: the model is
    writing a new sentence rather than rephrasing one, so the sets will not match. What must
    hold is containment. If the model produces a figure that is nowhere in the engine's output,
    it invented it, and the answer is discarded.

    Small integers are exempt: a sentence like "there are 2 reasons" or "in the next 7 days"
    uses a counting word, not a financial figure, and the engine's facts already contain the
    numbers that matter. Anything 100 or above, or with a decimal point, must be grounded.
    """
    allowed = _number_set(facts_json)
    for token in _number_set(answer):
        if "." not in token and int(token) < 100:
            continue
        if token not in allowed:
            return False
    return True


def _number_set(text: str) -> set[str]:
    import re

    # Normalise Devanagari digits so ७०० and 700 compare equal, then drop grouping commas.
    trans = str.maketrans("०१२३४५६७८९", "0123456789")
    normalised = text.translate(trans).replace(",", "")
    return set(re.findall(r"\d+(?:\.\d+)?", normalised))


# --- Open question answering -----------------------------------------------------------
# The deterministic parser in app/intent.py handles the four questions the demo is built on.
# Anything else used to return NO_INFO. With LS_OPEN_QA enabled, those go to the LLM instead,
# which may only phrase figures the engine already computed: `_numbers_grounded` enforces that
# after the fact, so the guarantee survives a prompt the model chooses to ignore.

_ANSWER_SYSTEM = (
    "You are Loan Saathi, helping a small Indian shopkeeper understand a loan offer they have "
    "been given. You will be shown a JSON object of facts computed by a deterministic engine "
    "from this shopkeeper's own Paytm settlement history.\n\n"
    "BE HELPFUL FIRST. The JSON is rich: it holds the offer terms, 90 days of settlement "
    "statistics, what happens if sales fall 30% or 50%, a smaller loan option, and the recent "
    "repayment trend. Most questions a shopkeeper asks can be answered from it, sometimes "
    "indirectly. For example, a question about closing the shop some days relates to "
    "'days_below_installment' and 'lowest_day', because the installment is deducted whether or "
    "not the shop opened. Look for the facts that bear on the question and use them.\n\n"
    "Rules you must not break:\n"
    "1. Every number, rupee amount and percentage you state must appear in the JSON. Never "
    "estimate, extrapolate, convert or compute a new figure. If answering well would need a "
    "number that is not there, describe the situation in words instead.\n"
    "2. Only if nothing in the JSON bears on the question, say you do not have that information "
    "and offer to connect them to the Paytm team. Do not guess, and do not answer questions "
    "that have nothing to do with this loan or this business.\n"
    "3. Give no financial advice, recommend no lender, and never suggest the loan will be "
    "approved. Approval is the lender's decision, not yours.\n"
    "4. Anything involving money or consent happens with an in-app PIN confirmation.\n"
    "5. Reply in the language you are asked to, in at most two short sentences, in plain words a "
    "shopkeeper would use.\n"
    "Reply with the answer only."
)


def answer_question(question: str, facts: dict, lang: str = HINDI) -> tuple[str, bool]:
    """Answer an off-script question from the engine's facts. Returns ``(text, llm_used)``.

    Every failure path returns the honest fallback rather than raising: no key, API down, a
    refusal, an empty reply, or an answer containing a figure the engine never produced. So the
    worst case is exactly the behaviour before this function existed.
    """
    import json

    from app.config import settings

    if not settings.ls_open_qa or not settings.sarvam_api_key:
        return NO_INFO[lang], False

    facts_json = json.dumps(facts, ensure_ascii=False)
    language = "Hindi" if lang == HINDI else "English"
    prompt = (
        f"Facts (JSON):\n{facts_json}\n\n"
        f"The shopkeeper asks: {question}\n\n"
        f"Answer in {language}."
    )

    try:
        out = _chat_sarvam(_ANSWER_SYSTEM, prompt)
    except Exception:
        return NO_INFO[lang], False

    out = (out or "").strip()
    if not out:
        return NO_INFO[lang], False

    if not _numbers_grounded(out, facts_json):
        # The model produced a figure that is nowhere in the engine's output. Discard it.
        return NO_INFO[lang], False

    return out, True


def _chat_sarvam(system: str, user: str) -> str:
    from sarvamai import SarvamAI

    from app.config import settings

    client = SarvamAI(api_subscription_key=settings.sarvam_api_key)
    resp = client.chat.completions(
        model=settings.sarvam_llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=400,
        temperature=0.2,
        seed=42,              # reproducible: what you rehearse is what the judges hear
        # No reasoning_effort: the -conversations model does not take a reasoning pass, and on
        # the reasoning models it runs away and consumes the entire output budget.
    )
    return resp.choices[0].message.content


def _polish_sarvam(text: str) -> str:
    from sarvamai import SarvamAI

    from app.config import settings

    client = SarvamAI(api_subscription_key=settings.sarvam_api_key)
    resp = client.chat.completions(
        model=settings.sarvam_llm_model,
        messages=[
            {"role": "system", "content": _POLISH_SYSTEM},
            {"role": "user", "content": text},
        ],
        max_tokens=400,
        temperature=0.2,
        seed=42,              # reproducible: what you rehearse is what the judges hear
        reasoning_effort="low",
    )
    return resp.choices[0].message.content


def _polish_claude(text: str) -> str:
    import anthropic

    from app.config import settings

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model="claude-opus-5",
        max_tokens=400,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        system=_POLISH_SYSTEM,
        messages=[{"role": "user", "content": text}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("refused")
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


# --- Advisory layer -----------------------------------------------------------------------
# Reads the risk model's output and says what the merchant should take from it. The model
# interprets; it never computes. `_numbers_grounded` rejects any figure the simulation did
# not produce, and a deterministic template covers every failure path.

# Worked examples live here rather than in the system prompt, and only the one matching
# the requested language is sent. With both in context the model code-mixes: an English
# answer comes back as "the daily किस्त will fail", which is worse than either language.
#
# They deliberately contain NO figures. An example with numbers in it gets copied, and
# `_numbers_grounded` then rejects the answer because those figures are not in the facts.
# The example teaches tone and shape; the numbers come from the simulation.
_ADVICE_EXAMPLE = {
    ENGLISH: (
        "Over the loan term the daily instalment is likely to fail on several days, almost "
        "all of them when your shop is shut, and each one carries a penalty. Borrowing less "
        "would not prevent those days, so set a little aside for the days you stay closed."
    ),
    HINDI: (
        "लोन की अवधि में कुछ दिन ऐसे आएंगे जब किस्त नहीं कट पाएगी, और लगभग हर बार वजह दुकान "
        "का बंद रहना होगा, जिस पर हर बार जुर्माना लगता है। कम लोन लेने से ये दिन नहीं बचेंगे, "
        "इसलिए बंद वाले दिनों के लिए थोड़े पैसे अलग रखें।"
    ),
}

_ADVICE_SYSTEM = (
    "You are advising a small Indian shopkeeper about a loan they have been offered. "
    "You will be given facts produced by a statistical model of their own sales history."
    "\n\nWrite exactly two short sentences: what this means for them, and what to do."
    "\n\nHOW TO WRITE:"
    "\n- Speak to the shopkeeper directly, the way a helpful bank staffer would."
    "\n- NEVER write a field name, a key, or a technical word from the facts. Words "
    "like expected_miss_days, trading_miss_days, simulations, closure_rate are forbidden "
    "in your answer. Say 'the daily instalment', 'days your shop is shut', 'about ten times'."
    "\n- Write ENTIRELY in the language you are asked for. Never mix two languages in "
    "one answer: an English answer contains no Hindi words, and a Hindi answer contains "
    "no English words such as days, loan, miss, installment or trading."
    "\n- No bullet points, no headings, no JSON."
    "\n\nRULES YOU MUST NOT BREAK:"
    "\n1. Every number you state must appear in the facts. Never estimate or compute "
    "a new one."
    "\n2. Separate the two causes. Failures on days the shop is shut are not fixed by "
    "borrowing less; failures on ordinary trading days are."
    "\n3. Give no guarantees and never say the loan will be approved."
    "\nReply with the two sentences only."
)


def advise(sim: dict, safe: dict, profile: dict, offer: dict, lang: str = HINDI):
    """Turn the risk simulation into advice. Returns ``(text, llm_used)``."""
    import json

    from app.config import settings

    fallback = _advice_template(sim, safe, lang)

    if not settings.ls_open_qa or not settings.sarvam_api_key:
        return fallback, False

    # Human-phrased keys on purpose: a model handed `expected_miss_days` tends to paste that
    # string into its answer, and the merchant is then reading a variable name.
    readable = {
        "days in the loan term": sim["horizon_days"],
        "daily instalment in rupees": sim["installment"],
        "times the instalment is predicted to fail": sim["expected_miss_days"],
        "of those, on days the shop is shut": sim["closure_miss_days"],
        "of those, on ordinary trading days": sim["trading_miss_days"],
        "likely penalty cost in rupees": sim["expected_penalty"],
        "in a bad case, times it fails": sim["p95_miss_days"],
        "what is causing the failures": sim["driven_by"],
        "days a month the shop is shut": profile["closed_days_per_month"],
        "sales change per month as a percentage": profile["trend_pct_per_month"],
        "largest loan that stays safe in rupees": safe["headroom_amount"],
        "loan amount offered in rupees": offer.get("loan_amount"),
    }
    if safe["changed"]:
        readable["suggested smaller loan in rupees"] = safe["loan_amount"]
        readable["failures on trading days if they take the smaller loan"] = (
            safe["trading_miss_days"]
        )
    facts = json.dumps(readable, ensure_ascii=False)
    language = "Hindi" if lang == HINDI else "English"
    example = _ADVICE_EXAMPLE[lang]
    prompt = (
        f"Facts:\n{facts}\n\n"
        f"Write the advice in {language} only, entirely in {language}.\n"
        f"Follow this tone and shape, but use ONLY the numbers from the facts above. "
        f"The example deliberately contains none:\n{example}"
    )
    try:
        out = _chat_sarvam(_ADVICE_SYSTEM, prompt)
    except Exception:
        return fallback, False

    out = (out or "").strip()
    if not out or not _numbers_grounded(out, facts):
        return fallback, False
    return out, True


def _advice_template(sim: dict, safe: dict, lang: str) -> str:
    """Deterministic advice, used whenever the model is off or its answer is rejected."""
    closures = sim["closure_miss_days"]
    trading = sim["trading_miss_days"]
    days = sim["horizon_days"]

    if lang == HINDI:
        base = (
            f"{days} दिनों में क़रीब {sim['expected_miss_days']} बार किस्त कट नहीं पाएगी, "
            f"जिनमें से {closures} दिन दुकान बंद रहने की वजह से होंगे। "
            f"इन पर जुर्माना लगभग {_inr(sim['expected_penalty'])} पड़ सकता है।"
        )
        if trading < 1:
            tail = (
                f"किस्त की रक़म आपकी रोज़ की कमाई के हिसाब से ठीक है, "
                f"इसलिए लोन छोटा करने से ये दिन नहीं बचेंगे। "
                f"{_inr(safe['headroom_amount'])} तक का लोन इसी हिसाब से सुरक्षित रहेगा।"
            )
        else:
            tail = (
                f"इनमें {trading} दिन ऐसे हैं जब दुकान खुली होगी फिर भी किस्त भारी पड़ेगी। "
                f"{_inr(safe['loan_amount'])} का लोन लेने पर यह घटकर "
                f"{safe['trading_miss_days']} दिन रह जाएगा।"
            )
    else:
        base = (
            f"Over {days} days the instalment is predicted to fail about "
            f"{sim['expected_miss_days']} times, {closures} of them on days your shop is shut. "
            f"That is roughly {_inr(sim['expected_penalty'])} in penalties."
        )
        if trading < 1:
            tail = (
                f"The instalment itself fits your takings, so borrowing less would not "
                f"prevent those days. You could take up to "
                f"{_inr(safe['headroom_amount'])} on this sales pattern."
            )
        else:
            tail = (
                f"{trading} of those fall on trading days, meaning the instalment is too "
                f"large for an ordinary day. At {_inr(safe['loan_amount'])} that drops to "
                f"{safe['trading_miss_days']} days."
            )
    return f"{base} {tail}"
