#!/usr/bin/env python3
# Generate the ~30s data-layer INSERT narration in the EXACT dossier-writer voice
# (ElevenLabs hpp4J3VqNfWAUOO0d1Us), same model + voice settings + loudnorm chain
# as gen_dossier_voice.py, so it sits seamlessly between demo segments 2 and 3.
# Research use only — not a diagnostic system, not medical advice.
import json, urllib.request, subprocess, os

VOICE = "hpp4J3VqNfWAUOO0d1Us"
OUT = "vo_dossier"
os.makedirs(OUT, exist_ok=True)

d = json.load(open('/home/ubuntu/.config/abacusai_auth_secrets.json'))
KEY = None
for k, v in d.items():
    if 'eleven' in k.lower():
        s = v.get('secrets', v) if isinstance(v, dict) else v
        if isinstance(s, dict):
            for kk, vv in s.items():
                KEY = vv.get('value') if isinstance(vv, dict) else vv
                if KEY: break
        else:
            KEY = s
    if KEY: break
assert KEY, "no elevenlabs key found"

# name "2b" so it slots between sec_2 and sec_3
SEGMENTS = {
    "2b": ("But no A-I should ever read millions of variants — and with Navigator, it doesn't "
           "have to. Before a single agent runs, a deterministic data layer does the heavy "
           "lifting: it cleans and standardizes every variant, drops the low-quality and the "
           "common ones, and ranks what's left against the patient's symptoms. Millions of "
           "variants become a focused shortlist — the same result every time. Only then do "
           "Meta's Muse agents take over, reasoning on the handful that actually matter. That's "
           "what lets Navigator work on a real genome, not just a demo."),
}

for i, text in SEGMENTS.items():
    body = json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.6, "similarity_boost": 0.85, "use_speaker_boost": True}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}",
        data=body, headers={"xi-api-key": KEY, "Content-Type": "application/json",
        "Accept": "audio/mpeg", "User-Agent": "navigator/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        open(f"/tmp/ins_raw_{i}.mp3", "wb").write(r.read())
    subprocess.run(["ffmpeg", "-y", "-i", f"/tmp/ins_raw_{i}.mp3",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-b:a", "192k",
        f"{OUT}/sec_{i}.mp3"], check=True, capture_output=True)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", f"{OUT}/sec_{i}.mp3"], capture_output=True, text=True).stdout.strip()
    print(f"sec_{i}.mp3 dur={dur}")
