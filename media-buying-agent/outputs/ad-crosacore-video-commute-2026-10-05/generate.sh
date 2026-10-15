#!/usr/bin/env bash
# Run from the repo root after topping up fal.ai: bash media-buying-agent/outputs/ad-crosacore-video-commute-2026-10-05/generate.sh
set -e
D=media-buying-agent/outputs/ad-crosacore-video-commute-2026-10-05
V="a woman in her mid-30s with a natural, conversational, slightly tired but warm, mid-pitch American female voice, casual and unscripted-sounding, moderate pace"
BASE="Handheld front-camera selfie video, vertical 9:16, candid UGC. The woman sits in the driver's seat of her parked car in a parking garage and talks straight into the camera, $V."
END="Quiet parking garage ambience, no music, no subtitles, no on-screen text."
G="doppler run --project digigrowth --config prd -- python content-agent/tools/generate_creative.py"
$G video "$BASE She rubs her neck briefly, then says: \"Real question. Who has time to sit on MoPac forty minutes, twice a week, just to get to PT?\" $END" --model veo31 --image $D/work/actor.png --duration 8 --out $D/work/take1.mp4 &
$G video "$BASE She shrugs and smiles a little, then says: \"So there's a physical therapist in Austin who comes to your house. Private pay, and the first consult's free.\" $END" --model veo31 --image $D/work/actor.png --duration 8 --out $D/work/take2.mp4 &
$G music "lo-fi hip hop, mellow, warm, no vocals" --duration 12 --out $D/work/bed.wav &
wait
echo "Takes done. Check the transcripts and set the in/out trim points in spec.json, then run:"
echo "python media-buying-agent/tools/assemble_ugc_ad.py $D/spec.json"
