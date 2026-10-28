#!/usr/bin/env python3
# Replace the audio of the existing v3 video (dissolves + 2:42 pacing already baked in)
# with the dossier-writer-voice narration, each section placed at its scene start.
import subprocess

VID = "navigator_demo_v3.mp4"      # has verified dissolves + original 2:42 pacing
AUD = "vo_dossier"                 # new narration sec_1..7.mp3
OUT = "navigator_demo_v4.mp4"

# scene start offsets (original cumulative spans), ms for adelay
STARTS_MS = [0, 19680, 48792, 75576, 100416, 115920, 141504]

inputs = ["-i", VID]
for i in range(1, 8):
    inputs += ["-i", f"{AUD}/sec_{i}.mp3"]

# delay each narration input to its scene start, then mix them into one track
parts = []
for idx, ms in enumerate(STARTS_MS, start=1):
    parts.append(f"[{idx}:a]adelay={ms}|{ms}[a{idx}]")
mix_in = "".join(f"[a{i}]" for i in range(1, 8))
filt = ";".join(parts) + f";{mix_in}amix=inputs=7:normalize=0[aout]"

cmd = ["ffmpeg", "-y"] + inputs + [
    "-filter_complex", filt,
    "-map", "0:v", "-map", "[aout]",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart", OUT]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-1500:]); raise SystemExit(1)
dur = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","csv=p=0",OUT],capture_output=True,text=True).stdout.strip()
print("DONE", OUT, "dur", dur)
