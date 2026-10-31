"""Deterministic repayment simulator.

This module is the heart of Loan Saathi and the reason its claims hold up: **every number a
merchant ever sees is computed here**, by plain arithmetic, from their own settlement history.
The language model never calculates anything, it only renders these results into a sentence.

Design rules (do not relax them):
  * stdlib only, no third-party imports, so nothing in the dependency tree can break this file
  * pure functions, no I/O, no globals, no state
  * ``shock_pct`` is NEGATIVE: a 30% sales drop is ``-0.30``

Reference: project brief §5.3.
"""

from __future__ import annotations

# --- Demo assumptions ------------------------------------------------------------------
# These are OUR demo settings, not Paytm or lender rules. Say so if asked.
#
# BURDEN_CEILING is the share of daily settlement we treat as a comfortable installment.
# The brief suggested 0.20 as a starting point; we use 0.15 because the pitch's own hero
# line ("the 700 rupee installment becomes 17% of your settlement, shall I suggest a
# smaller loan?") implies the threshold sits below 17%. A ceiling of 0.20 would approve
# that offer unchanged and the right-sizing step would be a no-op.
BURDEN_CEILING = 0.15

# The shock we right-size against: survive a 30% sales drop, not just an average day.
RIGHTSIZE_SHOCK = -0.30

# Coach fires when the trailing week falls below this fraction of the 90-day average.
COACH_DIP_FRACTION = 0.80

# Lenders quote round amounts; never suggest ₹87,431.
LOAN_AMOUNT_STEP = 1000


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("settlement history is empty")
    return sum(values) / len(values)


def average_daily(settlements: list[float]) -> float:
    """Mean daily settlement, the `A` of the brief's formulas.

    We use the mean, not the median, so the UI must say "average day" and never
    "typical day", for a weekend-heavy merchant the mean overstates a slow Monday.
    That is precisely why :func:`simulate` also reports shortfall days off the real series.
    """
    return _mean(settlements)


def simulate(
    settlements: list[float],
    installment: float,
    shock_pct: float = 0.0,
    shock_days: int = 30,
) -> dict:
    """Replay the merchant's own settlements under a sales shock.

    Args:
        settlements: daily settlement amounts in rupees, oldest first.
        installment: the offer's daily installment (``E``).
        shock_pct: sales change as a NEGATIVE fraction (``-0.30`` = a 30% drop).
        shock_days: how many of the most recent days the shock is applied over, 7-30.

    Returns a dict of plain numbers, ready to be substituted into a sentence.
    """
    if installment <= 0:
        raise ValueError("installment must be positive")
    if not -1.0 < shock_pct <= 0.0:
        raise ValueError("shock_pct must be a negative fraction greater than -1")

    window_len = max(1, min(int(shock_days), len(settlements)))
    avg = average_daily(settlements)
    shocked_avg = avg * (1 + shock_pct)

    # The shocked window: what the last `window_len` days would have looked like.
    window = [day * (1 + shock_pct) for day in settlements[-window_len:]]

    # Days the auto-debit could not have been met in full. This is the number that lands
    # with a merchant, a percentage is abstract, "four days you'd have come up short" isn't.
    short_days = [day for day in window if day < installment]
    cumulative_shortfall = sum(installment - day for day in short_days)

    return {
        "shock_pct": round(shock_pct, 4),
        "shock_days": window_len,
        "avg_daily": round(avg),
        "shocked_avg": round(shocked_avg),
        "installment": round(installment),
        # Burden = what share of a day's settlement the installment eats.
        "burden_pct": round(installment / shocked_avg * 100, 1),
        "daily_cushion": round(shocked_avg - installment),
        "shortfall_days": len(short_days),
        "cumulative_shortfall": round(cumulative_shortfall),
        "worst_day": round(min(window)) if window else 0,
    }


def rightsize(
    settlements: list[float],
    offer: dict,
    ceiling: float = BURDEN_CEILING,
    shock_pct: float = RIGHTSIZE_SHOCK,
) -> dict:
    """Largest loan whose burden stays under `ceiling` even after a sales shock.

    The lender's cost ratio is held constant, so the installment scales linearly with the
    principal and we can solve directly rather than search:

        installment_max = ceiling x average_settlement x (1 + shock_pct)
        factor          = installment_max / current_installment

    The amount is then floored to a round ``LOAN_AMOUNT_STEP``.
    """
    installment = offer["daily_installment"]
    shocked_avg = average_daily(settlements) * (1 + shock_pct)
    safe_installment = ceiling * shocked_avg

    factor = min(1.0, safe_installment / installment)
    amount = int(offer["loan_amount"] * factor / LOAN_AMOUNT_STEP) * LOAN_AMOUNT_STEP

    # Re-derive the installment from the rounded amount so the two always agree, and keep
    # the lender's total-payable ratio intact rather than inventing new pricing.
    exact_factor = amount / offer["loan_amount"] if offer["loan_amount"] else 0.0
    cost_ratio = offer["total_payable"] / offer["loan_amount"]
    new_installment = round(installment * exact_factor)

    return {
        "changed": amount < offer["loan_amount"],
        "ceiling_pct": round(ceiling * 100, 1),
        "shock_pct": round(shock_pct, 4),
        "loan_amount": amount,
        "daily_installment": new_installment,
        "tenor_days": offer["tenor_days"],
        "total_payable": round(amount * cost_ratio),
        "saved_per_day": round(installment - new_installment),
        # What the merchant is actually buying: burden under the shock they asked about.
        "burden_pct": round(new_installment / shocked_avg * 100, 1) if new_installment else 0.0,
    }


def coach(
    settlements: list[float],
    installment: float,
    fraction: float = COACH_DIP_FRACTION,
) -> dict:
    """Early-warning check: has the trailing week fallen away from the 90-day baseline?

    Deterministic by design. This never decides anything about credit, at the `act` tier it
    produces a handoff for a human to action.
    """
    last_7 = _mean(settlements[-7:])
    baseline = average_daily(settlements)
    drop = 1 - (last_7 / baseline) if baseline else 0.0

    if drop >= 0.30:
        tier = "act"
    elif drop >= 1 - fraction:   # default: a 20% drop
        tier = "warn"
    elif drop >= 0.10:
        tier = "watch"
    else:
        tier = "ok"

    return {
        "tier": tier,
        "alert": tier in ("warn", "act"),
        "last_7_avg": round(last_7),
        "baseline_avg": round(baseline),
        "drop_pct": round(drop * 100, 1),
        "burden_now_pct": round(installment / last_7 * 100, 1) if last_7 else 0.0,
        # A human handles the restructuring. We only raise our hand.
        "handoff_suggested": tier == "act",
    }
