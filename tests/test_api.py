"""Integration tests for the HTTP surface.

These drive the real FastAPI app through `TestClient`, so they cover routing, request
validation, response shape and the demo's actual flow. `test_engine.py` proves the arithmetic;
this file proves the thing a judge will click actually works.

Nothing here needs an API key or a network. With `LS_NARRATOR=template` and no `SARVAM_API_KEY`
the whole app runs offline, which is the configuration the demo is given.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import AUDIT, app

client = TestClient(app)

PIN = "1234"


@pytest.fixture(autouse=True)
def _clear_audit():
    """The audit log is module-level state, so reset it between tests."""
    AUDIT.clear()
    yield
    AUDIT.clear()


# --- meta ------------------------------------------------------------------------------


def test_health_reports_what_is_switched_on():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["settlement_days"] == 90
    assert body["synthetic_data"] is True


def test_openapi_schema_builds():
    """A malformed pydantic model would only surface here, not in the engine tests."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for route in (
        "/api/health", "/api/demo", "/api/explain", "/api/simulate",
        "/api/rightsize", "/api/coach", "/api/confirm", "/api/ask",
        "/api/voice/ask", "/api/audit",
    ):
        assert route in paths, f"{route} missing from the OpenAPI schema"


def test_single_page_and_assets_are_served():
    assert client.get("/").status_code == 200
    assert client.get("/styles.css").status_code == 200
    assert client.get("/app.js").status_code == 200


# --- demo payload ----------------------------------------------------------------------


def test_demo_payload_has_everything_first_paint_needs():
    body = client.get("/api/demo").json()
    assert body["merchant"]["name"]
    assert len(body["settlements"]["daily"]) == 90
    assert body["offer"]["daily_installment"] == 700
    assert body["offer"]["kfs"], "the Key Facts table would render empty"
    assert "SYNTHETIC" in body["disclaimer"].upper()
    # The assumptions must travel with the data so the UI can label them.
    assert body["assumptions"]["rightsize_ceiling_pct"] == 15.0


# --- simulate --------------------------------------------------------------------------


@pytest.mark.parametrize("shock, expected", [(0.0, 11.7), (-0.30, 16.7), (-0.50, 23.3)])
def test_simulate_returns_the_deck_figures(shock, expected):
    r = client.post("/api/simulate", json={"shock_pct": shock, "shock_days": 30, "lang": "hi"})
    assert r.status_code == 200
    assert r.json()["numbers"]["burden_pct"] == expected


def test_simulate_narration_quotes_the_engine_numbers():
    body = client.post("/api/simulate", json={"shock_pct": -0.30, "lang": "en"}).json()
    n = body["numbers"]
    assert f"{n['burden_pct']}%" in body["text"]


def test_narrate_false_skips_text_and_audio_but_keeps_numbers():
    """The UI fills three burden tiles this way; it must not trigger TTS or an LLM call."""
    quiet = client.post(
        "/api/simulate",
        json={"shock_pct": -0.30, "shock_days": 30, "lang": "hi", "narrate": False},
    ).json()
    loud = client.post(
        "/api/simulate", json={"shock_pct": -0.30, "shock_days": 30, "lang": "hi"}
    ).json()

    assert quiet["text"] == ""
    assert quiet["audio"] is None
    assert quiet["numbers"] == loud["numbers"], "the numbers must not depend on narration"


@pytest.mark.parametrize("bad", [{"shock_pct": 0.5}, {"shock_pct": -1.5}, {"shock_days": 3}])
def test_simulate_rejects_out_of_range_input(bad):
    assert client.post("/api/simulate", json=bad).status_code == 422


# --- rightsize -------------------------------------------------------------------------


def test_rightsize_actually_reduces_the_offer():
    """Guards the demo's third beat. A no-op here means the beat shows nothing."""
    body = client.post("/api/rightsize", json={"shock_pct": -0.30, "lang": "en"}).json()
    n = body["numbers"]
    assert n["changed"] is True, "right-size became a no-op; check LS_RIGHTSIZE_THRESHOLD"
    assert n["loan_amount"] < 100000
    assert n["daily_installment"] < 700
    assert n["burden_pct"] <= n["ceiling_pct"] + 0.1
    assert "PIN" in body["text"] or "पुष्टि" in body["text"]


# --- coach -----------------------------------------------------------------------------


def test_coach_fires_and_routes_to_a_human():
    body = client.get("/api/coach", params={"lang": "en"}).json()
    assert body["numbers"]["alert"] is True, "the demo's coach beat would show nothing"
    assert body["handoff"]["detail"]["decided_by_ai"] is False
    assert "human" in body["handoff"]["detail"]["routed_to"].lower()


# --- consent ---------------------------------------------------------------------------


def test_wrong_pin_is_rejected_and_still_audited():
    r = client.post(
        "/api/confirm", json={"pin": "9999", "loan_amount": 89000, "daily_installment": 623}
    )
    assert r.status_code == 401
    rows = client.get("/api/audit").json()["rows"]
    assert rows[-1]["action"] == "consent_failed"


def test_correct_pin_records_consent():
    r = client.post(
        "/api/confirm",
        json={"pin": PIN, "loan_amount": 89000, "daily_installment": 623, "lang": "en"},
    )
    assert r.status_code == 200
    detail = r.json()["audit"]["detail"]
    assert detail["loan_amount"] == 89000
    assert detail["method"] == "in-app PIN"
    assert detail["decided_by_ai"] is False


def test_audit_is_append_only_and_ordered():
    client.post("/api/confirm", json={"pin": "0000", "loan_amount": 1, "daily_installment": 1})
    client.post("/api/confirm", json={"pin": PIN, "loan_amount": 89000, "daily_installment": 623})
    rows = client.get("/api/audit").json()["rows"]
    assert [r["seq"] for r in rows] == list(range(1, len(rows) + 1))


# --- ask -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, intent",
    [
        ("अगर बिक्री 30% गिरी तो?", "shock"),
        ("what if sales drop 30 percent", "shock"),
        ("छोटा लोन सुझाओ", "rightsize"),
        ("मेरा कारोबार कैसा चल रहा है", "coach"),
        ("explain the offer", "explain"),
    ],
)
def test_ask_routes_to_the_right_engine_call(text, intent):
    body = client.post("/api/ask", json={"text": text, "lang": "hi"}).json()
    assert body["intent"] == intent
    assert body["text"], "every answer must carry a sentence"


def test_ask_admits_when_it_does_not_know():
    """Brief rule 3: never guess, say so and offer a human."""
    body = client.post(
        "/api/ask", json={"text": "what is the weather in Mumbai", "lang": "en"}
    ).json()
    assert body["intent"] == "unknown"
    assert "don't have that information" in body["text"]


def test_spoken_question_drives_the_stress_test():
    body = client.post("/api/ask", json={"text": "अगर बिक्री 30% गिरी तो?", "lang": "hi"}).json()
    assert body["numbers"]["burden_pct"] == 16.7


def test_voice_endpoint_degrades_to_the_text_box_without_a_key():
    """With no Sarvam key the mic cannot work, and the UI must be told to fall back."""
    r = client.post(
        "/api/voice/ask",
        files={"audio": ("clip.webm", b"not-really-audio", "audio/webm")},
        data={"lang": "hi"},
    )
    assert r.status_code == 503
    assert "/api/ask" in r.json()["hint"]


# --- the guarantee ---------------------------------------------------------------------


def test_no_endpoint_invents_a_number_with_the_default_narrator():
    """Every narration must come from a template, not a model, in the shipped configuration."""
    calls = [
        client.post("/api/explain", json={"lang": "hi"}),
        client.post("/api/simulate", json={"shock_pct": -0.30, "lang": "hi"}),
        client.post("/api/rightsize", json={"shock_pct": -0.30, "lang": "hi"}),
        client.get("/api/coach", params={"lang": "hi"}),
    ]
    for r in calls:
        assert r.status_code == 200
        assert r.json()["llm_used"] is False
        assert r.json()["narrator"] == "template"


# --- the full demo, start to finish ------------------------------------------------------


def test_the_three_minute_demo_runs_end_to_end():
    """Walks docs/DEMO-SCRIPT.md beat by beat. If this passes, the demo works."""
    # Beat 1: explain the offer
    explain = client.post("/api/explain", json={"lang": "hi"}).json()
    assert "1,26,000" in explain["text"]

    # Beat 2: the merchant asks, in Hindi, what a 30% fall does
    shock = client.post("/api/ask", json={"text": "अगर बिक्री 30% गिरी तो?", "lang": "hi"}).json()
    assert shock["numbers"]["burden_pct"] == 16.7
    assert shock["numbers"]["shortfall_days"] >= 1

    # Beat 3: right-size to something survivable
    rs = client.post("/api/rightsize", json={"shock_pct": -0.30, "lang": "hi"}).json()
    assert rs["numbers"]["changed"] is True
    smaller = rs["numbers"]

    # Beat 4: consent, with a PIN, in the app
    confirm = client.post(
        "/api/confirm",
        json={
            "pin": PIN,
            "loan_amount": smaller["loan_amount"],
            "daily_installment": smaller["daily_installment"],
            "lang": "hi",
        },
    )
    assert confirm.status_code == 200

    # Beat 5: the coach spots the dip and asks a human to step in
    coach = client.get("/api/coach", params={"lang": "hi"}).json()
    assert coach["numbers"]["handoff_suggested"] is True

    # The trail shows consent and the handoff, in order.
    actions = [r["action"] for r in client.get("/api/audit").json()["rows"]]
    assert "consent_recorded" in actions
    assert "restructure_requested" in actions


# --- open Q&A (LS_OPEN_QA) ---------------------------------------------------------------
# The guard is the point of this feature, so it is tested far more than the happy path.


def test_unknown_still_falls_back_when_the_flag_is_off():
    """The flag is the revert path. With it off, behaviour must be exactly as before."""
    from app.config import settings

    assert settings.ls_open_qa is False, "conftest pins this off for the suite"
    body = client.post("/api/ask", json={"text": "do you like cricket", "lang": "en"}).json()
    assert body["intent"] == "unknown"
    assert "don't have that information" in body["text"]
    assert body["llm_used"] is False


def test_answer_question_is_a_no_op_without_a_key():
    """conftest blanks the key, so this must never reach the network."""
    from app import narrate

    text, used = narrate.answer_question("anything at all", {"offer": {}}, "en")
    assert used is False
    assert text == narrate.NO_INFO["en"]


def test_facts_handed_to_the_llm_are_all_engine_output():
    """The grounding set must carry the real figures, since it doubles as the allow-list."""
    from app.main import _facts

    f = _facts("en")
    assert f["offer"]["daily_installment"] == 700
    assert f["today"]["burden_pct"] == 11.7
    assert f["if_sales_fall_30_pct"]["burden_pct"] == 16.7
    assert f["if_sales_fall_50_pct"]["burden_pct"] == 23.3
    assert f["smaller_loan_option"]["changed"] is True
    assert f["repayment_trend"]["alert"] is True
    assert any("synthetic" in r.lower() for r in f["rules"])


class TestNumericGuard:
    """Every number in a free-form answer must already exist in the supplied facts."""

    FACTS = '{"installment": 700, "total": 126000, "burden_pct": 16.7, "days": 3}'

    def test_accepts_an_answer_using_only_supplied_figures(self):
        from app.narrate import _numbers_grounded

        assert _numbers_grounded("Your installment is Rs 700, which is 16.7%.", self.FACTS)

    def test_rejects_an_invented_rupee_figure(self):
        from app.narrate import _numbers_grounded

        assert not _numbers_grounded("You could borrow Rs 500000 instead.", self.FACTS)

    def test_rejects_an_invented_percentage(self):
        from app.narrate import _numbers_grounded

        assert not _numbers_grounded("That would be about 42.5% of your takings.", self.FACTS)

    def test_accepts_devanagari_digits_for_a_supplied_figure(self):
        from app.narrate import _numbers_grounded

        assert _numbers_grounded("रोज़ की किस्त ₹७०० है।", self.FACTS)

    def test_accepts_lakh_grouped_formatting(self):
        from app.narrate import _numbers_grounded

        assert _numbers_grounded("You will repay Rs 1,26,000 in total.", self.FACTS)

    def test_allows_small_counting_words(self):
        """'3 days' or '2 reasons' are prose, not financial claims."""
        from app.narrate import _numbers_grounded

        assert _numbers_grounded("There were 3 days like that, for 2 reasons.", self.FACTS)

    def test_still_rejects_a_large_bare_number(self):
        from app.narrate import _numbers_grounded

        assert not _numbers_grounded("Roughly 85000 rupees.", self.FACTS)


def test_an_llm_failure_degrades_to_the_fallback(monkeypatch):
    """A dead API, a refusal or a timeout must never surface as an error."""
    from app import narrate
    from app.config import settings

    monkeypatch.setattr(settings, "ls_open_qa", True)
    monkeypatch.setattr(settings, "sarvam_api_key", "pretend-key")
    monkeypatch.setattr(narrate, "_chat_sarvam", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))

    text, used = narrate.answer_question("what happens if I close for a week?", {"a": 1}, "hi")
    assert used is False
    assert text == narrate.NO_INFO["hi"]


def test_a_hallucinated_number_is_discarded(monkeypatch):
    """The whole point: a plausible answer containing an invented figure must not reach anyone."""
    from app import narrate
    from app.config import settings

    monkeypatch.setattr(settings, "ls_open_qa", True)
    monkeypatch.setattr(settings, "sarvam_api_key", "pretend-key")
    monkeypatch.setattr(
        narrate, "_chat_sarvam",
        lambda *a, **k: "You could comfortably borrow Rs 450000 over 365 days.",
    )

    text, used = narrate.answer_question("how much can I borrow?", {"loan_amount": 100000}, "en")
    assert used is False, "an invented figure was allowed through"
    assert text == narrate.NO_INFO["en"]


def test_a_grounded_answer_is_allowed_through(monkeypatch):
    from app import narrate
    from app.config import settings

    monkeypatch.setattr(settings, "ls_open_qa", True)
    monkeypatch.setattr(settings, "sarvam_api_key", "pretend-key")
    monkeypatch.setattr(
        narrate, "_chat_sarvam",
        lambda *a, **k: "Your daily installment is Rs 700 and you repay Rs 126000 in all.",
    )

    facts = {"daily_installment": 700, "total_payable": 126000}
    text, used = narrate.answer_question("what do I repay?", facts, "en")
    assert used is True
    assert "700" in text


def test_the_scripted_beats_never_touch_the_llm(monkeypatch):
    """Switching open Q&A on must not change a single scripted answer."""
    from app import narrate
    from app.config import settings

    monkeypatch.setattr(settings, "ls_open_qa", True)
    monkeypatch.setattr(settings, "sarvam_api_key", "pretend-key")
    monkeypatch.setattr(
        narrate, "_chat_sarvam",
        lambda *a, **k: pytest.fail("a scripted beat reached the LLM"),
    )

    for text in ("अगर बिक्री 30% गिरी तो?", "छोटा लोन सुझाओ", "मेरा कारोबार कैसा चल रहा है"):
        r = client.post("/api/ask", json={"text": text, "lang": "hi"})
        assert r.status_code == 200
        assert r.json()["llm_used"] is False


# --- document extraction (Sarvam Doc AI) --------------------------------------------------
# The validation is what matters here: a misread document must never silently drive the
# engine, because every figure on screen would then be wrong and look authoritative.


def test_schema_is_valid_for_the_api():
    """Doc AI rejects a schema whose properties lack descriptions."""
    from app.document import KFS_SCHEMA

    assert KFS_SCHEMA["type"] == "object"
    assert KFS_SCHEMA["properties"]
    for name, spec in KFS_SCHEMA["properties"].items():
        assert spec["type"] in ("string", "number", "integer", "boolean", "object", "array"), name
        assert spec.get("description", "").strip(), f"{name} needs a non-empty description"


def test_schema_fields_match_the_offer_the_engine_expects():
    """Extraction output drops into the engine with no translation, so the names must align."""
    from app.document import KFS_SCHEMA
    from app.main import BUNDLED_OFFER

    for field in ("loan_amount", "daily_installment", "tenor_days", "total_payable"):
        assert field in KFS_SCHEMA["properties"]
        assert field in BUNDLED_OFFER


class TestExtractionValidation:
    """`_to_offer` is the gate between a language model and the merchant's numbers."""

    GOOD = {
        "lender_name": "Piramal Capital",
        "loan_amount": 100000, "daily_installment": 700, "tenor_days": 180,
        "total_payable": 126000, "processing_fee": 2360, "interest_rate_pa": 24.0,
    }

    def test_accepts_a_consistent_document(self):
        from app.document import _to_offer

        offer, reason = _to_offer(self.GOOD)
        assert reason == "ok"
        assert offer["loan_amount"] == 100000
        assert offer["daily_installment"] == 700
        assert offer["kfs"], "the on-screen Key Facts table would be empty"

    def test_rejects_figures_that_do_not_add_up(self):
        """700 x 180 is 126,000. A total of 450,000 means something was misread."""
        from app.document import _to_offer

        offer, reason = _to_offer({**self.GOOD, "total_payable": 450000})
        assert offer is None
        assert "do not add up" in reason

    def test_rejects_an_absurd_tenure(self):
        from app.document import _to_offer

        offer, _ = _to_offer({**self.GOOD, "tenor_days": 5, "total_payable": 3500})
        assert offer is None

    def test_rejects_negative_or_zero_amounts(self):
        from app.document import _to_offer

        assert _to_offer({**self.GOOD, "loan_amount": -5000})[0] is None
        assert _to_offer({**self.GOOD, "daily_installment": 0})[0] is None

    def test_rejects_an_installment_larger_than_the_loan(self):
        from app.document import _to_offer

        offer, _ = _to_offer({**self.GOOD, "daily_installment": 200000})
        assert offer is None

    def test_reports_which_fields_were_missing(self):
        from app.document import _to_offer

        offer, reason = _to_offer({"lender_name": "Someone"})
        assert offer is None
        assert "loan amount" in reason

    def test_rejects_a_non_dict_result(self):
        from app.document import _to_offer

        assert _to_offer("not a dict")[0] is None

    def test_parses_figures_the_model_returns_as_text(self):
        """Models often hand back 'Rs. 1,00,000' rather than a bare number."""
        from app.document import _to_offer

        offer, reason = _to_offer({
            **self.GOOD,
            "loan_amount": "Rs. 1,00,000",
            "daily_installment": "Rs. 700",
            "interest_rate_pa": "24.0% per annum",
        })
        assert reason == "ok"
        assert offer["loan_amount"] == 100000
        assert offer["interest_rate_pa"] == 24.0


def test_no_key_means_no_doc_ai_call():
    """conftest blanks credentials, so the suite must never submit a Doc AI job."""
    from app.document import extract_offer

    offer, reason = extract_offer(b"%PDF-1.4 fake", "x.pdf")
    assert offer is None
    assert "Sarvam API key" in reason


def test_upload_failure_keeps_the_current_offer(monkeypatch):
    """A bad document must not leave the demo without an offer."""
    from app import document as doc_mod
    from app.main import BUNDLED_OFFER

    monkeypatch.setattr(doc_mod, "extract_offer", lambda *a, **k: (None, "Unreadable."))
    r = client.post("/api/document", files={"file": ("junk.pdf", b"junk", "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["reason"] == "Unreadable."
    assert body["offer"]["daily_installment"] == BUNDLED_OFFER["daily_installment"]


def test_a_read_document_drives_the_engine_and_is_audited(monkeypatch):
    from app import document as doc_mod

    extracted = {
        "offer_id": "DOC-UPLOAD", "lender_name": "Test NBFC",
        "loan_amount": 50000, "daily_installment": 350, "tenor_days": 180,
        "total_payable": 63000, "processing_fee": 1000, "interest_rate_pa": 22.0,
        "source": "extracted", "kfs": [], "pages_read": 1,
    }
    monkeypatch.setattr(doc_mod, "extract_offer", lambda *a, **k: (dict(extracted), "ok"))

    try:
        r = client.post("/api/document",
                        files={"file": ("kfs.pdf", b"%PDF-1.4", "application/pdf")})
        body = r.json()
        assert body["ok"] is True
        assert body["offer"]["lender_name"] == "Test NBFC"
        # The engine computed from the document's installment, not the bundled one.
        assert body["baseline"]["installment"] == 350
        assert body["baseline"]["burden_pct"] == round(350 / 6000 * 100, 1)

        actions = [row["action"] for row in client.get("/api/audit").json()["rows"]]
        assert "document_read" in actions
    finally:
        client.post("/api/document/reset")


def test_reset_restores_the_bundled_offer():
    from app.main import BUNDLED_OFFER

    body = client.post("/api/document/reset").json()
    assert body["ok"] is True
    assert body["offer"]["daily_installment"] == BUNDLED_OFFER["daily_installment"]
    assert body["baseline"]["burden_pct"] == 11.7
