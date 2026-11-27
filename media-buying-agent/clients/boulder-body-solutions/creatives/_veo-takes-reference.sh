#!/usr/bin/env bash
# Batch 1 talking takes, Veo 3.1 Fast ($0.15/s, 8s = $1.20 each). 14 takes, ~$16.80.
cd "C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain/content-agent"
export SSL_CERT_FILE="C:/Users/dylan/AppData/Roaming/Python/Python314/site-packages/certifi/cacert.pem"
W="../media-buying-agent/outputs/ad-boulder-batch1-2026-11-09/work"
mkdir -p "$W/takes"

take() { # name still voice setting line
  doppler run --project digigrowth --config prd -- python tools/generate_creative.py video \
    "Handheld front-camera selfie video, vertical 9:16, candid UGC. $3 talks straight into the camera and says exactly: \"$5\" $4 No music, no subtitles, no on-screen text." \
    --model veo31-fast --image "$W/$2" --duration 8 --out "$W/takes/$1.mp4" > "$W/takes/$1.log" 2>&1
  echo "$1 exit $?"
}

V1="The woman, warm, slightly tired, conversational American voice, mid-40s, natural pace,"
S1="Quiet parked car ambience."
V3="The man, early 40s, frustrated but determined, clear American voice, a little out of breath from running,"
S3="Light outdoor breeze, birds in the distance."
V6="The man, about 50, dry wry tone, calm deep American voice,"
S6="Quiet home office ambience."
V8="The woman, mid-40s, honest reflective tone, warm clear American voice,"
S8="Soft climbing gym ambience, distant chatter."

take c1-t1 c1-actor.png "$V1" "$S1" "You ever leave a massage feeling amazing... and by Thursday it's right back? That was me." &
take c1-t2 c1-actor.png "$V1" "$S1" "The sore spot usually isn't the problem. A muscle next to it quit, so it does double duty." &
take c1-t3 c1-actor.png "$V1" "$S1" "A DPT in Boulder tests for exactly that, muscle by muscle. Forty-nine bucks. Ten spots a month." &
take c3-t1 c3-actor-v2.png "$V3" "$S3" "A doctor told me, if it hurts, maybe you just can't run anymore. I'm forty." &
take c3-t2 c3-actor-v2.png "$V3" "$S3" "Nobody checked if the muscles around my knee were even firing. If one quits, the knee takes the hit." &
take c3-t3 c3-actor-v2.png "$V3" "$S3" "A DPT in Boulder tests that, muscle by muscle. Before you hang up the shoes. Ten spots a month." &
take c6-t1 c6-actor.png "$V6" "$S6" "My MRI says everything's normal. Bending over says otherwise. Two years of this." &
take c6-t2 c6-actor.png "$V6" "$S6" "A scan shows the parts. It doesn't show which muscles actually turn on when you bend or lift." &
take c6-t3 c6-actor.png "$V6" "$S6" "A DPT in Boulder tests exactly that, one muscle at a time. Forty-nine dollars. Ten spots a month." &
take c8-t1 c8-actor.png "$V8" "$S8" "I spent three years managing my shoulder. Never fixing it." &
take c8-t2 c8-actor.png "$V8" "$S8" "PT twice. Massage every month. Bands every night. It'd calm down, then flare the first time I pushed." &
take c8-t3 c8-actor.png "$V8" "$S8" "Then I learned about MAT. When one muscle stops firing, the one next to it does double duty." &
take c8-t4 c8-actor.png "$V8" "$S8" "Stretching and massage calm the cranky one. Nobody was checking the quiet one." &
take c8-t5 c8-actor.png "$V8" "$S8" "A DPT in Boulder, Dr. Aaron Shaver, tests exactly that. A full hour, one on one. Ten spots a month." &
wait
echo ALL DONE
