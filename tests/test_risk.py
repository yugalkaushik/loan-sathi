"""Tests for the cash-flow risk model.

This is the only component that makes a prediction, so it is the one that most needs holding
to account. The tests fall into three groups:

  * **it learns real structure** - given a series with a planted weekday rhythm, trend or
    closure rate, the model must recover it. Otherwise it is just noise with a confident face.
  * **it behaves coherently** - a bigger instalment can never be safer, a longer term can
    never be safer. These are the properties that make the output trustworthy.
  * **it is reproducible** - same input, same seed, same answer, every run. A demo whose
    numbers move between rehearsal and stage is worthless.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import risk

ROOT = Path(__file__).resolve().parent.parent

FLAT = [6000.0] * 90
INSTALLMENT = 700.0


def shipped() -> tuple[list[float], dict, int]:
    """The dataset the demo runs on, plus the weekday its history starts on."""
    from datetime import date

    data = json.loads((ROOT / "data" / "demo.json").read_text(encoding="utf-8"))
    daily = data["settlements"]["daily"]
    start = date.fromisoformat(data["settlements"]["start_date"]).weekday()
    return daily, data["offer"], start


# --- it learns real structure -------------------------------------------------------------


def test_recovers_a_planted_weekday_rhythm():
    """Sundays twice as busy: the model must see it, and in the right slot."""
    series = []
    for day in range(91):
        weekday = day % 7                      # start on Monday, so index 6 is Sunday
        series.append(12000.0 if weekday == 6 else 6000.0)

    p = risk.decompose(series, first_weekday=0)
    assert p.weekday_factor[6] > 1.4, "the Sunday spike was not learned"
    assert p.weekday_factor[6] == max(p.weekday_factor)
    assert all(f < 1.2 for i, f in enumerate(p.weekday_factor) if i != 6)


def test_recovers_the_closure_rate():
    series = [6000.0] * 81 + [0.0] * 9         # exactly 10% closed
    p = risk.decompose(series)
    assert p.closure_rate == pytest.approx(0.10, abs=0.01)


def test_near_zero_days_count_as_closures():
    """A real settlement feed rarely shows a clean zero; one stray payment still lands."""
    series = [6000.0] * 85 + [40.0] * 5
    p = risk.decompose(series)
    assert p.closure_rate == pytest.approx(5 / 90, abs=0.01)


def test_detects_a_declining_business():
    series = [8000.0 - 40 * i for i in range(90)]      # falls steadily
    p = risk.decompose(series)
    assert p.trend_per_day < 0
    assert p.as_dict()["trend_pct_per_month"] < -5


def test_detects_a_growing_business():
    series = [4000.0 + 40 * i for i in range(90)]
    assert risk.decompose(series).trend_per_day > 0


def test_flat_series_has_almost_no_volatility():
    p = risk.decompose(FLAT)
    assert p.volatility < 0.01
    assert p.closure_rate == 0.0


def test_refuses_too_little_history():
    with pytest.raises(ValueError):
        risk.decompose([6000.0] * 5)


def test_refuses_a_series_that_is_nearly_all_closures():
    with pytest.raises(ValueError):
        risk.decompose([0.0] * 85 + [6000.0] * 5)


# --- it behaves coherently ----------------------------------------------------------------


def test_a_comfortable_instalment_never_fails_on_a_flat_series():
    out = risk.simulate_risk(FLAT, 700.0, horizon=180, sims=200)
    assert out["expected_miss_days"] == 0.0
    assert out["risk_band"] == "low"


def test_an_impossible_instalment_fails_every_day():
    out = risk.simulate_risk(FLAT, 99000.0, horizon=90, sims=200)
    assert out["expected_miss_days"] == 90.0
    assert out["risk_band"] == "high"


def test_a_bigger_instalment_is_never_safer():
    """The core monotonicity property. If this breaks, nothing the model says can be trusted."""
    daily, _, start = shipped()
    profile = risk.decompose(daily, start)
    misses = [
        risk.simulate_risk(daily, emi, 180, 400, 42, start, profile)["expected_miss_days"]
        for emi in (500, 1500, 3000, 5000, 8000)
    ]
    assert misses == sorted(misses), f"not monotonic in instalment: {misses}"


def test_a_longer_term_is_never_safer():
    daily, _, start = shipped()
    profile = risk.decompose(daily, start)
    misses = [
        risk.simulate_risk(daily, 700.0, h, 400, 42, start, profile)["expected_miss_days"]
        for h in (30, 90, 180, 360)
    ]
    assert misses == sorted(misses), f"not monotonic in horizon: {misses}"


def test_closure_and_trading_misses_add_up():
    daily, offer, start = shipped()
    out = risk.simulate_risk(daily, 3000.0, 180, 400, 42, start)
    assert out["closure_miss_days"] + out["trading_miss_days"] == pytest.approx(
        out["expected_miss_days"], abs=0.2
    )


def test_a_small_instalment_fails_only_on_closure_days():
    """Rs 700 against Rs 6,000 of takings: the loan is not the problem, the shutter is."""
    daily, offer, start = shipped()
    out = risk.simulate_risk(daily, offer["daily_installment"], 180, 800, 42, start)
    assert out["trading_miss_days"] < 1
    assert out["driven_by"] == "shop closures"
    assert out["closure_miss_days"] > 5


def test_a_large_instalment_starts_failing_on_trading_days():
    daily, _, start = shipped()
    out = risk.simulate_risk(daily, 3500.0, 180, 800, 42, start)
    assert out["trading_miss_days"] > 1
    assert out["driven_by"] == "instalment size"


def test_penalty_scales_with_predicted_misses():
    out = risk.simulate_risk(FLAT, 99000.0, horizon=10, sims=100, penalty_per_miss=500)
    assert out["expected_penalty"] == 10 * 500


def test_rejects_nonsense_arguments():
    with pytest.raises(ValueError):
        risk.simulate_risk(FLAT, 0)
    with pytest.raises(ValueError):
        risk.simulate_risk(FLAT, 700, horizon=0)
    with pytest.raises(ValueError):
        risk.simulate_risk(FLAT, 700, sims=0)


# --- it is reproducible -------------------------------------------------------------------


def test_same_seed_gives_identical_results():
    daily, _, start = shipped()
    a = risk.simulate_risk(daily, 2000.0, 180, 500, 42, start)
    b = risk.simulate_risk(daily, 2000.0, 180, 500, 42, start)
    assert a == b, "the demo would show different numbers on each run"


def test_different_seeds_agree_closely():
    """Sampling noise must be small enough that the headline figure is stable."""
    daily, _, start = shipped()
    profile = risk.decompose(daily, start)
    runs = [
        risk.simulate_risk(daily, 2000.0, 180, 1500, s, start, profile)["expected_miss_days"]
        for s in (1, 2, 3, 4)
    ]
    assert max(runs) - min(runs) < 1.5, f"too noisy across seeds: {runs}"


# --- the forecast -------------------------------------------------------------------------


def test_forecast_length_and_positivity():
    p = risk.decompose(FLAT)
    f = risk.forecast(p, 180)
    assert len(f) == 180
    assert all(v > 0 for v in f)


def test_forecast_carries_the_weekday_rhythm():
    series = [12000.0 if d % 7 == 6 else 6000.0 for d in range(91)]
    p = risk.decompose(series, first_weekday=0)
    f = risk.forecast(p, 14, first_weekday=0)
    assert f[6] > f[5], "Sunday should still be the peak in the forecast"


def test_forecast_trend_is_clamped():
    """Ninety days of decline should bend a six-month projection, not take it to zero."""
    series = [9000.0 - 60 * i for i in range(90)]
    p = risk.decompose(series)
    f = risk.forecast(p, 360)
    assert min(f) > 0
    assert min(f) >= 0.4 * max(f), "the trend ran away over a long horizon"


# --- safe_amount --------------------------------------------------------------------------


def test_safe_amount_reports_headroom_when_the_offer_is_already_safe():
    daily, offer, start = shipped()
    out = risk.safe_amount(daily, offer, sims=250, first_weekday=start)
    assert out["changed"] is False
    assert out["headroom_amount"] >= offer["loan_amount"], "headroom cannot be below the offer"


def test_safe_amount_shrinks_a_dangerous_offer():
    daily, offer, start = shipped()
    big = dict(offer, loan_amount=600000, daily_installment=4200, total_payable=756000)
    out = risk.safe_amount(daily, big, sims=250, first_weekday=start)
    assert out["changed"] is True
    assert out["loan_amount"] < big["loan_amount"]
    assert out["saved_per_day"] > 0
    assert out["trading_miss_days"] < out["trading_miss_days_before"]


def test_safe_amount_never_exceeds_a_dangerous_offer():
    daily, offer, start = shipped()
    big = dict(offer, loan_amount=800000, daily_installment=5600, total_payable=1008000)
    out = risk.safe_amount(daily, big, sims=200, first_weekday=start)
    assert out["loan_amount"] <= big["loan_amount"]


def test_safe_amount_is_a_round_figure():
    """No lender quotes Rs 87,431."""
    daily, offer, start = shipped()
    big = dict(offer, loan_amount=600000, daily_installment=4200, total_payable=756000)
    out = risk.safe_amount(daily, big, sims=200, first_weekday=start)
    assert out["loan_amount"] % 1000 == 0


def test_both_search_directions_agree():
    """Searching down from a big offer and up from a small one must find the same ceiling."""
    daily, offer, start = shipped()
    from_small = risk.safe_amount(daily, offer, sims=300, first_weekday=start)["headroom_amount"]
    big = dict(offer, loan_amount=600000, daily_installment=4200, total_payable=756000)
    from_big = risk.safe_amount(daily, big, sims=300, first_weekday=start)["loan_amount"]
    assert abs(from_small - from_big) / from_small < 0.25, (
        f"inconsistent ceiling: {from_small} from below, {from_big} from above"
    )


# --- the advisory layer -------------------------------------------------------------------


def test_advice_template_needs_no_network():
    from app import narrate

    daily, offer, start = shipped()
    sim = risk.simulate_risk(daily, offer["daily_installment"], 180, 200, 42, start)
    safe = risk.safe_amount(daily, offer, sims=150, first_weekday=start)

    for lang in ("hi", "en"):
        text = narrate._advice_template(sim, safe, lang)
        assert text.strip()
        assert "_" not in text, "a raw field name leaked into the advice"


def test_advice_falls_back_without_a_key():
    """conftest blanks credentials, so this must not reach the network."""
    from app import narrate

    daily, offer, start = shipped()
    sim = risk.simulate_risk(daily, offer["daily_installment"], 180, 200, 42, start)
    safe = risk.safe_amount(daily, offer, sims=150, first_weekday=start)
    text, used = narrate.advise(sim, safe, risk.decompose(daily, start).as_dict(), offer, "hi")
    assert used is False
    assert text == narrate._advice_template(sim, safe, "hi")


def test_a_hallucinated_advisory_is_rejected(monkeypatch):
    """The guard is what lets us hand these numbers to a merchant at all."""
    from app import narrate
    from app.config import settings

    daily, offer, start = shipped()
    sim = risk.simulate_risk(daily, offer["daily_installment"], 180, 200, 42, start)
    safe = risk.safe_amount(daily, offer, sims=150, first_weekday=start)

    monkeypatch.setattr(settings, "ls_open_qa", True)
    monkeypatch.setattr(settings, "sarvam_api_key", "pretend-key")
    monkeypatch.setattr(
        narrate, "_chat_sarvam",
        lambda *a, **k: "You will miss 47 payments and owe Rs 250000 in penalties.",
    )

    text, used = narrate.advise(sim, safe, risk.decompose(daily, start).as_dict(), offer, "en")
    assert used is False, "invented figures reached the merchant"
    assert text == narrate._advice_template(sim, safe, "en")


def test_the_examples_carry_no_figures():
    """An example with numbers gets copied, and the guard then rejects every answer."""
    import re

    from app import narrate

    for lang, example in narrate._ADVICE_EXAMPLE.items():
        assert not re.search(r"\d", example), f"{lang} example contains a digit"
