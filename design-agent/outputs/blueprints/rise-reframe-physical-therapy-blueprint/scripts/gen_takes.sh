#!/usr/bin/env bash
cd "C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain/content-agent"
export SSL_CERT_FILE="C:/Users/dylan/AppData/Roaming/Python/Python314/site-packages/certifi/cacert.pem"
T="C:/Users/dylan/AppData/Local/Temp/claude/a9af8daf59219919/fdd1186d-201d-42b1-8758-ccf0afa93671/scratchpad/blueprint-rise-reframe/cut/takes"
C="C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain/media-buying-agent/clients/crosacore/creatives"
take() { # name still voice setting line
  doppler run --project digigrowth --config prd -- python tools/generate_creative.py video \
    "Handheld front-camera selfie video, vertical 9:16, candid UGC. $3 talks straight into the camera and says exactly: \"$5\" $4 No music, no subtitles, no on-screen text." \
    --model veo31-fast --image "$2" --duration 8 --out "$T/$1.mp4" > "$T/$1.log" 2>&1
  echo "$1 exit $?"
}
VW="The woman, early 30s, warm, wry, mid-pitch American female voice, casual and unscripted-sounding, moderate pace,"
SW="Quiet bright office ambience."
VM="The man, late 30s, relaxed, slightly exasperated but good-humored, mid-low American male voice, casual and unscripted-sounding, moderate pace,"
SM="Quiet parked car ambience."
take th-t2 "$C/video-back-by-thursday/actor.png" "$VW" "$SW" "Turns out there's a PT in Temecula who works one-on-one the whole visit." &
take th-t3 "$C/video-back-by-thursday/actor.png" "$VW" "$SW" "Normally a hundred fifty, right now it's forty-nine, and she only takes ten new patients a month." &
take sq-t2 "$C/video-back-to-square-one/actor.png" "$VM" "$SM" "So there's a PT in Temecula, Dr. BettyLou, one-on-one start to finish." &
take sq-t3 "$C/video-back-to-square-one/actor.png" "$VM" "$SM" "First visit's forty-nine bucks right now. Only ten spots a month." &
wait
echo ALL DONE
