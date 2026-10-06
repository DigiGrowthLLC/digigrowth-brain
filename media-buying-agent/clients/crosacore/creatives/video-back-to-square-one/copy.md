# CrosaCore: "Stuck Restarting at the Gym?" (AI UGC video, new concept: in-clinic, back to training)

**Avatar:** man, late 30s, busy professional who lifts. This is Brandon's onboarding ideal patient
(under 60, recurring pain, wants to get back to training). **Angle:** in-clinic, one-on-one, central Austin.
**Funnel stage:** top of funnel. **Format:** AI actor selfie UGC, Veo 3.1 Fast, 2 takes, approved 2026-10-06.

| Take | Spoken |
|---|---|
| 1 | "Every time I get back into lifting, my back flares up, and I'm right back to square one." |
| 2 | "So there's a PT clinic in central Austin that's one-on-one, start to finish. Private pay, first consult's free." |

Hook card: "Back to square one?" · Proof: Akhil ("helped me build strength... confidence in my movements")
Guardrails: the actor describes his own situation, doesn't claim to be a patient and makes no results claim.
The hook describes a situation, not the viewer's condition.

## Ad copy (paste into Ads Manager; add all variants and let Meta rotate them)

**Primary text 1 (story):**
> Hey Austin 👋 A few good weeks back in the gym, then a flare-up, and it's square one again?
>
> For a lot of active professionals, that cycle isn't a willpower problem. It usually needs a plan that rebuilds strength progressively, not another round of resting and starting over.
>
> Dr. Brandon Crosdale, DPT, OCS works one-on-one at his central Austin clinic, combining orthopedic physical therapy with progressive strength work in one individualized plan.
>
> Private pay, superbills available. Start with a free 15-minute consult.

**Primary text 2 (proof):**
> "Brandon helped me build strength, improve my posture, and develop confidence in my movements." Akhil, real Google review
>
> One-on-one physical therapy at a central Austin clinic, built around getting back to lifting, running and training with confidence.
>
> Dr. Brandon Crosdale, DPT, OCS · 60+ real Google reviews · Private pay, superbills available.
>
> Book a free 15-minute consult.

**Primary text 3 (short):**
> Getting back into training shouldn't mean starting over every few weeks. One-on-one PT at Dr. Brandon Crosdale's central Austin clinic. Private pay. Free 15-minute consult.

**Headlines:** One-on-One PT in Central Austin · Back to Training, Not Square One · Get Back to Lifting With a Plan · Free 15-Min Consult With a DPT · Strength-Based PT in Austin
**Descriptions:** Free 15-min consult · Private pay | In-clinic, one-on-one · Central Austin
**Button:** Sign Up

**Files:** `video-9x16.mp4` (Reels/Stories) + `video-4x5.mp4` (Feed) go in the same ad. `actor.png` is the approved still.

**Iterating on it (same actor, different scripts):** animate `actor.png` with `generate_creative.py video
--model veo31-fast`, reusing this voice line: "a man in his late 30s with a relaxed, slightly exasperated
but good-humored, mid-low American male voice, casual and unscripted-sounding, moderate pace". Setting:
driver's seat of a parked car in an office parking lot. **Approved look includes a finishing pass** on the
takes before assembly (Veo Fast footage looks over-sharpened/"animated" without it):
`ffmpeg -i take.mp4 -vf "gblur=sigma=0.8,noise=alls=8:allf=t+u,eq=saturation=0.9:contrast=0.96:gamma=1.02,colorbalance=rm=0.02:bm=-0.02,format=yuv420p" -c:v libx264 -crf 16 -c:a copy take-polished.mp4`
