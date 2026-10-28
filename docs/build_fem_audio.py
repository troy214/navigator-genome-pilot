#!/usr/bin/env python3
# Feminize the existing (too-low) female narration by pitch-shifting UP without
# formant preservation (so timbre also moves female), then loudness-normalize.
import subprocess, os, numpy as np, librosa

SRC = "vo_female"          # sec_1..7.mp3  (~157-167 Hz, reads male)
OUT = "vo_fem2"            # feminized, clearly female
os.makedirs(OUT, exist_ok=True)
SEMITONES = 4.0            # raise pitch; no -F so formants rise too -> female timbre

results = []
for i in range(1, 8):
    src = f"{SRC}/sec_{i}.mp3"
    wav_in = f"/tmp/fa_{i}_in.wav"
    wav_sh = f"/tmp/fa_{i}_sh.wav"
    out = f"{OUT}/sec_{i}.mp3"
    # to wav
    subprocess.run(["ffmpeg","-y","-i",src,"-ar","44100","-ac","1",wav_in],
                   capture_output=True, check=True)
    # pitch shift up, formants NOT preserved (feminize), high quality
    subprocess.run(["rubberband","-p",str(SEMITONES),"--pitch-hq",wav_in,wav_sh],
                   capture_output=True, check=True)
    # loudness normalize to -16 LUFS and encode mp3
    subprocess.run(["ffmpeg","-y","-i",wav_sh,"-af","loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar","44100","-b:a","192k",out], capture_output=True, check=True)
    # measure
    dur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                "-of","csv=p=0",out],capture_output=True,text=True).stdout.strip())
    y,sr = librosa.load(out, sr=16000)
    f0,vf,_ = librosa.pyin(y, fmin=60, fmax=500, sr=sr)
    med = float(np.median(f0[vf]))
    results.append((i,dur,med))
    print(f"sec_{i}.mp3  dur={dur:.3f}s  median_F0={med:.0f}Hz")

print("TOTAL_DUR", round(sum(r[1] for r in results),3))
print("MEAN_F0", round(np.mean([r[2] for r in results]),0))
