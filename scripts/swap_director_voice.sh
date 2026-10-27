#!/usr/bin/env bash
# Regenerate the Director avatar's voice using Troy's own ElevenLabs clone.
# Run this once Troy's ElevenLabs invoice is paid. No code changes needed after.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=$(python3 -c "import json;d=json.load(open('/home/ubuntu/.config/abacusai_auth_secrets.json'))
for k,v in d.items():
    if 'eleven' in k.lower():
        s=v.get('secrets',v) if isinstance(v,dict) else v
        [print(vv.get('value') if isinstance(vv,dict) else vv) or exit() for kk,vv in s.items()]")
VOICE="${1:-5738cBvsPLDQd4RRaVkz}"   # default: TROY STUDIO VOICE (professional clone); pass YEYSULOf5XIjp3C9ixZJ for "Troy clean"
SCRIPT="I'm Troy Burns, a real human research scientist. Our team built this Navigator Genome Pilot for the Meta Hackathon. I'm the Director of the Navigator research pilot. I coordinate all eight agents, from intake through independent red-team review, and I hold them to one standard: keep what is verified separate from what is only a hypothesis. On this case, the team's leading candidate is a rare C F T R variant in the F five-oh-eight del region, consistent with cystic fibrosis. I'm flagging it as a research hypothesis only, moderate confidence, requiring expert review and orthogonal confirmation. Navigator assembles the evidence. It does not diagnose."
python3 - "$KEY" "$VOICE" "$SCRIPT" <<'PY'
import sys,json,urllib.request
key,voice,text=sys.argv[1],sys.argv[2],sys.argv[3]
body=json.dumps({"text":text,"model_id":"eleven_multilingual_v2","voice_settings":{"stability":0.5,"similarity_boost":0.85,"use_speaker_boost":True}}).encode()
req=urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",data=body,headers={"xi-api-key":key,"Content-Type":"application/json","Accept":"audio/mpeg","User-Agent":"navigator/1.0"})
with urllib.request.urlopen(req,timeout=120) as r: data=r.read()
open("app/frontend/assets/voice_director.mp3","wb").write(data); print("OK bytes",len(data))
PY
sudo systemctl reload nginx || true
echo "Done. Hard-refresh the /lab page to hear it."
