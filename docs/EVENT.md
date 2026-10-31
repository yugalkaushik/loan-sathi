# Event facts and final deliverables

From the official devSemble event page (supplied by Yugal, 30 Oct 2026). **This supersedes the brief's
§1 where they differ.**

## Status: through to Stage 2

Stage 1 (PPT pitch) is **completed and cleared**, Team MegaByte is shortlisted for the offline finals.

| | |
|---|---|
| Event | Paytm Build for India AI Hackathon – Delhi Edition · hosted by Paytm Community with devSemble |
| Event window | **31 Oct 2026** (single day) |
| Venue | Paytm, SkymarkOne, Sector 98, Noida, Uttar Pradesh 201304 |
| Track | **2, AI-Powered Financial Journeys** · problem `paytmai` · difficulty **Medium** |
| Eligibility | Open to all · registration closed 27 Oct · Stage 1 deadline was 28 Oct, 2:00 PM |
| Team | Up to 3 members, **currently 1 of 3 joined** |
| Interest | 23,754 views |
| On-site | **Mentors are available during the build**, use them |

> Brief §1 says the Stage 1 deadline was 25 Oct; the event page says **28 Oct, 2:00 PM**. The event page
> is authoritative. Not load-bearing, but don't quote 25 Oct.

## Track 2 brief, verbatim

> "Make Insurance, Lending and Fintech simpler, faster and more human. Reimagine customer-facing
> journeys across Insurance, Lending and Fintech using AI. Focus on removing friction, reducing
> complexity, and helping customers complete critical financial journeys faster and with greater
> confidence."

Loan Saathi maps onto this cleanly, say these words back: *removing friction* (spoken Hindi instead of
a PDF), *reducing complexity* (one question instead of reading a KFS), *greater confidence* (seeing the
bad week before signing).

##  Three required final deliverables

> "The finalists will submit **the prototype, a demo video and the presentation of the prototype** built
> for final evaluation."

| # | Deliverable | Status |
|---|---|---|
| 1 | **Working prototype / proof of concept** | to build, `docs/BUILD-ORDER.md` |
| 2 | **Demo video** | **a required submission, not a fallback.** Budget real time for it. |
| 3 | **Presentation of the prototype** | the Stage 1 deck, updated to match what was actually built |

**This changes the last hour.** The demo video was planned as a network-failure backup; it is in fact a
graded artifact. Record it with enough time to re-record once. Evaluation also includes *demonstrating
the solution and explaining the approach*, so the Q&A table in `docs/DEMO-SCRIPT.md` is scored material.

Deliverable 3 means the deck must be reconciled with reality before submission, in particular the deck
names **Saaras v3 / Bulbul v3 / LiveKit**, and we ship **`saaras:v4` / `bulbul:v3` / no LiveKit**. Fix
the tech-stack slide, or be ready to explain the delta. See `docs/CONTEXT.md` §7.

## Sarvam AI is the Official AI Partner, build on Sarvam

> "Sarvam AI · Official AI Partner · **₹5,000 in Sarvam AI credits for each of the top 3 teams in every
> city** · **500 Sarvam AI credits for every participant who builds using Sarvam AI**"

Two consequences, and they point the same way:

1. **Credits are paid out for building on Sarvam**, free credits just for using it.
2. **The official AI partner's stack is the one in the room.** Sarvam engineers may well be among the
   mentors and the judges. A solution that runs end-to-end on Sarvam reads better here than one that
   uses Sarvam only as a microphone.

**Therefore: default the narrator to `sarvam-105b`, not Claude.** Both sit behind the same interface in
`app/narration/`, so this is a one-line env change (`LS_NARRATOR=sarvam`) and either can be demoed. Keep
Claude wired as the documented swap and as the structured-output path for intent extraction if Sarvam's
is weaker, but the headline demo should be Sarvam STT + Sarvam LLM + Sarvam TTS.

This also strengthens the pitch's "built on real Indian-AI infrastructure" slide: it becomes literally
true across the whole stack rather than for one component.

## Prizes and why the Q&A matters

Prizes, rewards, recognition, and **hiring opportunities with Paytm**, with the chance to "showcase
your skills to industry teams". The evaluation explicitly includes *explaining your approach*. The
guard-rail story (deterministic engine, numeric guard, no AI credit decisions, in-app consent) is the
part that demonstrates engineering judgement rather than demo polish. Lead with it when asked how it works.

## Team

1 of 3 slots filled. If anyone joins late, the parallelisable work is: the `web/` UI (hours 3–5) and the
**demo video**, both are near-independent of the engine. Hand over `docs/BUILD-ORDER.md` rows 17–20 and
the recording.
