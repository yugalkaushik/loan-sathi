"""Tests for the deterministic simulator.

The first test is the one that matters: it pins the three numbers printed on slide 6 of the
submitted deck. If it ever fails, either the engine is wrong or the pitch is wrong, and we need
to know which before standing in front of judges.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import engine, intent, narrate

ROOT = Path(__file__).resolve().parent.parent

FLAT = [6000.0] * 90      # a flat series isolates the arithmetic from the data generator
INSTALLMENT = 700.0


# --- the deck ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shock, expected",
    [(0.0, 11.7), (-0.30, 16.7), (-0.50, 23.3)],
)
def test_burden_matches_deck_slide_6(shock: float, expected: float) -> None:
    assert engine.simulate(FLAT, INSTALLMENT, shock)["burden_pct"] == expected


def test_generated_dataset_also_reproduces_the_deck() -> None:
    """The shipped data must reproduce the deck too, not just a synthetic flat series."""
    data = json.loads((ROOT / "data" / "demo.json").read_text(encoding="utf-8"))
    daily = data["settlements"]["daily"]
    installment = data["offer"]["daily_installment"]

    assert len(daily) == 90
    for shock, expected in ((0.0, 11.7), (-0.30, 16.7), (-0.50, 23.3)):
        assert engine.simulate(daily, installment, shock)["burden_pct"] == expected


# --- simulate ---------------------------------------------------------------------------


def test_shortfall_counts_days_the_debit_could_not_be_met() -> None:
    # Two closed days in a 10-day window: the ₹700 debit cannot be met on either.
    series = [6000.0] * 8 + [0.0, 0.0]
    out = engine.simulate(series, INSTALLMENT, 0.0, shock_days=10)
    assert out["shortfall_days"] == 2
    assert out["cumulative_shortfall"] == 1400


def test_shortfall_grows_as_the_shock_deepens() -> None:
    series = [6000.0] * 27 + [0.0, 900.0, 1300.0]
    counts = [
        engine.simulate(series, INSTALLMENT, s, 30)["shortfall_days"]
        for s in (0.0, -0.30, -0.50)
    ]
    assert counts == sorted(counts), f"shortfall days must be monotonic, got {counts}"
    assert counts[0] == 1    # only the closed day
    assert counts[-1] == 3   # closed day + both washout days


def test_window_is_bounded_by_history_length() -> None:
    out = engine.simulate([6000.0] * 5, INSTALLMENT, -0.30, shock_days=30)
    assert out["shock_days"] == 5


def test_cushion_and_worst_day() -> None:
    out = engine.simulate(FLAT, INSTALLMENT, -0.30, 30)
    assert out["shocked_avg"] == 4200
    assert out["daily_cushion"] == 3500
    assert out["worst_day"] == 4200


@pytest.mark.parametrize("bad", [0.5, -1.0, -1.5])
def test_rejects_a_non_negative_or_impossible_shock(bad: float) -> None:
    with pytest.raises(ValueError):
        engine.simulate(FLAT, INSTALLMENT, bad)


def test_rejects_empty_history() -> None:
    with pytest.raises(ValueError):
        engine.simulate([], INSTALLMENT)


# --- rightsize --------------------------------------------------------------------------

OFFER = {
    "lender_name": "Piramal Capital & Housing Finance",
    "loan_amount": 100000,
    "tenor_days": 180,
    "daily_installment": 700,
    "total_payable": 126000,
    "processing_fee": 1500,
    "interest_rate_pa": 24.0,
}


def test_rightsize_brings_the_shocked_burden_under_the_ceiling() -> None:
    rs = engine.rightsize(FLAT, OFFER, ceiling=0.15, shock_pct=-0.30)
    assert rs["changed"] is True
    assert rs["loan_amount"] < OFFER["loan_amount"]
    assert rs["burden_pct"] <= 15.0 + 0.1          # rounding to the ₹1,000 step
    assert rs["loan_amount"] % 1000 == 0, "lenders quote round amounts"


def test_rightsize_keeps_installment_and_amount_consistent() -> None:
    rs = engine.rightsize(FLAT, OFFER, ceiling=0.15, shock_pct=-0.30)
    ratio = rs["loan_amount"] / OFFER["loan_amount"]
    assert rs["daily_installment"] == round(OFFER["daily_installment"] * ratio)
    # The lender's pricing ratio is preserved, not reinvented.
    assert rs["total_payable"] == round(rs["loan_amount"] * 1.26)


def test_rightsize_is_a_no_op_when_the_offer_is_already_safe() -> None:
    rs = engine.rightsize(FLAT, OFFER, ceiling=0.60, shock_pct=-0.30)
    assert rs["changed"] is False
    assert rs["loan_amount"] == OFFER["loan_amount"]
    assert rs["saved_per_day"] == 0


def test_rightsize_never_increases_the_loan() -> None:
    for ceiling in (0.05, 0.15, 0.30, 0.90):
        rs = engine.rightsize(FLAT, OFFER, ceiling=ceiling)
        assert rs["loan_amount"] <= OFFER["loan_amount"]


# --- coach ------------------------------------------------------------------------------


def test_coach_is_quiet_on_a_steady_series() -> None:
    c = engine.coach(FLAT, INSTALLMENT)
    assert c["tier"] == "ok"
    assert c["alert"] is False
    assert c["handoff_suggested"] is False


def test_coach_escalates_to_act_on_a_deep_dip_and_asks_for_a_human() -> None:
    series = [6000.0] * 83 + [3800.0] * 7
    c = engine.coach(series, INSTALLMENT)
    assert c["tier"] == "act"
    assert c["alert"] is True
    assert c["handoff_suggested"] is True
    assert c["drop_pct"] > 30


def test_coach_fires_on_the_shipped_dataset() -> None:
    """Beat 5 of the demo depends on this."""
    data = json.loads((ROOT / "data" / "demo.json").read_text(encoding="utf-8"))
    c = engine.coach(data["settlements"]["daily"], data["offer"]["daily_installment"])
    assert c["alert"] is True, "the demo's coach beat would show nothing"
    assert c["handoff_suggested"] is True


def test_coach_tiers_are_ordered() -> None:
    tiers = [
        engine.coach([6000.0] * 83 + [drop] * 7, INSTALLMENT)["tier"]
        for drop in (6000.0, 5300.0, 4600.0, 3500.0)
    ]
    assert tiers == ["ok", "watch", "warn", "act"]


# --- intent parsing ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, pct",
    [
        ("अगर बिक्री 30% गिरी तो?", -0.30),
        ("अगर बिक्री तीस परसेंट गिर जाए", -0.30),
        ("what if sales drop 30 percent", -0.30),
        ("बिक्री आधी हो गई तो?", -0.50),
        ("if my sales fall by half", -0.50),
        ("बिक्री ५० प्रतिशत गिरी", -0.50),          # Devanagari digits
        ("sales down 20", -0.20),
    ],
)
def test_parses_a_sales_drop(text: str, pct: float) -> None:
    out = intent.parse(text)
    assert out["intent"] == "shock"
    assert out["shock_pct"] == pytest.approx(pct)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("छोटा लोन सुझाओ", "rightsize"),
        ("suggest a smaller loan", "rightsize"),
        ("मेरा कारोबार कैसा चल रहा है", "coach"),
        ("मुझे ऑफ़र समझाओ", "explain"),
        ("explain the offer", "explain"),
        ("कुल कितना चुकाना है", "explain"),
        # Out of scope: must stay unknown so the UI says "I don't have that information"
        # and offers a human, rather than answering a loan question that wasn't asked.
        ("what is the weather in Mumbai", "unknown"),
        ("मेरा नाम क्या है", "unknown"),
    ],
)
def test_parses_other_intents(text: str, expected: str) -> None:
    assert intent.parse(text)["intent"] == expected


def test_drop_is_clamped_to_the_slider_range() -> None:
    assert intent.parse("sales fall 95%")["shock_pct"] == pytest.approx(-0.60)


# --- narration --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "amount, expected",
    [
        (700, "₹700"),
        (6000, "₹6,000"),
        (126000, "₹1,26,000"),
        (100000, "₹1,00,000"),
        (10000000, "₹1,00,00,000"),
        (0, "₹0"),
    ],
)
def test_indian_digit_grouping(amount: int, expected: str) -> None:
    assert narrate._inr(amount) == expected


def test_narration_does_not_repeat_the_disclaimer() -> None:
    """The disclosure lives in the UI, not at the end of every spoken sentence.

    Saying "this is a simulation, not a guarantee" four times in a three minute demo made the
    audio long and the voice stilted. The masthead badge and the colophon carry it instead.
    """
    base = engine.simulate(FLAT, INSTALLMENT)
    sim = engine.simulate(FLAT, INSTALLMENT, -0.30)

    for lang in ("hi", "en"):
        for text in (
            narrate.explain_offer(OFFER, base, lang),
            narrate.explain_shock(sim, base, lang),
            narrate.explain_coach(engine.coach(FLAT, INSTALLMENT), lang),
        ):
            assert narrate.DISCLAIMER[lang] not in text
            assert text.strip() == text, "no trailing whitespace where it used to sit"


def test_rightsize_narration_reminds_about_in_app_confirmation() -> None:
    rs = engine.rightsize(FLAT, OFFER, ceiling=0.15)
    for lang in ("hi", "en"):
        assert narrate.CONFIRM_REMINDER[lang] in narrate.explain_rightsize(rs, OFFER, lang)


def test_narration_quotes_the_engine_numbers_verbatim() -> None:
    """The headline figure in the sentence must be the engine's, character for character."""
    base = engine.simulate(FLAT, INSTALLMENT)
    sim = engine.simulate(FLAT, INSTALLMENT, -0.30)
    text = narrate.explain_shock(sim, base, "en")
    assert f"{sim['burden_pct']}%" in text
    assert "₹4,200" in text          # the shocked average, formatted


# --- the guarantee ----------------------------------------------------------------------


def test_llm_polish_is_off_by_default() -> None:
    """With the default narrator there is no network call and no model in the path at all."""
    out, used = narrate.polish("रोज़ की किस्त ₹700 है।", "template")
    assert out == "रोज़ की किस्त ₹700 है।"
    assert used is False


@pytest.mark.parametrize(
    "tampered",
    [
        "रोज़ की किस्त ₹900 है।",      # changed a figure
        "रोज़ की किस्त ₹700 है। कुल ₹50,000।",   # invented a figure
        "रोज़ की किस्त है।",            # dropped the figure
    ],
)
def test_a_rephrasing_that_alters_any_number_is_rejected(tampered: str) -> None:
    """Backstop on top of the architecture: a garbled figure is caught and discarded."""
    original = "रोज़ की किस्त ₹700 है।"
    assert narrate._numbers_preserved(original, tampered) is False


def test_devanagari_and_ascii_digits_compare_equal() -> None:
    assert narrate._numbers_preserved("किस्त ₹700 है", "किस्त ₹७०० है") is True


def test_a_faithful_rephrasing_is_accepted() -> None:
    assert narrate._numbers_preserved(
        "The installment is ₹700 and the total is ₹1,26,000.",
        "You'll pay ₹700 a day, ₹1,26,000 in all.",
    ) is True
