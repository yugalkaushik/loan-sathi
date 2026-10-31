"""Loan Saathi API.

One FastAPI app, one process, one port. It serves the JSON API, the generated audio, and the
single-page UI, so the demo is `uvicorn app.main:app` and nothing else.

Shape of every response that carries a narration:

    {"numbers": {...from engine...}, "text": "...", "audio": "/audio/x.wav"|null,
     "llm_used": false}

`numbers` always comes from ``app.engine``. `text` always comes from ``app.narrate`` templates.
Audio is a nice-to-have that silently degrades to ``null``.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import document, engine, intent, narrate, risk, voice
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("loan_saathi")

app = FastAPI(
    title="Loan Saathi",
    version="1.0.0",
    description=(
        "A merchant loan that explains itself and stress-tests itself.\n\n"
        "**All data served by this API is synthetic.** Every number is computed by the "
        "deterministic simulator in `app/engine.py`; the language model never calculates "
        "anything and never decides anything about credit."
    ),
)

# --- data -------------------------------------------------------------------------------
# One small JSON file, loaded once. Swapping in a real Paytm settlement feed and lender offer
# API means replacing this function, nothing else.


def _load() -> dict:
    try:
        return json.loads(settings.data_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(
            f"{settings.data_file} is missing. Run: python scripts/gen_data.py"
        ) from None


DATA = _load()
MERCHANT = DATA["merchant"]
SETTLEMENTS: list[float] = DATA["settlements"]["daily"]

# The offer in play. Starts as the bundled sample and is replaced when a merchant uploads a
# real loan document. The settlement history never changes: that is the merchant's own data,
# and only the lender's terms come from the document.
OFFER: dict = dict(DATA["offer"])
BUNDLED_OFFER: dict = dict(DATA["offer"])
OFFER_LOADED = False

# In-memory, append-only consent + action trail. A list is enough to show rows landing on
# screen during the demo; it is not pretending to be durable storage.
AUDIT: list[dict] = []

# Weekday of the first settlement, so the risk model labels Monday as Monday. Without it the
# learned weekday rhythm is still correct in shape but attached to the wrong day names.
try:
    FIRST_WEEKDAY = date.fromisoformat(DATA["settlements"]["start_date"]).weekday()
except (KeyError, ValueError):
    FIRST_WEEKDAY = 0

# The learned profile depends only on the settlement history, which never changes during a
# session, so it is computed once at startup rather than on every request.
PROFILE = risk.decompose(SETTLEMENTS, FIRST_WEEKDAY)


def _audit(action: str, detail: dict) -> dict:
    row = {
        "seq": len(AUDIT) + 1,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "merchant_id": MERCHANT["id"],
        "action": action,
        "detail": detail,
    }
    AUDIT.append(row)
    log.info("audit %s %s", action, detail)
    return row


Lang = Literal["hi", "en"]


def _facts(lang: Lang) -> dict:
    """Everything the LLM is allowed to know, all of it computed by the engine.

    Deliberately flat and small: it is also the allow-list the numeric guard checks answers
    against, so anything not in here cannot legally appear in a reply.
    """
    installment = OFFER["daily_installment"]
    base = engine.simulate(SETTLEMENTS, installment)
    return {
        "merchant": {k: MERCHANT[k] for k in ("name", "city", "category")},
        "offer": {
            "lender": OFFER["lender_name"],
            "loan_amount": OFFER["loan_amount"],
            "daily_installment": installment,
            "tenor_days": OFFER["tenor_days"],
            "total_payable": OFFER["total_payable"],
            "processing_fee": OFFER["processing_fee"],
            "interest_rate_pa": OFFER["interest_rate_pa"],
            "repayment": "auto-deducted from the merchant's daily Paytm settlement",
            "foreclosure_charges": "nil",
        },
        "settlements": {
            "days_of_history": len(SETTLEMENTS),
            "average_daily": base["avg_daily"],
            "lowest_day": min(SETTLEMENTS),
            "highest_day": max(SETTLEMENTS),
            "days_below_installment": base["shortfall_days"],
        },
        "today": base,
        "if_sales_fall_30_pct": engine.simulate(SETTLEMENTS, installment, -0.30),
        "if_sales_fall_50_pct": engine.simulate(SETTLEMENTS, installment, -0.50),
        "smaller_loan_option": engine.rightsize(
            SETTLEMENTS, OFFER, settings.ls_rightsize_threshold
        ),
        "predicted_risk": risk.simulate_risk(
            SETTLEMENTS, installment, int(OFFER["tenor_days"]),
            600, settings.ls_risk_seed, FIRST_WEEKDAY, PROFILE,
        ),
        "trading_behaviour": PROFILE.as_dict(),
        "repayment_trend": engine.coach(
            SETTLEMENTS, installment, settings.ls_coach_dip_fraction
        ),
        "rules": [
            "All data here is synthetic demo data, not real Paytm data.",
            "Loan approval is the lender's decision, never Loan Saathi's.",
            "Money and consent actions require an in-app PIN confirmation.",
        ],
    }


def _narrated(text: str, lang: Lang, numbers: dict | None = None, speak: bool = True) -> dict:
    """Apply the optional LLM polish, optionally synthesise audio, and shape the response.

    ``speak`` exists to protect a limited credit balance. Dragging the what-if slider fires
    a request per stop and flipping the language re-renders everything; none of that is
    played, so none of it should be billed. The UI sends ``speak: false`` for those, and
    true only when a button or a question was used."""
    final, llm_used = narrate.polish(text, settings.ls_narrator, lang)
    return {
        "numbers": numbers or {},
        "text": final,
        "audio": voice.speak(final, lang) if speak else None,
        "llm_used": llm_used,
        "narrator": settings.ls_narrator,
    }


# --- requests ---------------------------------------------------------------------------


class SimulateIn(BaseModel):
    # Negative fraction: -0.30 is a 30% sales drop. See app/engine.py.
    shock_pct: float = Field(0.0, le=0.0, gt=-1.0, examples=[-0.30])
    shock_days: int = Field(30, ge=7, le=90)
    lang: Lang = "hi"
    # The UI fetches three simulations just to fill the burden tiles. Nobody hears those, so
    # they ask for numbers only: no LLM call, no TTS, no latency on first paint.
    narrate_: bool = Field(True, alias="narrate")
    # False while dragging the slider or switching language: render text, bill no audio.
    speak: bool = True

    model_config = {"populate_by_name": True}


class RightsizeIn(BaseModel):
    shock_pct: float = Field(-0.30, le=0.0, gt=-1.0)
    ceiling: float = Field(default_factory=lambda: settings.ls_rightsize_threshold, gt=0, le=1)
    lang: Lang = "hi"
    speak: bool = True


class ConfirmIn(BaseModel):
    pin: str = Field(..., min_length=4, max_length=6)
    loan_amount: int = Field(..., gt=0)
    daily_installment: int = Field(..., gt=0)
    lang: Lang = "hi"


class AskIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    lang: Lang = "hi"
    speak: bool = True


# --- endpoints --------------------------------------------------------------------------


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    """Liveness plus which optional features are actually switched on."""
    return {
        "ok": True,
        "narrator": settings.ls_narrator,
        "voice_enabled": settings.voice_enabled,
        "doc_ai_enabled": settings.ls_doc_ai and settings.voice_enabled,
        "offer_source": OFFER.get("source", "bundled sample"),
        "settlement_days": len(SETTLEMENTS),
        "synthetic_data": True,
    }


@app.get("/api/demo", tags=["data"])
def demo() -> dict:
    """Everything the UI needs for first paint: merchant, offer, KFS, settlement series."""
    base = engine.simulate(SETTLEMENTS, OFFER["daily_installment"])
    return {
        "disclaimer": DATA["_disclaimer"],
        "merchant": MERCHANT,
        "offer": OFFER,
        "offer_loaded": OFFER_LOADED,
        "settlements": DATA["settlements"],
        "baseline": base,
        "voice_enabled": settings.voice_enabled,
        "assumptions": {
            "statistic": "mean of 90 days of settlement ('average day', not 'typical day')",
            "passthrough": "sales to settlement passthrough assumed 1:1",
            "rightsize_ceiling_pct": round(settings.ls_rightsize_threshold * 100, 1),
            "note": "Demo assumptions, not Paytm or lender rules.",
        },
    }


@app.post("/api/explain", tags=["narration"])
def explain(lang: Lang = Body("hi", embed=True), speak: bool = Body(True, embed=True)) -> dict:
    """Beat 1, read the offer and its Key Facts aloud."""
    base = engine.simulate(SETTLEMENTS, OFFER["daily_installment"])
    text = narrate.explain_offer(OFFER, base, lang)
    return _narrated(text, lang, base, speak)


@app.post("/api/simulate", tags=["narration"])
def simulate(body: SimulateIn) -> dict:
    """Beat 2, the stress test, replayed over the merchant's own settlements."""
    base = engine.simulate(SETTLEMENTS, OFFER["daily_installment"], 0.0, body.shock_days)
    sim = engine.simulate(
        SETTLEMENTS, OFFER["daily_installment"], body.shock_pct, body.shock_days
    )
    if not body.narrate_:
        return {"numbers": sim, "baseline": base, "text": "", "audio": None, "llm_used": False}

    text = narrate.explain_shock(sim, base, body.lang)
    out = _narrated(text, body.lang, sim, body.speak)
    out["baseline"] = base
    return out


@app.post("/api/rightsize", tags=["narration"])
def rightsize(body: RightsizeIn) -> dict:
    """Beat 3, the largest loan that survives the shock."""
    rs = engine.rightsize(SETTLEMENTS, OFFER, body.ceiling, body.shock_pct)
    text = narrate.explain_rightsize(rs, OFFER, body.lang)
    return _narrated(text, body.lang, rs, body.speak)


@app.get("/api/coach", tags=["narration"])
def coach(lang: Lang = "hi", speak: bool = True) -> dict:
    """Beat 5, early warning on a settlement dip, before an installment is missed."""
    c = engine.coach(SETTLEMENTS, OFFER["daily_installment"], settings.ls_coach_dip_fraction)
    text = narrate.explain_coach(c, lang)
    out = _narrated(text, lang, c, speak)
    if c["handoff_suggested"]:
        out["handoff"] = _audit("restructure_requested", {
            "tier": c["tier"],
            "drop_pct": c["drop_pct"],
            "routed_to": "human agent, Paytm merchant support",
            "decided_by_ai": False,
        })
    return out


@app.post("/api/confirm", tags=["consent"])
def confirm(body: ConfirmIn) -> dict:
    """Beat 4, in-app consent. Voice alone is never enough (brief rule 4)."""
    if body.pin != DATA["demo_pin"]:
        # Recorded either way: a failed consent attempt is exactly what an audit log is for.
        _audit("consent_failed", {"reason": "wrong_pin"})
        raise HTTPException(status_code=401, detail="Incorrect PIN")

    row = _audit("consent_recorded", {
        "offer_id": OFFER["offer_id"],
        "lender": OFFER["lender_name"],
        "loan_amount": body.loan_amount,
        "daily_installment": body.daily_installment,
        "method": "in-app PIN",
        "decided_by_ai": False,
    })
    text = (
        f"पुष्टि हो गई। {OFFER['lender_name']} को आपका अनुरोध भेज दिया गया है। "
        f"मंज़ूरी का फ़ैसला लेंडर करेगा, कोई AI नहीं।"
        if body.lang == "hi" else
        f"Confirmed. Your request has been sent to {OFFER['lender_name']}. "
        f"The approval decision is the lender's, not an AI's."
    )
    out = _narrated(text, body.lang)
    out["audit"] = row
    return out


@app.post("/api/ask", tags=["voice"])
def ask(body: AskIn) -> dict:
    """Typed question in, answer out. The same path voice uses, minus the microphone.

    This exists so a dead mic or failed transcription never costs us the demo.
    """
    parsed = intent.parse(body.text)
    return _answer(parsed, body.text, body.lang, body.speak)


@app.post("/api/voice/ask", tags=["voice"])
async def voice_ask(
    audio: UploadFile = File(...),
    lang: Lang = Form("hi"),
) -> JSONResponse:
    """Recorded audio in, spoken answer out: STT, then the identical deterministic path."""
    raw = await audio.read()
    transcript = voice.transcribe(
        raw, audio.filename or "clip.webm", lang, audio.content_type
    )
    if not transcript:
        return JSONResponse(
            status_code=503,
            content={
                "error": "transcription_unavailable",
                "hint": "Type the question instead, /api/ask takes the same path.",
            },
        )
    parsed = intent.parse(transcript)
    out = _answer(parsed, transcript, lang)
    out["transcript"] = transcript
    return JSONResponse(out)


def _answer(parsed: dict, asked: str, lang: Lang, speak: bool = True) -> dict:
    """Route a parsed intent to the engine. The LLM never makes this decision either."""
    if parsed["intent"] == "shock":
        return simulate(SimulateIn(shock_pct=parsed["shock_pct"], lang=lang, speak=speak)) | {
            "intent": parsed["intent"], "asked": asked,
        }
    if parsed["intent"] == "rightsize":
        return rightsize(RightsizeIn(lang=lang, speak=speak)) | {
            "intent": parsed["intent"], "asked": asked,
        }
    if parsed["intent"] == "coach":
        return coach(lang, speak) | {"intent": parsed["intent"], "asked": asked}
    if parsed["intent"] == "explain":
        return explain(lang, speak) | {"intent": parsed["intent"], "asked": asked}

    # Out of scope for the deterministic parser. With LS_OPEN_QA on, the LLM answers from the
    # engine's facts; otherwise, and on any failure, this is the honest fallback (brief rule 3).
    text, llm_used = narrate.answer_question(asked, _facts(lang), lang)
    out = _narrated(text, lang, None, speak)
    out["llm_used"] = llm_used
    out["intent"] = "unknown"
    out["asked"] = asked
    return out


@app.post("/api/document", tags=["document"])
async def read_document(file: UploadFile = File(...)) -> JSONResponse:
    """Read a lender's loan document and compute from what it actually says.

    This is the AI step a calculator cannot do: the merchant is handed a Key Fact Statement in
    English, and Sarvam Doc AI turns it into the fields the engine needs. The deterministic
    engine then calculates over the existing sales history; this upload changes loan terms only.
    """
    global OFFER, OFFER_LOADED

    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        return JSONResponse(status_code=413, content={
            "ok": False, "reason": "That file is larger than 10 MB."})

    offer, reason = document.extract_offer(
        raw, file.filename or "document.pdf", file.content_type or "application/pdf"
    )

    if offer is None:
        # Never a dead end: say what went wrong and keep the offer already on screen.
        log.info("document rejected: %s", reason)
        return JSONResponse(status_code=200, content={
            "ok": False, "reason": reason, "offer": OFFER})

    OFFER = offer
    OFFER_LOADED = True
    _audit("document_read", {
        "filename": file.filename,
        "lender": offer["lender_name"],
        "loan_amount": offer["loan_amount"],
        "daily_installment": offer["daily_installment"],
        "read_by": "Sarvam Doc AI",
        "computed_by": "deterministic engine, not a language model",
    })

    base = engine.simulate(SETTLEMENTS, offer["daily_installment"])
    return JSONResponse({
        "ok": True,
        "offer": offer,
        "baseline": base,
        "sales_history_days": len(SETTLEMENTS),
        "reason": "ok",
    })


@app.post("/api/document/reset", tags=["document"])
def reset_document() -> dict:
    """Go back to the bundled sample offer."""
    global OFFER, OFFER_LOADED
    OFFER = dict(BUNDLED_OFFER)
    OFFER_LOADED = False
    base = engine.simulate(SETTLEMENTS, OFFER["daily_installment"])
    return {"ok": True, "offer": OFFER, "baseline": base}


@app.get("/api/risk", tags=["risk"])
def risk_forecast(lang: Lang = "hi", speak: bool = False, shock_pct: float = 0.0) -> dict:
    """Predict how often this loan's auto-debit will fail over its full term.

    This is the part of the product that has an opinion. Everything else either reports a
    figure from the document or divides two numbers the merchant already had. Here a model
    learns how this merchant trades, simulates the loan's whole term a few thousand times,
    and says what is likely to happen.

    The language model is not involved in any of it: the simulation produces the numbers and
    the model is handed them afterwards to write two sentences of advice.
    """
    offer = OFFER
    sim = risk.simulate_risk(
        SETTLEMENTS,
        offer["daily_installment"],
        horizon=int(offer["tenor_days"]),
        sims=settings.ls_risk_sims,
        seed=settings.ls_risk_seed,
        first_weekday=FIRST_WEEKDAY,
        profile=PROFILE,
        sales_shock=shock_pct,
    )
    safe = risk.safe_amount(
        SETTLEMENTS, offer,
        max_trading_misses=settings.ls_max_trading_misses,
        seed=settings.ls_risk_seed,
        first_weekday=FIRST_WEEKDAY,
    )
    profile = PROFILE.as_dict()

    text, llm_used = narrate.advise(sim, safe, profile, offer, lang)
    out = _narrated(text, lang, sim, speak)
    out["llm_used"] = llm_used
    # The advisory uses the chat model, not LS_NARRATOR, so report which one actually wrote it.
    out["advisor"] = settings.sarvam_llm_model if llm_used else "deterministic template"
    out["profile"] = profile
    out["safe"] = safe
    out["forecast"] = [
        round(v * (1 + shock_pct))
        for v in risk.forecast(PROFILE, int(offer["tenor_days"]), FIRST_WEEKDAY)
    ]
    return out


@app.get("/api/audit", tags=["consent"])
def audit() -> dict:
    """The trail, exposed on purpose, it is part of the pitch, not an internal detail."""
    return {"merchant_id": MERCHANT["id"], "count": len(AUDIT), "rows": AUDIT}


@app.get("/audio/{name}", include_in_schema=False)
def audio_file(name: str):
    path = (settings.audio_dir / name).resolve()
    # Keep the path inside data/audio even if `name` contains traversal segments.
    if not str(path).startswith(str(settings.audio_dir.resolve())) or not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="audio/wav")


# The UI. Mounted last so it never shadows an /api route.
app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
