"""Read a lender's loan document with Sarvam Doc AI.

This is the step that makes the journey AI-powered rather than AI-narrated. A merchant is
handed a Key Fact Statement: English, dense, laid out as a table of regulatory parameters.
They cannot read it. Doc AI reads it and returns the fields; `app/engine.py` then computes
from those exactly as it does from the bundled demo offer.

The division of labour is unchanged and deliberate:

    the model READS the document   ->   arithmetic COMPUTES the consequences
                                        ->   the model SPEAKS the result

A language model is never asked to work out what 700 is as a share of 4,200. It is asked to
find "amount of each instalment" on a page, which is what models are actually good at.

Doc AI is an asynchronous job: submit, poll, fetch results. Verified against docs.sarvam.ai
on 31 Oct 2026. Nothing here raises: every failure returns a reason and the caller keeps the
offer it already had.
"""

from __future__ import annotations

import json
import logging
import re
import time

from app.config import settings

log = logging.getLogger("loan_saathi.document")

# Field names match data/demo.json's `offer` object, so an extraction result drops straight
# into the engine with no translation layer. Every property needs a non-empty description:
# the API rejects the schema otherwise, and the description is what the model matches on, so
# these are phrased the way an Indian lender document phrases them.
KFS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "lender_name": {
            "type": "string",
            "description": "Name of the lender, bank or NBFC issuing this loan",
        },
        "loan_amount": {
            "type": "number",
            "description": "Sanctioned loan amount or principal, in INR, digits only",
        },
        "daily_installment": {
            "type": "number",
            "description": (
                "Amount of each instalment in INR. The repayment is daily, so this is the "
                "daily instalment, EMI or auto-debit amount, digits only"
            ),
        },
        "tenor_days": {
            "type": "integer",
            "description": (
                "Loan term in days. If the term is given in months, convert to days. "
                "May also appear as the number of instalments when repayment is daily"
            ),
        },
        "total_payable": {
            "type": "number",
            "description": (
                "Total amount to be repaid over the full term, including principal, interest "
                "and charges, in INR, digits only"
            ),
        },
        "processing_fee": {
            "type": "number",
            "description": "Processing fee or upfront charges in INR, digits only",
        },
        "interest_rate_pa": {
            "type": "number",
            "description": "Annual interest rate as a percentage, for example 24.0",
        },
    },
}

_POLL_SECONDS = 2.0
_POLL_TIMEOUT = 45.0
_DONE = {"completed", "partially_completed", "failed", "rejected"}

# A daily-repayment loan has to hold together arithmetically. These bounds catch a garbled
# read before it reaches the engine and quietly drives every number on screen.
_MIN_TENOR_DAYS = 30
_MAX_TENOR_DAYS = 730
_TOTAL_TOLERANCE = 0.15      # total_payable vs installment x tenor


def extract_offer(
    data: bytes, filename: str, mime: str = "application/pdf"
) -> tuple[dict | None, str]:
    """Extract loan terms from a document. Returns ``(offer, reason)``.

    ``offer`` is None on any failure, with ``reason`` explaining why in words the UI can show.
    """
    if not settings.ls_doc_ai:
        return None, "Document reading is switched off (LS_DOC_AI=false)."
    if not settings.sarvam_api_key:
        return None, "No Sarvam API key, so documents cannot be read."
    if not data:
        return None, "The uploaded file was empty."

    try:
        from sarvamai import SarvamAI

        client = SarvamAI(api_subscription_key=settings.sarvam_api_key)
        job = client.doc_ai.extract(
            file=[(filename, data, mime)],
            schema=json.dumps(KFS_SCHEMA),          # multipart form field, so a JSON string
            output_format="json",
            # NOTE: the docs show a `language` argument; the installed SDK's extract() does
            # not accept one and raises TypeError. Verified against sarvamai 0.1.41.
        )
        job_id = job.job_id
    except Exception as exc:
        log.warning("Doc AI submit failed: %s", exc)
        return None, "Could not send the document for reading."

    status, pages = _poll(client, job_id)
    if status not in ("completed", "partially_completed"):
        return None, f"The document could not be read (status: {status})."

    try:
        raw = client.doc_ai.get_results(job_id=job_id).result
    except Exception as exc:
        log.warning("Doc AI results failed: %s", exc)
        return None, "The document was read but the result could not be fetched."

    offer, reason = _to_offer(raw)
    if offer is None:
        return None, reason

    offer["pages_read"] = pages
    log.info("extracted offer from %s: %s", filename, offer)
    return offer, "ok"


def _poll(client, job_id: str) -> tuple[str, int]:
    """Wait for the job, returning ``(status, pages_processed)``."""
    deadline = time.monotonic() + _POLL_TIMEOUT
    pages = 0
    while time.monotonic() < deadline:
        try:
            st = client.doc_ai.get_status(job_id=job_id)
        except Exception as exc:
            log.warning("Doc AI status failed: %s", exc)
            return "failed", pages

        status = str(getattr(st, "status", "") or "").lower()
        usage = getattr(st, "usage", None)
        if usage is not None:
            pages = getattr(usage, "pages_processed", pages) or pages
        if status in _DONE:
            return status, pages
        time.sleep(_POLL_SECONDS)

    return "timed_out", pages


def _num(value) -> float | None:
    """Coerce whatever the model returned into a number.

    It may hand back ``"Rs. 1,00,000"`` or ``"24.0% per annum"`` rather than a bare figure,
    so strip everything that is not part of the number rather than rejecting the field.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    # Drop grouping commas, then take the first number-like token. Keeping every "." would
    # turn "Rs. 1,00,000" into 0.1, because the full stop in "Rs." becomes a decimal point.
    text = str(value).replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _to_offer(raw: dict) -> tuple[dict | None, str]:
    """Validate and normalise an extraction result into an engine-ready offer."""
    if not isinstance(raw, dict):
        return None, "The document reader returned an unexpected result."

    amount = _num(raw.get("loan_amount"))
    installment = _num(raw.get("daily_installment"))
    tenor = _num(raw.get("tenor_days"))
    total = _num(raw.get("total_payable"))
    fee = _num(raw.get("processing_fee")) or 0.0
    rate = _num(raw.get("interest_rate_pa")) or 0.0

    missing = [
        name for name, v in (
            ("loan amount", amount), ("daily instalment", installment),
            ("loan term", tenor), ("total payable", total),
        ) if v is None
    ]
    if missing:
        return None, f"Could not find {', '.join(missing)} in this document."

    if min(amount, installment, total) <= 0 or fee < 0:
        return None, "The amounts read from this document are not valid."
    if not (_MIN_TENOR_DAYS <= tenor <= _MAX_TENOR_DAYS):
        return None, f"A loan term of {tenor:.0f} days is outside the supported range."
    if installment >= amount:
        return None, "The instalment read is larger than the loan, so the document misread."

    # The strongest check available: for a daily-repayment loan the instalments must add up
    # to roughly the total payable. If they do not, one of the two was misread and every
    # figure the engine derives would be wrong.
    expected = installment * tenor
    if abs(expected - total) / total > _TOTAL_TOLERANCE:
        return None, (
            f"The figures do not add up: {installment:.0f} x {tenor:.0f} days is "
            f"{expected:,.0f}, but the total payable reads {total:,.0f}."
        )

    return {
        "offer_id": "DOC-UPLOAD",
        "lender_name": str(raw.get("lender_name") or "Lender from uploaded document").strip(),
        "loan_amount": int(round(amount)),
        "daily_installment": int(round(installment)),
        "tenor_days": int(round(tenor)),
        "total_payable": int(round(total)),
        "processing_fee": int(round(fee)),
        "interest_rate_pa": round(rate, 2),
        "source": "extracted from an uploaded document by Sarvam Doc AI",
        "kfs": _kfs_rows(amount, fee, rate, tenor, installment, total),
    }, "ok"


def _kfs_rows(amount, fee, rate, tenor, installment, total) -> list[dict]:
    """Rebuild the on-screen Key Facts table from the extracted values."""
    def inr(n: float) -> str:
        s = str(int(round(n)))
        if len(s) <= 3:
            return f"₹{s}"
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        return f"₹{','.join(parts)},{tail}"

    return [
        {"label": "Loan amount", "label_hi": "लोन राशि", "value": inr(amount)},
        {"label": "Processing fee", "label_hi": "प्रोसेसिंग फीस", "value": inr(fee)},
        {"label": "Net disbursed", "label_hi": "मिलने वाली राशि", "value": inr(amount - fee)},
        {"label": "Interest rate (p.a.)", "label_hi": "ब्याज दर (सालाना)", "value": f"{rate}%"},
        {"label": "Tenure", "label_hi": "अवधि", "value": f"{int(tenor)} days"},
        {"label": "Daily installment", "label_hi": "रोज़ की किस्त", "value": inr(installment)},
        {"label": "Total payable", "label_hi": "कुल चुकाना है", "value": inr(total)},
        {"label": "Repayment mode", "label_hi": "भुगतान का तरीका",
         "value": "Auto-deduct from daily Paytm settlement"},
    ]
