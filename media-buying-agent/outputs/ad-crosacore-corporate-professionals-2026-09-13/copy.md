# Ad: CrosaCore — Busy Corporate Professionals

**Client:** CrosaCore (Brandon Crosdale, PT, DPT, OCS) — cash-pay physical therapy & personal
training, Austin, TX. **Offer:** free 15-minute Pain Confidence Consultation.
**Avatar/angle:** busy corporate professionals whose job leaves no time to deal with pain — one of
the 2 avatars from `campaign-crosacore-2026-09-13/campaign-plan.md`, Concept 1.
**Mode:** new concept (part of the approved 2-avatar campaign plan, not an iteration).
**Placement:** Feed (1:1).

---

**Hook:** "Hey Austin. Does a demanding job leave no time to deal with pain?"

**Problem:** Desk-driven neck and shoulder tension, recurring low back pain, pain that's hard to
switch off from after hours — with no time for lengthy treatment.

**Solution:** Dr. Brandon Crosdale, PT, DPT, OCS, offers a free, no-pressure 15-minute Pain
Confidence Consultation built around a schedule that doesn't stop. Cash-pay, no insurance billing
required.

**Proof:** In her own words: "As a recruiter at Apple, I live a busy, high-pressure lifestyle where
staying active isn't optional. Since starting with Brandon, I've had a real reduction in pain and
learned how to work through flare-ups without catastrophizing." (real client testimonial, Lauren
Wright)

**CTA:** "Free 15-Minute Pain Confidence Consultation" — Learn More

**Condition checklist (on-image support text):** Desk-driven tension · Recurring low back pain ·
Can't switch off from it · No time for lengthy treatment

---

## Image (v3 — revised twice per Dylan's feedback)

- v1: generic corporate portrait, plain bottom banner — too obviously a stock photo, no PT content.
- v2: added a real PT-treatment scene and a split layout, but the photo still read as visibly
  AI-polished and took up too much of the frame, and the copy jumped straight to trust bullets
  without agitating the pain point first.
- v3 (current): smaller, more candid photo + copy restructured to pain → solution → trust → CTA.

**Prompt used (v3):** raw, unedited-looking iPhone photo, slightly imperfect candid angle, a
physical therapist assessing and mobilizing the shoulder of a seated professional client, client's
face shows real mild discomfort with natural facial asymmetry, therapist mid-motion, ordinary
clinic/home-office room with visible clutter, mixed indoor lighting with slight color cast, visible
skin texture, slight motion blur, grainy low-contrast amateur photography (deliberately
less-polished than a professional photoshoot), no text, no logos.

**Layout:** 1080x1400 — photo now only the top ~40% (down from ~62% in v2) so it reads less like a
staged AI photoshoot and more like an incidental candid; forest-green panel below, vertically
balanced (no dead space) with:
- Eyebrow: "CROSACORE · AUSTIN, TX"
- **Pain-point headline:** "Sitting all day is quietly wrecking your back and shoulders."
- **Solution line:** "One individualized plan, not a generic program, built around what is actually
  going on."
- 3 real trust bullets (from the live funnel's own trust bar, not invented): 60+ real Google reviews
  · Trusted by busy professionals · DPT, OCS, Certified Pain Specialist
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

## v6 (current) — back to vertical, zoomed-out photo

Reverted to the top/bottom vertical layout (photo top ~40%, panel bottom ~60%), same as v3, but
regenerated the photo pulled back to a medium distance (about six feet, full upper bodies) instead
of a tight close-up — close framing was what made the AI generation most noticeable (skin/facial
detail scrutinized at full frame). New prompt keeps the actual PT action clearly visible (therapist
mobilizing the shoulder) while de-emphasizing facial closeup detail. Output: `base5.jpg` (raw AI
photo, medium-distance) + `image.jpg` (final composited ad).
