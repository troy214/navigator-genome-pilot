#!/usr/bin/env python3
# Rebuild demo v3: smooth the hard-cut "flashing" with a gentle temporal dissolve
# (tmix), retime each scene to the feminized narration, mux, concat.
import subprocess, os

SRC = "navigator_demo_daniel_backup.mp4"   # original 162s footage (clean source)
AUD = "vo_fem2"                            # feminized narration sec_1..7.mp3
WORK = "rebuild_v3"
os.makedirs(WORK, exist_ok=True)

# (orig_start, orig_end)  original scene spans
SPANS = [(0.000,19.680),(19.680,48.792),(48.792,75.576),(75.576,100.416),
         (100.416,115.920),(115.920,141.504),(141.504,162.024)]
# Keep each scene's ORIGINAL footage length (no compression) so the video never
# gets shorter; the feminized narration (shorter) sits inside it with breathing
# room, and the dissolves are layered on top. Target = original span.
TGT = [e - s for (s,e) in SPANS]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL:", " ".join(cmd[:6]), "...\n", r.stderr[-1200:]); raise SystemExit(1)

scene_files = []
for i,((s,e),tgt) in enumerate(zip(SPANS,TGT), start=1):
    span = e - s
    ratio = tgt / span                 # setpts factor to retime to narration
    vout = f"{WORK}/scene{i}_v.mp4"
    aout = f"{WORK}/scene{i}.mp4"
    # video: trim -> tmix(7-frame gentle dissolve, kills flashing) -> retime -> 30fps 1080p
    vf = (f"tmix=frames=7:weights='1 1 1 1 1 1 1',"
          f"setpts={ratio:.6f}*PTS,fps=30,scale=1920:1080,setsar=1,format=yuv420p")
    run(["ffmpeg","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",SRC,
         "-an","-vf",vf,"-c:v","libx264","-preset","medium","-crf","19",vout])
    # mux feminized narration for this scene; pad audio then cut to video length
    run(["ffmpeg","-y","-i",vout,"-i",f"{AUD}/sec_{i}.mp3",
         "-af","apad","-shortest","-c:v","copy","-c:a","aac","-b:a","192k",
         "-movflags","+faststart",aout])
    d = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","csv=p=0",aout],capture_output=True,text=True).stdout.strip()
    print(f"scene{i}: span={span:.3f} -> {d}s (target {tgt})")
    scene_files.append(aout)

# concat
with open(f"{WORK}/concat.txt","w") as f:
    for sf in scene_files: f.write(f"file '{os.path.abspath(sf)}'\n")
run(["ffmpeg","-y","-f","concat","-safe","0","-i",f"{WORK}/concat.txt",
     "-c:v","libx264","-preset","medium","-crf","19","-c:a","aac","-b:a","192k",
     "-movflags","+faststart","navigator_demo_v3.mp4"])
dur = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","csv=p=0","navigator_demo_v3.mp4"],capture_output=True,text=True).stdout.strip()
print("DONE navigator_demo_v3.mp4 dur", dur)
