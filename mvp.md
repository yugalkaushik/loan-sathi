# Loan Saathi, MVP and pitch brief

What we're building, what it proves, and the Paytm intelligence to pitch it with.
Research done 30 Oct 2026. Build day 31 Oct 2026.

---

## 1. The MVP in one sentence

A web page that looks like the Paytm for Business loan-offer screen, where a merchant asks in Hindi
*"what if my sales drop 30%?"* and gets a spoken, personalised answer computed from **their own 90-day
settlement history**, then a right-sized smaller offer, a PIN-confirmed consent step, and a
post-disbursal dip alert.

Six files. Four hours. Build order in `docs/BUILD-ORDER.md`.

## 2. What a judge sees, 3 minutes

| Beat | On screen | The line that lands |
|---|---|---|
| 1 | Offer card: ₹1,00,000 · ₹700/day · 180 days · total ₹1,26,000. Speaker plays Hindi. | "RBI requires the Key Fact Statement in a language the borrower understands. This is it, spoken." |
| 2 | Ask in Hindi → three tiles: **11.7% → 16.7% → 23.3%** | "And on *their own* history at -30%: **3 days** the settlement couldn't cover the ₹700 debit, and **₹1,470** cumulative shortfall." |
| 3 | "छोटा लोन सुझाएँ" → smaller amount, lower installment | "It talks the merchant *down* to the right amount. That's the opposite of pressure selling." |
| 4 | PIN modal → audit row appears | "Voice is never enough to record consent." |
| 5 | Coach alert: 7-day average down 22% → human handoff | "It warns *before* a missed payment. No AI credit decisions anywhere." |

## 3. What it delivers

1. **Personalisation**, shortfall days and cumulative shortfall off the merchant's real series. Generic
   EMI math cannot produce this. It is the one number nobody else in the room will show.
2. **Comprehension**, Hindi voice, grounded on the lender's Key Fact Statement.
3. **Trust that's structural, not claimed**, numbers live in fixed Hindi templates filled by a
   deterministic function. There is **no code path** where the model can invent a rupee figure.
4. **Compliance posture**, no AI underwriting, in-app consent, audit log, human escalation.

## 4. Where the win comes from

- **It finishes.** Most submissions are 70% done and the demo is an apology. Ours is demoable at the end
  of hour 2 and polished after.
- **The trust story is the differentiator, not the AI.** Paytm distributes regulated credit and is
  openly scouting hires; evaluation explicitly scores *explaining your approach*. "The LLM only
  explains, a deterministic engine does all the math, consent needs a tap" is an engineering-judgement
  answer. Most teams will demo a chatbot that confidently states a wrong number.
- **Sarvam end-to-end.** Official AI partner, their people may be in the room, credits paid for using it.
- **Honesty reads as seniority.** Synthetic-data badge, "average day" not "normal day", and "based on
  public information, to be validated" instead of claiming competitors lack features.

---

# Paytm intelligence, use this to pitch

## 5.  The deck's numbers are out of date. Q2 FY27 landed three days ago.

Paytm reported **Q2 FY27 on 27 Oct 2026** ([Paytm investor
relations](https://paytm.com/blog/investor-relations/paytm-q2-fy27-results-pat-225-crore-ebitda-rises-90-to-270-crore/)).
The deck quotes Q1 FY27 (₹814 Cr, +45%). **Quote Q2 instead, the newer numbers are better and quoting
a three-day-old result signals you actually follow the company.**

| Metric | Q2 FY27 | Why it matters to us |
|---|---|---|
| **Financial services distribution revenue** | **₹912 Cr, up 49% YoY** | Up from +45% in Q1, **accelerating**, and Paytm attributes it to "accelerating growth in merchant loan distribution". This is the line Loan Saathi protects. |
| FSD share of operating revenue | **≈34%** | A third of the company. Not a side bet. |
| Repeat borrowers, merchant loans | **more than 50% of quarterly disbursements** | Still true, still the core of our thesis: trust compounds into repeat lending. |
| Key financial-services customers | **8.8 lakh, up 35% YoY** | |
| Operating revenue | ₹2,648 Cr, up 28% | FSD is growing ~1.75× faster than the company. |
| PAT | **₹225 Cr** (from ₹21 Cr, ~10×) | |
| EBITDA | **₹270 Cr, up 90%**, margin **10% for the first time** | |
| Merchant GMV | ₹7.1 lakh crore, up 26% | |
| Subscription merchants / Soundbox storefronts | **1.64 crore** (+27 lakh YoY) | Our distribution surface. |
| Monthly transacting users | 8.5 crore (+1 crore YoY) | |
| Indirect expenses | 46% of revenue, down from 52% | AI-driven cost leverage, ties to our "cut cost to serve" slide. |

## 6. The quote to open or close with

From Paytm's own Q2 FY27 release:

> **"AI is increasingly becoming the operating system of Paytm."**

Then: *"Loan Saathi is that operating system applied to the one journey where a wrong decision costs the
merchant real money, taking a loan."*

## 7. Paytm's enterprise AI push reframes our business model

> ⚠️ **Do not say the brand name on stage.** Medianama reports the service was *officially
> unnamed* in Paytm's own Q2 FY27 release; "Paytm Intelligence" / "Pi" comes from Bloomberg
> reporting. Say **"your enterprise AI offering"**. Same point, no exposure.
>
> It also has **no public developer API**, so we do not and cannot build on it. It is a
> positioning angle, not a dependency.

Paytm launched an **enterprise AI service** in Oct 2026. Per [Medianama](https://www.medianama.com/2026/10/223-paytm-enterprise-ai-service/)
and Bloomberg reporting, it will **"initially sell AI agents to banks, lenders, insurers, and other
financial institutions in India and the UAE"**, covering **sales, customer support and operations**.
Revenue sits under the *Commerce Cloud* line. CEO Vijay Shekhar Sharma: *"We have developed a low-cost
AI model… We will sell it to other businesses"*, expecting *"a meaningful business in less than a year"*.

**Why this is the single most useful thing we found:** our business-model slide currently says "funded
from loan-distribution margin". There is a better answer now,

> "Loan Saathi has two revenue paths. It protects distribution margin by lifting offer-to-accept and
> repeat-loan rate. And it's **an agent you could sell through your enterprise AI offering**,
> a borrower-comprehension and early-warning agent. You've said you'll sell AI agents to banks and
> lenders; this is one, already pointed at your own loan book."

Paytm is also building AI agents that act as a small merchant's digital **"COO, CFO or CMO"**
([Medianama, Q4 FY26 earnings call](https://www.medianama.com/2026/05/223-paytm-agentic-ai-wealthtech-growth-q4-fy26/)).
Say it plainly: **Loan Saathi is the CFO for the borrowing decision.**

## 8. How the lending product actually works (so we don't get caught)

From [Paytm's own business-loan page](https://paytm.com/loans-credit-cards/business-loan/):

- **Up to ₹10 lakh**, collateral-free, fully digital, **no foreclosure charges**
- **"Repay in daily installments through auto-deductions from Paytm settlements"**, verbatim. This is
  the mechanic our whole product rests on; it's confirmed by the source, not inferred.
- Offers are pre-qualified from transaction data, the merchant doesn't apply so much as accept

Average ticket size **₹1.8 lakh** and tenure **13 months**, but that figure is from **Sept 2023**, so
label it as dated or skip it. Our ₹1,00,000 / 180-day demo offer is inside the plausible range either
way. **Flag:** FLDG cost is expensed up front while collection revenue arrives over the 12–18 month
tenure, which means early delinquency hits Paytm's P&L before the revenue lands. That makes our
early-warning coach a *margin* story, not just a goodwill story. Use it.

### Lending partners, the deck has a stale name

Reported partners now include **SMFG India Credit (formerly Fullerton India)**, **Poonawalla Fincorp**,
**Piramal Capital & Housing Finance**, **Aditya Birla Finance**, **Tata Capital** and **Clix Capital**.
Paytm has board approval for a **default loss guarantee of up to ₹225 Cr**.

- The deck says **"Fullerton"** → it is **SMFG India Credit** now. Fix it.
- The deck says **"Suryoday"** → it did not appear in current partner lists. Drop it or say "partners
  including SMFG India Credit, Piramal, Tata Capital and Clix".
- DLG/FLDG percentage per loan: **unconfirmed, do not quote a percentage.**

## 9. The AI Soundbox is our distribution story

Launched at Global Fintech Festival (Oct 2025): Android-based, dual display, **AI assistant in 11 Indian
languages**, answers merchant questions on payments, sales, collections and business performance.
**1.64 crore Soundbox storefronts** are deployed.

> "You've already put an AI that speaks 11 languages into 1.64 crore storefronts, and it already answers
> questions about sales. Loan Saathi is the lending conversation on that same device, no new hardware,
> no new install."

Coverage also notes Soundbox data already **feeds merchant creditworthiness assessment**. So the data our
simulator needs is data Paytm already has.

## 10. Say these Track 2 words back to them

The track asks to *"remove friction, reduce complexity, and help customers complete critical financial
journeys faster and with greater confidence."*

- **friction** → spoken Hindi instead of a PDF
- **complexity** → one question instead of reading a Key Fact Statement
- **confidence** → seeing the bad week *before* signing

---

## 11. Deck fixes before submitting (deliverable 3)

1. **₹814 Cr / +45% (Q1 FY27) → ₹912 Cr / +49% (Q2 FY27)**, and add "FSD is ~34% of revenue".
2. **"Fullerton" → "SMFG India Credit"**; drop or soften "Suryoday".
3. Tech stack says **Saaras v3 / Bulbul v3 / LiveKit** → we ship **`saaras:v4`**, `bulbul:v3`, **no
   LiveKit**. Fix it or be ready to explain.
4. Add one line to the business-model slide about selling this through Paytm's enterprise AI
   offering. Describe it, do not name it.

## 12. Be clear-eyed

- **This is not novel AI.** It's a thin LLM layer over ~25 lines of arithmetic. The novelty is the
  product insight, daily settlement deduction means a slow week is the real risk, and nobody shows it
  before signing, plus the discipline of refusing to let the model touch the numbers. Own that framing;
  don't imply a model breakthrough.
- **Voice is the fragile part.** Text input box always present, audio pre-generated to files. If the
  venue wifi dies, the demo still runs.
- **Never claim competitors lack features.** "Based on public information, to be validated."
- **Figures marked dated or unconfirmed above stay unquoted.** One wrong number in Q&A costs more than
  any extra number gains.

## 13. The sentence to open and close with

> "Merchants repay these loans daily out of their settlement. The offer screen shows the installment but
> never what happens in a slow week, so we show it, in Hindi, computed from their own sales, before
> they sign."

---

### Sources

- [Paytm Q2 FY27 results, Paytm investor relations, 27 Oct 2026](https://paytm.com/blog/investor-relations/paytm-q2-fy27-results-pat-225-crore-ebitda-rises-90-to-270-crore/)
- [Paytm Q2 FY27, Business Standard](https://www.business-standard.com/amp/companies/quarterly-results/paytm-q2fy27-net-profit-jumps-10-fold-to-225-crore-revenue-up-28-126102601539_1.html)
- [Paytm business loan, official product page](https://paytm.com/loans-credit-cards/business-loan/)
- [Paytm enterprise AI service (Pi), Medianama, Oct 2026](https://www.medianama.com/2026/10/223-paytm-enterprise-ai-service/)
- [Paytm agentic AI + wealthtech, Q4 FY26 earnings call, Medianama](https://www.medianama.com/2026/05/223-paytm-agentic-ai-wealthtech-growth-q4-fy26/)
- [Paytm FLDG/DLG for merchant loans, Inc42](https://inc42.com/buzz/paytm-inks-fldg-pact-to-boost-lending-play-for-merchants/)
- [Why Paytm is betting on FLDG, YourStory](https://yourstory.com/2024/10/why-paytm-is-betting-on-fldg-model-to-boost-lending-and-revenues)
- [Paytm AI Soundbox launch, Business Today, Oct 2025](https://www.businesstoday.in/tech-today/launch/story/paytm-unveils-indias-first-ai-soundbox-for-merchants-shares-jump-25-after-launch-497139-2025-10-07)
- [RBI Key Facts Statement circular, 15 Apr 2024](https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12663&Mode=0)
