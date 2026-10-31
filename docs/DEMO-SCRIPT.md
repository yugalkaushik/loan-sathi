# Demo script, 3 minutes

Merchant: **Sharma Kirana Store**, one merchant, 90 days of settlement averaging ≈ ₹6,000/day, with a
dip in the last week so the coach alert fires on the same dataset.
Offer: **₹1,00,000**, **₹700 daily installment**, **180 days**, total payable **₹1,26,000**.

Open on the web UI with the **"Synthetic demo data, not Paytm data"** badge visible. Say the word
"synthetic" in the first sentence, it buys credibility for everything after it.

Every beat has a fallback. Rehearse the fallbacks too.

---

## Beat 0, the frame (0:00–0:20)

> "Paytm's merchant loans are repaid by auto-deducting from the merchant's daily settlement. The offer
> screen shows the amount, the total payable and the daily installment, but not what happens in a slow
> week. That's the gap. Everything you'll see is synthetic data."

---

## Beat 1, Explain (0:20–0:55)

Tap the speaker icon on the offer card. Hindi plays:

> रोज़ की किस्त ₹700 है। कुल चुकाना है ₹1,26,000, 180 दिन में।
> यह आपकी औसत रोज़ की सेटलमेंट का 11.7% है।
> यह एक अनुमान है, गारंटी नहीं।

Point at the KFS panel while it plays.

> "That's the lender's Key Fact Statement, read out in Hindi. RBI requires the KFS in a language the
> borrower understands, this goes past a PDF to a spoken, personalised explanation."

**Fallback:** pre-rendered WAV from `data/audio/`. No network needed.

---

## Beat 2, Stress-test (0:55–1:40) ← **the beat that wins or loses it**

Tap the mic and ask:

> **अगर बिक्री 30% गिरी तो?**

Three tiles update:

| | Average day | Sales -30% | Sales -50% |
|---|---|---|---|
| Settlement | ₹6,000 | ₹4,200 | ₹3,000 |
| **Burden** | **11.7%** | **16.7%** | **23.3%** |

Then point at the two numbers nobody else shows:

> "And on their **own** 90-day history, at -30%: **3 days** where the settlement couldn't cover the
> ₹700 debit in full, and **₹1,470** of cumulative shortfall. That's not generic EMI math, that's this
> merchant's actual sales pattern replayed."

> "These numbers come from a deterministic Python simulator. The LLM doesn't do arithmetic, it only
> turns the simulator's JSON into Hindi."

**Fallbacks, in order:** the text input box (type the question, skips STT) → the what-if slider (drag to
-30%). The tiles are what matter; how the question arrives does not.

---

## Beat 3, Right-size (1:40–2:05)

Tap **छोटा लोन सुझाएँ** ("suggest a smaller loan").

> "It right-sizes to the largest amount that keeps the burden under 15% even at -30%. Here that is
> **₹89,000 at ₹623 a day**, which brings the burden to **14.8%**. That 15% ceiling is our demo
> assumption, not a Paytm rule."

Show the reduced amount and the new daily installment side by side with the original.

> "This is the opposite of pressure selling. It talks the merchant *down* to the right amount."

---

## Beat 4, Confirm (2:05–2:25)

Tap accept → PIN modal → enter `1234`.

> "Voice is never enough to record consent. Anything that moves money or records consent takes an
> in-app confirmation, and it lands in an audit log."

Open `GET /api/confirm`'s response (or the audit list). Show the row.

---

## Beat 5, Coach (2:25–2:55)

Hit **"simulate a dip"**, the last week of the same dataset is already down.

> "After disbursal it watches the settlement trend. Trailing 7-day average is ₹3,883 against a ₹6,000 baseline, 35.3% down, below 80% of the
> 90-day average, so it raises an alert *before* an installment is missed, and routes a restructuring
> request to a human. No AI credit decisions anywhere in this product."

Show the `act`-tier alert and the handoff record.

---

## Beat 6, Close (2:55–3:00)

> "Explain, stress-test, coach. Merchants know the real burden before signing. Paytm gets more repeat
> borrowers, already over half of disbursements, on a financial-services distribution line that grew
> **49% to ₹912 crore last quarter**. And lending partners get earlier warning signals on a book where
> the loss guarantee is expensed up front."

---

## Judge Q&A, prepared answers

| Question | Answer |
|---|---|
| "Is this real Paytm data?" | "No, fully synthetic, labelled in the UI. It reads from one JSON file, so a real settlement feed is a swap at one function." |
| "Does the AI decide the loan?" | "No. The lender's offer and KFS are the source of truth. A deterministic simulator does every calculation; the LLM only explains. No underwriting." |
| "How do you know the LLM isn't making numbers up?" | "Because it never holds them. The numbers come out of a deterministic function and get substituted into fixed Hindi sentences. There is no code path where a model can produce a rupee figure. And there's a unit test pinning 11.7 / 16.7 / 23.3, want to see it run?" |
| "Sales or settlement?" | "We shock the settlement series directly, so we're assuming 1:1 passthrough from sales. It's footnoted in the UI. Modelling the digital-share split properly is next." |
| "Why average and not median?" | "We use the mean and the tile says 'average day', not 'typical day'. For a weekend-heavy merchant a mean does understate a bad Monday, which is exactly why we also show shortfall *days* off the real series, not just the average." |
| "Competitors do this already?" | "Based on public information, the Paytm app shows the loan numbers and the Soundbox announces payments in regional languages. We don't claim anyone lacks these, to be validated with Paytm. What we haven't seen anywhere is a stress-test against the merchant's own settlements before they sign." |
| "Where's LiveKit, from the deck?" | "Cut for the MVP, this is request/response. Sarvam's own `speech_to_text_realtime_streaming` is the lower-risk path to duplex, and that's what we'd build next." |
| "What's the APR?" | "We show total payable and daily burden rather than APR, that's what a merchant on a daily-deduction loan actually feels. The RBI circular defines APR as the annual cost of credit including all charges; computing it from the lender's cash flows is a small addition, we just didn't prioritise it over the stress-test." |
| "Languages?" | "Hindi and English today; language is a request parameter. Sarvam's TTS covers 11 languages and STT 24, so the ceiling is the vendor's, not ours." |
| "Business model?" | "Two paths. No fee to merchants, it's funded from loan-distribution margin, where better comprehension lifts offer-to-accept and repeat-loan rate, and the AI absorbs contacts that would otherwise be support tickets. Second, it's a **Paytm Intelligence product you could sell to the lending partners**, you've said Pi will sell AI agents to banks, lenders and insurers; this is one, already pointed at your own loan book." |
| "Why should Paytm care?" | "Financial-services distribution grew 49% to ₹912 crore last quarter, about 34% of revenue, and Paytm credits accelerating merchant-loan distribution. Over half of disbursements are repeat borrowers. We protect the flywheel that line depends on." |
| "Why not just put this on the Soundbox?" | "Partly there. Today's Soundbox speaks but does not listen, so it raises the prompt: your offer is ready, open the app. The conversation happens on the phone, which is where the PIN is anyway. Paytm has said the Soundbox is evolving to support voice-led merchant assistance; when that ships this moves onto the device. 1.64 crore storefronts, no new hardware." |

## The video is a deliverable, not a backup

`docs/EVENT.md`: finalists submit **prototype + demo video + presentation**. The video is graded.

So record this script properly, clean audio, no dead air, the synthetic-data badge visible in frame,
and keep the recording as the network-failure fallback too. Leave enough time to record it twice.
