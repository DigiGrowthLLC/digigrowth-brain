# Ad: CrosaCore — Older / Recovery-Focused Patients

**Client:** CrosaCore (Brandon Crosdale, PT, DPT, OCS) — cash-pay physical therapy & personal
training, Austin, TX. **Offer:** free 15-minute Pain Confidence Consultation.
**Avatar/angle:** older / recovery-focused patients regaining confidence after surgery or a setback
— the 2nd avatar from `campaign-crosacore-2026-09-13/campaign-plan.md`, Concept 2.
**Mode:** new concept (part of the approved 2-avatar campaign plan, not an iteration).
**Placement:** Feed (1:1).

---

**Hook:** "Hey Austin. Ready to move with confidence again after surgery or a setback?"

**Problem:** Recovering from surgery, fear of re-injury or falling, balance or mobility concerns,
wanting to stay independent.

**Solution:** Dr. Brandon Crosdale, PT, DPT, OCS, offers a free, no-pressure 15-minute Pain
Confidence Consultation to talk through what's safe and what's next.

**Proof:** In her own words: "I was anxious and fearful of exercise... Brandon was patient and kind
and acknowledged my feelings... The personal attention he is able to provide is uncommon in physical
therapy... I feel more confident and healthier than ever." (real client testimonial, Sharon
Anderson)

**CTA:** "Free 15-Minute Pain Confidence Consultation" — Learn More

**Condition checklist (on-image support text):** Recovering from surgery · Fear of re-injury/falling
· Balance concerns · Wants to stay independent

---

## Image (v3 — revised twice per Dylan's feedback)

- v1: generic solo lifestyle portrait, plain bottom banner — too obviously a stock photo, no PT
  content.
- v2: added a real PT-treatment scene and a split layout, but the photo still read as visibly
  AI-polished and took up too much of the frame, and the copy jumped straight to trust bullets
  without agitating the pain point first.
- v3 (current): smaller, more candid photo + copy restructured to pain → solution → trust → CTA.

**Prompt used (v3):** raw, unedited-looking iPhone photo, slightly imperfect candid angle, a
physical therapist helping an older adult client through a standing balance and leg-strengthening
exercise, therapist's hand near the client's back for support, client's face shows real focused
strain with natural facial asymmetry and visible wrinkles, ordinary home-gym or clinic room with
visible clutter, mixed indoor lighting with slight color cast, visible skin texture, slight motion
blur, grainy low-contrast amateur photography (deliberately less-polished than a professional
photoshoot), no text, no logos.

**Layout:** 1080x1400 — photo now only the top ~40% (down from ~62% in v2) so it reads less like a
staged AI photoshoot and more like an incidental candid; forest-green panel below, vertically
balanced (no dead space) with:
- Eyebrow: "CROSACORE · AUSTIN, TX"
- **Pain-point headline:** "Afraid one wrong move could set you back again?"
- **Solution line:** "A guided plan to rebuild strength and confidence, one step at a time."
- 3 real trust bullets (from the live funnel's own trust bar, not invented): 60+ real Google reviews
  · In-clinic & in-home care · DPT, OCS, Certified Pain Specialist
- Gold CTA pill: "FREE 15-MIN CONSULTATION"

All panel text composited with Pillow, not AI-generated (unreliable text rendering on diffusion
models) — see `image.jpg.meta.json` for full provenance.

Output: `base3.jpg` (raw AI photo) + `image.jpg` (final composited ad) + `.meta.json` sidecars.
(`base.jpg`/`base2.jpg` kept as earlier revision history, not for use.)

## Layout v4 — overlay attempt, superseded

Tried a full-bleed photo with a fading text scrim over the left side. Dylan's call: this hid too
much of the photo — reverted.

## Layout v5 — separated left/right split, superseded

Two distinct blocks side by side (text panel left, photo right). Dylan's call: reverted back to
vertical, and the photo itself was too close/detailed — see v6 below.

## v7 (current) — younger client, correct target age (50-60)

Dylan's call: the client in v6 read as too old for the actual 50-60 target demographic. Regenerated
with the same scene/action (therapist supporting a standing balance/reach exercise, medium
distance) but the client now a fit, active woman in her mid-50s — graying at the temples, not
elderly. Output: `base6.jpg` (raw AI photo) + `image.jpg`/`image.png` (final composited ad, same
50/50 vertical layout and copy as v6).

## v6 — back to vertical, zoomed-out photo

Reverted to the top/bottom vertical layout (photo top ~40%, panel bottom ~60%), same as v3, but
regenerated the photo pulled back to a medium distance (about six feet, full upper/full bodies)
instead of a tight close-up — close framing was what made the AI generation most noticeable
(skin/facial detail scrutinized at full frame). New prompt keeps the actual PT action clearly
visible (therapist supporting a standing balance/reach exercise) while de-emphasizing facial
closeup detail. Output: `base5.jpg` (raw AI photo, medium-distance) + `image.jpg` (final
composited ad).
