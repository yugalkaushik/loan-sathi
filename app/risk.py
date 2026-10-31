"""Predict whether this merchant can actually survive this loan.

This is the part of Loan Saathi that has an opinion.

`app/engine.py` answers "what if sales fall 30%" — but the merchant has to supply the 30%,
and the answer is a division. This module instead *learns how this particular merchant's cash
flow behaves* and predicts what happens over the loan's full term:

    "Over 180 days there is a 68% chance you miss at least one instalment.
     At Rs 89,000 instead, that falls to 23%."

Nothing about that comes from a slider or a calculator. It comes from four behaviours read out
of the merchant's own ninety days:

  * **weekday rhythm** - their Tuesdays are quiet and their Saturdays are busy
  * **closure rate** - how often the shutter stays down, because the auto-debit does not care
  * **trend** - whether the business is drifting up or down right now
  * **volatility** - how erratic a normal day is, kept as the merchant's own residuals rather
    than a fitted normal distribution, because real retail is not normally distributed

Those drive a Monte Carlo: simulate the next 180 days a few thousand times by resampling the
merchant's own good and bad days, and count how often the settlement cannot cover the debit.

Design rules, same as `engine.py`:
  * **stdlib only** - no numpy, nothing that can break the thing the demo depends on
  * **seeded** - identical inputs give identical probabilities, every run, forever
  * **pure functions** - no I/O, no globals

A language model is never involved. The model computes the risk; the LLM only puts it into a
sentence afterwards.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# A day at or below this share of the median counts as "shop shut", not "quiet day". Real
# settlement feeds rarely show an exact zero (a single stray payment still lands), so a
# threshold finds closures more reliably than testing for 0.
_CLOSED_THRESHOLD = 0.15

# Guard rails on the learned weekday factors. With ~13 observations per weekday in 90 days,
# one freak Diwali Saturday should not convince the model that every Saturday triples.
_MIN_WEEKDAY_FACTOR = 0.35
_MAX_WEEKDAY_FACTOR = 2.50

# Likewise for the trend: a sharp recent dip should bend the forecast, not run it to zero or
# to the moon over a 180-day horizon.
_MIN_TREND_FACTOR = 0.50
_MAX_TREND_FACTOR = 1.50

DEFAULT_SIMS = 2000
DEFAULT_HORIZON = 180
DEFAULT_SEED = 42

# Penalty per failed auto-debit. The sample Key Fact Statement says "Rs. 500 per instance",
# and when a real document is uploaded this should come from it.
DEFAULT_PENALTY = 500.0


@dataclass(frozen=True)
class Profile:
    """What we learned about how this merchant trades."""

    mean_daily: float
    median_daily: float
    weekday_factor: list[float]        # index 0 = Monday, matching date.weekday()
    closure_rate: float
    trend_per_day: float               # fractional change per day, e.g. -0.001 = -0.1%/day
    residuals: list[float] = field(repr=False)   # multiplicative, around 1.0
    volatility: float = 0.0            # spread of those residuals
    n_days: int = 0

    def as_dict(self) -> dict:
        """Presentable summary. The residual sample is omitted: it is 80-odd floats."""
        return {
            "mean_daily": round(self.mean_daily),
            "median_daily": round(self.median_daily),
            "weekday_factor": [round(f, 2) for f in self.weekday_factor],
            "busiest_weekday": self.weekday_factor.index(max(self.weekday_factor)),
            "quietest_weekday": self.weekday_factor.index(min(self.weekday_factor)),
            "closure_rate_pct": round(self.closure_rate * 100, 1),
            "closed_days_per_month": round(self.closure_rate * 30, 1),
            "trend_pct_per_month": round(self.trend_per_day * 30 * 100, 1),
            "volatility_pct": round(self.volatility * 100, 1),
            "days_learned": self.n_days,
        }


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if not n:
        raise ValueError("no settlements")
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _percentile(xs: list[float], p: float) -> float:
    """Linear-interpolated percentile. `p` in 0..1."""
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = p * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def decompose(settlements: list[float], first_weekday: int = 0) -> Profile:
    """Learn the merchant's trading behaviour from their settlement history.

    Args:
        settlements: daily settlement amounts, oldest first.
        first_weekday: weekday of ``settlements[0]``, 0 = Monday. The caller knows the real
            start date; the default only matters for which weekday gets which label.
    """
    n = len(settlements)
    if n < 14:
        raise ValueError("need at least two weeks of settlements to learn anything")

    median = _median(settlements)
    mean = sum(settlements) / n

    # --- closures: the shutter is down, but the instalment still goes out --------------
    closed_cut = median * _CLOSED_THRESHOLD
    closed = [s for s in settlements if s <= closed_cut]
    trading = [(i, s) for i, s in enumerate(settlements) if s > closed_cut]
    closure_rate = len(closed) / n

    if len(trading) < 10:
        raise ValueError("too few trading days to model")

    trading_mean = sum(s for _, s in trading) / len(trading)

    # --- trend: least squares on trading days, expressed per day as a fraction ---------
    xs = [float(i) for i, _ in trading]
    ys = [s for _, s in trading]
    x_bar = sum(xs) / len(xs)
    y_bar = sum(ys) / len(ys)
    denom = sum((x - x_bar) ** 2 for x in xs)
    slope = (
        sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys)) / denom if denom else 0.0
    )
    trend_per_day = (slope / y_bar) if y_bar else 0.0

    # --- weekday rhythm, measured after removing the trend ----------------------------
    by_weekday: list[list[float]] = [[] for _ in range(7)]
    for i, s in trading:
        detrended = s / (1 + trend_per_day * (i - x_bar)) if trend_per_day else s
        by_weekday[(first_weekday + i) % 7].append(detrended)

    weekday_factor = [
        _clamp((sum(v) / len(v)) / trading_mean, _MIN_WEEKDAY_FACTOR, _MAX_WEEKDAY_FACTOR)
        if v else 1.0
        for v in by_weekday
    ]

    # --- what is left over is this merchant's own volatility --------------------------
    # Kept as a sample and resampled later (a bootstrap), so the simulation inherits the
    # real shape of their good and bad days instead of assuming a bell curve.
    residuals: list[float] = []
    for i, s in trading:
        base = trading_mean * weekday_factor[(first_weekday + i) % 7]
        base *= 1 + trend_per_day * (i - x_bar)
        if base > 0:
            residuals.append(s / base)
    if not residuals:
        residuals = [1.0]

    r_mean = sum(residuals) / len(residuals)
    volatility = (sum((r - r_mean) ** 2 for r in residuals) / len(residuals)) ** 0.5

    return Profile(
        mean_daily=mean,
        median_daily=median,
        weekday_factor=weekday_factor,
        closure_rate=closure_rate,
        trend_per_day=trend_per_day,
        residuals=residuals,
        volatility=volatility,
        n_days=n,
    )


def forecast(
    profile: Profile, horizon: int = DEFAULT_HORIZON, first_weekday: int = 0
) -> list[float]:
    """Expected settlement for each of the next `horizon` days, before volatility."""
    base = profile.mean_daily * (1 - profile.closure_rate)
    base = base / (1 - profile.closure_rate) if profile.closure_rate < 1 else base

    out = []
    for d in range(horizon):
        # Trend is extrapolated but clamped: ninety days of drift should inform a six-month
        # projection, not dominate it.
        trend = _clamp(1 + profile.trend_per_day * d, _MIN_TREND_FACTOR, _MAX_TREND_FACTOR)
        out.append(base * profile.weekday_factor[(first_weekday + d) % 7] * trend)
    return out


def simulate_risk(
    settlements: list[float],
    installment: float,
    horizon: int = DEFAULT_HORIZON,
    sims: int = DEFAULT_SIMS,
    seed: int = DEFAULT_SEED,
    first_weekday: int = 0,
    profile: Profile | None = None,
    penalty_per_miss: float = DEFAULT_PENALTY,
    sales_shock: float = 0.0,
) -> dict:
    """Monte Carlo the loan term. Returns how often the auto-debit is predicted to fail.

    Each simulated day is either a closure (probability `closure_rate`) or a trading day whose
    settlement is the forecast multiplied by a residual drawn from the merchant's own history.
    """
    if installment <= 0:
        raise ValueError("installment must be positive")
    if horizon < 1 or sims < 1:
        raise ValueError("horizon and sims must be positive")

    if not -1.0 < sales_shock <= 0.0:
        raise ValueError("sales_shock must be a negative fraction greater than -1")

    p = profile or decompose(settlements, first_weekday)
    # A sales shock scales the whole predicted path. The merchant's weekday rhythm, closure
    # rate and volatility are unchanged by it: a 30% worse quarter is still their business,
    # just a smaller version of it.
    expected = [v * (1 + sales_shock) for v in forecast(p, horizon, first_weekday)]
    residuals = p.residuals
    n_res = len(residuals)
    rng = random.Random(seed)

    miss_counts: list[int] = []
    trading_miss_counts: list[int] = []
    shortfalls: list[float] = []
    cushions: list[float] = []

    for _ in range(sims):
        misses = trading_misses = 0
        shortfall = 0.0
        total = 0.0
        for day in range(horizon):
            closed = rng.random() < p.closure_rate
            settlement = 0.0 if closed else expected[day] * residuals[rng.randrange(n_res)]
            total += settlement
            if settlement < installment:
                misses += 1
                # Separating the two causes is the whole point. A failed debit on a day the
                # shutter was down is not the loan's fault and shrinking the loan will not
                # prevent it. A failed debit on a trading day means the instalment is simply
                # too big for this merchant's takings, and that IS a loan-sizing problem.
                if not closed:
                    trading_misses += 1
                shortfall += installment - settlement
        miss_counts.append(misses)
        trading_miss_counts.append(trading_misses)
        shortfalls.append(shortfall)
        cushions.append(total / horizon - installment)

    expected_misses = sum(miss_counts) / sims
    expected_trading = sum(trading_miss_counts) / sims
    expected_closure = expected_misses - expected_trading
    any_miss = sum(1 for m in miss_counts if m >= 1) / sims

    # The headline is the *number* of failed auto-debits, not whether there is ever one.
    # Over a 180-day term a merchant who shuts even one day a month is near-certain to miss
    # at least once, so "probability of any miss" saturates at 100% and tells nobody anything.
    # What varies with the loan size, and what actually costs the merchant money, is how many.
    miss_rate = expected_misses / horizon
    # Banded on trading-day failures, because those are the ones a smaller loan would fix.
    if expected_trading < 1:
        band = "low"
    elif expected_trading < horizon * 0.05:
        band = "moderate"
    else:
        band = "high"

    return {
        "horizon_days": horizon,
        "simulations": sims,
        "sales_shock_pct": round(abs(sales_shock) * 100),
        "installment": round(installment),
        # Headline: how many times the auto-debit fails over the term.
        "expected_miss_days": round(expected_misses, 1),
        # The split that tells the merchant what to actually do about it.
        "closure_miss_days": round(expected_closure, 1),
        "trading_miss_days": round(expected_trading, 1),
        "driven_by": "shop closures" if expected_trading < 1 else "instalment size",
        "p95_miss_days": round(_percentile([float(m) for m in miss_counts], 0.95)),
        "miss_rate_pct": round(miss_rate * 100, 1),
        "misses_per_month": round(miss_rate * 30, 1),
        # Each failed debit carries a penalty in the lender's own Key Fact Statement, so the
        # prediction converts into a rupee figure the merchant can act on.
        "expected_penalty": round(expected_misses * penalty_per_miss),
        "p95_cumulative_shortfall": round(_percentile(shortfalls, 0.95)),
        "median_daily_cushion": round(_percentile(cushions, 0.50)),
        "p_any_miss": round(any_miss * 100, 1),
        "p_three_plus_misses": round(sum(1 for m in miss_counts if m >= 3) / sims * 100, 1),
        "risk_band": band,
    }


def safe_amount(
    settlements: list[float],
    offer: dict,
    max_trading_misses: float = 1.0,
    horizon: int | None = None,
    sims: int = 600,
    seed: int = DEFAULT_SEED,
    first_weekday: int = 0,
) -> dict:
    """Largest loan before the instalment itself starts causing failed debits.

    The target is **trading-day** misses, not total misses. A merchant who shuts one day a
    month will fail that day's debit whatever they borrow, so including closures in the target
    would make every loan look equally bad and the answer would never move. What the loan size
    controls is whether a normal trading day covers the instalment, and that is what this
    searches on.

    This replaces an arbitrary burden ceiling with a statement about this merchant's own
    takings: "above roughly Rs X, your ordinary days stop covering the instalment."
    """
    horizon = horizon or int(offer.get("tenor_days", DEFAULT_HORIZON))
    principal = float(offer["loan_amount"])
    installment = float(offer["daily_installment"])
    if principal <= 0 or installment <= 0:
        raise ValueError("offer must have a positive amount and instalment")

    profile = decompose(settlements, first_weekday)
    cost_ratio = float(offer.get("total_payable", principal)) / principal

    def trading_misses_at(amount: float) -> float:
        emi = installment * (amount / principal)
        return simulate_risk(
            settlements, emi, horizon, sims, seed, first_weekday, profile
        )["trading_miss_days"]

    at_full = trading_misses_at(principal)

    # Search upward as well as downward: if the offer is already safe, the useful answer is
    # how much headroom the merchant has, not a shrug.
    if at_full <= max_trading_misses:
        hi = principal
        ceiling = principal * 12          # far past Paytm's Rs 10 lakh cap, so the search binds
        lo = principal
        while hi < ceiling and trading_misses_at(hi) <= max_trading_misses:
            lo, hi = hi, hi * 2
        for _ in range(7):
            mid = (lo + hi) / 2
            if trading_misses_at(mid) <= max_trading_misses:
                lo = mid
            else:
                hi = mid
        step = int(offer.get("amount_step", 1000))
        headroom = max(step, int(lo / step) * step)
        return {
            "changed": False,
            "target_trading_misses": max_trading_misses,
            "loan_amount": int(principal),
            "daily_installment": int(round(installment)),
            "tenor_days": horizon,
            "total_payable": int(round(principal * cost_ratio)),
            "saved_per_day": 0,
            "trading_miss_days": round(at_full, 1),
            "trading_miss_days_before": round(at_full, 1),
            # The genuinely useful number when the offer is already fine.
            "headroom_amount": headroom,
        }

    lo, hi = 0.0, principal
    for _ in range(9):                       # ~Rs 200 resolution on Rs 1,00,000
        mid = (lo + hi) / 2
        if trading_misses_at(mid) <= max_trading_misses:
            lo = mid
        else:
            hi = mid

    step = int(offer.get("amount_step", 1000))
    amount = max(step, int(lo / step) * step)
    emi = installment * (amount / principal)

    return {
        "changed": amount < principal,
        "target_trading_misses": max_trading_misses,
        "loan_amount": amount,
        "daily_installment": int(round(emi)),
        "tenor_days": horizon,
        "total_payable": int(round(amount * cost_ratio)),
        "saved_per_day": int(round(installment - emi)),
        "trading_miss_days": round(trading_misses_at(amount), 1),
        "trading_miss_days_before": round(at_full, 1),
        "headroom_amount": amount,
    }
