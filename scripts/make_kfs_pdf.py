"""Generate a sample lender Key Fact Statement PDF for the document-extraction demo.

This is the document a merchant actually receives: dense, in English, full of terms, laid out
as a table. Sarvam Doc AI reads it and `app/engine.py` computes from what it finds.

The layout deliberately follows the RBI Key Facts Statement circular (15 Apr 2024) rather than
being a tidy key-value list, because an easy document would not demonstrate anything. Figures
match `data/demo.json` so the extraction can be checked against a known answer.

    python scripts/make_kfs_pdf.py       ->  data/sample-kfs.pdf
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sample-kfs.pdf"

NAVY = colors.HexColor("#002970")
RULE = colors.HexColor("#c9d2e0")
INK = colors.HexColor("#10192b")
MUTED = colors.HexColor("#5a6a82")


def rows_from_demo() -> list[tuple[str, str]]:
    """Build the KFS body from the same JSON the app serves, so the two cannot drift."""
    data = json.loads((ROOT / "data" / "demo.json").read_text(encoding="utf-8"))
    o = data["offer"]
    net = o["loan_amount"] - o["processing_fee"]

    def inr(n: int) -> str:
        s = str(int(n))
        if len(s) <= 3:
            return f"Rs. {s}"
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        return f"Rs. {','.join(parts)},{tail}"

    return [
        ("1.", "Loan proposal / account number", o["offer_id"]),
        ("2.", "Type of loan", "Unsecured Merchant Business Loan (Cash Advance)"),
        ("3.", "Sanctioned loan amount (in Rupees)", inr(o["loan_amount"])),
        ("4.", "Disbursal schedule", "100% upfront, credited to the linked settlement account"),
        ("5.", "Loan term", f"{o['tenor_days']} days"),
        ("6.", "Instalment details: repayment frequency", "Daily"),
        ("7.", "Number of instalments", str(o["tenor_days"])),
        ("8.", "Amount of each instalment (in Rupees)", inr(o["daily_installment"])),
        ("9.", "Interest rate (% per annum) and type",
         f"{o['interest_rate_pa']}% per annum, fixed, monthly reducing balance"),
        ("10.", "Fee / charges: processing fee",
         f"{inr(o['processing_fee'])} (2% of sanctioned amount, inclusive of GST)"),
        ("11.", "Net disbursed amount (in Rupees)", inr(net)),
        ("12.", "Total amount to be repaid (principal + interest + charges)",
         inr(o["total_payable"])),
        ("13.", "Mode of repayment",
         "Auto-debit from daily Paytm merchant settlement proceeds"),
        ("14.", "Foreclosure / prepayment charges", "Nil"),
        ("15.", "Contingent charges: penal charges for late payment",
         "Rs. 500 per instance, plus applicable taxes"),
        ("16.", "Cooling-off / look-up period",
         "3 days from the date of disbursal, as per RBI directions"),
        ("17.", "Grievance redressal officer",
         "Nodal Officer, grievance@example-lender.in, 1800-000-0000"),
    ]


def build() -> None:
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Key Fact Statement", author="Sample lender document",
    )

    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=13.5, textColor=NAVY,
                        spaceAfter=2, leading=17)
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=8.5, textColor=MUTED, leading=12)
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=8.5, textColor=INK, leading=11.5)
    cellb = ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.5, textColor=INK,
                           leading=11.5)
    note = ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=7.5, textColor=MUTED,
                          leading=10)

    data = json.loads((ROOT / "data" / "demo.json").read_text(encoding="utf-8"))
    lender = data["offer"]["lender_name"]
    merchant = data["merchant"]

    story = [
        Paragraph("KEY FACT STATEMENT", h1),
        Paragraph(
            f"{lender} &nbsp;|&nbsp; Issued under RBI circular "
            f"DOR.STR.REC.13/13.03.00/2024-25 dated 15 April 2024 on Key Facts Statement "
            f"for Loans and Advances", sub),
        Spacer(1, 5 * mm),
        Paragraph(
            f"<b>Borrower:</b> {merchant['name']}, {merchant['city']} &nbsp;&nbsp;"
            f"<b>Merchant ID:</b> {merchant['id']}", cell),
        Spacer(1, 4 * mm),
    ]

    body = [[Paragraph("Sr.", cellb), Paragraph("Parameter", cellb), Paragraph("Details", cellb)]]
    for sr, param, value in rows_from_demo():
        body.append([Paragraph(sr, cell), Paragraph(param, cell), Paragraph(value, cell)])

    table = Table(body, colWidths=[12 * mm, 72 * mm, 90 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f8")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    story += [
        Spacer(1, 5 * mm),
        Paragraph(
            "The borrower confirms that the contents of this Key Fact Statement have been "
            "explained to them in a language they understand. This statement is indicative and "
            "does not constitute a sanction. Credit approval remains at the sole discretion of "
            "the lender.", note),
        Spacer(1, 3 * mm),
        Paragraph(
            "SYNTHETIC SAMPLE DOCUMENT. Generated by scripts/make_kfs_pdf.py for the Loan "
            "Saathi prototype. Not issued by any lender, and not a real loan offer.", note),
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)


if __name__ == "__main__":
    build()
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes)")
    print("  figures mirror data/demo.json, so extraction has a known correct answer")
