#!/usr/bin/env python3
import subprocess, os, numpy as np, librosa
from PIL import Image

VID = "navigator_demo_v3.mp4"

# --- VIDEO: sample lab scene at 30fps, inspect transition profiles ---
tmp = "/tmp/v3lab"; os.makedirs(tmp, exist_ok=True)
for f in os.listdir(tmp): os.remove(os.path.join(tmp,f))
# lab scene in v3 ~ 46s..70s
subprocess.run(["ffmpeg","-y","-ss","46","-to","70","-i",VID,
                "-vf","fps=30,scale=160:90",f"{tmp}/f_%04d.png"],capture_output=True)
fs=sorted(os.listdir(tmp)); prev=None; diffs=[]
for f in fs:
    a=np.array(Image.open(os.path.join(tmp,f)).convert('L'),float)
    if prev is not None: diffs.append(float(np.mean(np.abs(a-prev))))
    prev=a
d=np.array(diffs)
# A hard cut = single frame diff>20 with both neighbors <4.
# A dissolve  = a run of >=3 consecutive frames with diff between 3 and 20.
hard=0; diss=0; i=1
while i < len(d)-1:
    if d[i] > 20 and d[i-1] < 4 and d[i+1] < 4:
        hard+=1; i+=1
    elif d[i] > 3:
        run=0; j=i
        while j < len(d) and d[j] > 3: run+=1; j+=1
        if run>=3: diss+=1
        i=j
    else: i+=1
print(f"LAB 30fps: frames={len(fs)} maxdiff={d.max():.0f} isolated-hard-cuts={hard} dissolve-runs={diss}")

# --- AUDIO: F0 across 3 regions ---
for lbl,ss,t in [("intro",2,12),("lab",58,12),("outro",135,10)]:
    w=f"/tmp/vf_{lbl}.wav"
    subprocess.run(["ffmpeg","-y","-ss",str(ss),"-t",str(t),"-i",VID,"-vn","-ar","16000","-ac","1",w],capture_output=True)
    y,sr=librosa.load(w,sr=16000)
    f0,vf,_=librosa.pyin(y,fmin=60,fmax=500,sr=sr)
    print(f"AUDIO {lbl}: median F0 = {np.median(f0[vf]):.0f} Hz")
