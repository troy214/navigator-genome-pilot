# Navigator — Lab Avatar Upgrade & Development Roadmap

_Working notes for Troy. Planning document — no Lab code or assets were changed when this was written; the build happens on the Mac. Navigator remains a **research tool**: it assembles evidence dossiers for researchers and clinicians, makes no diagnostic claims, and gives no medical advice._

---

## Part 1 — The Lab avatar upgrade

### Where the Lab is today

The Lab (`app/frontend/lab.html`) is a **2D composite**: one static background photo (`assets/lab_background.png`, 2048×1152) with nine agents drawn on top of it as **circular 80px headshots** (`assets/avatar_<agent>.png` + `avatar_director.png`). Each agent is a `.pod` positioned over the photo by percent coordinates in the `POS` map, and each plays its own pre-recorded clip (`assets/voice_<agent>.mp3`) when it "speaks." It reads well as a dashboard, but the agents are floating portraits, not people in a room.

**What you want:** the 8 agents + Director as realistic figures **seated at stations / standing in the lab** — people, not head-in-a-circle pods.

### The honest platform picture (verified Oct 30, 2026)

- **HeyGen** (you have an account) is the right tool, with two capabilities that matter here:
  - **Avatar IV** turns a single photo into a talking avatar, driven by audio. It handles angled/tilted poses and adds gestures and head motion.
  - The **Video Generation API** (`POST /v3/videos`) and the **Lip Sync API** (`POST /v3/lipsyncs`) both accept an **existing audio file** (`audio_url` / `audio_asset_id`, MP3/WAV). This is the key point for us: **HeyGen can lip-sync to your current recorded voice clips** — we do not have to regenerate or replace any voices. That keeps the original Lab voices intact.
  - Caveat: HeyGen avatars are framed **head-and-shoulders / upper-body**. True "full-body figure seated at a bench" is not HeyGen's native output — it animates the person, not the room. Full-body staging has to come from image generation (below), with HeyGen supplying the motion if we want them to talk.
- **Meta avatar platform ("muse"):** there is **no public Meta avatar product** to build on. Meta **Movie Gen** is a research model, not an API; **Codec Avatars** is research, not a product; Microsoft (not Meta) has a game model called "Muse." So the roadmap does **not** depend on a Meta avatar tool — it would be a dead end for the Nov 4 deadline. Meta's role in Navigator stays where it is: the **reasoning engine** behind the 8 agents.

### Three ways to build it (tradeoffs)

| Path | What it is | Keeps original voices? | Effort | Cost | Best for |
|---|---|---|---|---|---|
| **A. Static full-body composite** | Generate 9 full-body characters, composite them into a re-rendered lab scene; keep the existing hotspot + audio layer on top | Yes (unchanged) | Low–Med | One-time image gen only | **Hackathon demo** |
| **B. HeyGen audio-driven video avatars** | Feed each existing `voice_<agent>.mp3` to HeyGen; get a short talking clip per agent; play the clip when that agent speaks | Yes (HeyGen lip-syncs to them) | Med | Per-clip render credits | Phase-2 "they actually talk" |
| **C. Real-time interactive avatars** | HeyGen Interactive/Streaming avatar that responds live | No (needs live TTS) | High | Per-minute streaming API | Future / out of scope now |

### Recommendation (one line)

**Do Path A for the hackathon, architect for Path B next.** Build a re-rendered lab scene with nine realistic **full-body figures at stations**, keep the current hotspot + original-voice audio layer exactly as-is, and leave the DOM seams so each figure can later be swapped for a HeyGen talking clip without touching the data wiring.

### Path A — concrete build steps (on the Mac tomorrow)

1. **Generate 9 full-body characters** matching the existing headshots (same person per agent, same lab-coat palette), each on a transparent background, consistent lighting, seated-or-standing poses that fit a bench. Keep the Director visually distinct (center, standing).
2. **Re-render the lab scene** (or reuse `docs/lab_scene_clean_1920x1080.png` as the plate) and composite the 9 figures at believable workstation spots. Export one combined `lab_scene_peopled.png` **and** keep the figures as separate transparent PNGs (so the speaking-glow can target just the active person).
3. **In `lab.html`, keep the architecture, change the skin:**
   - Swap `.portrait` (the 80px circle + `border-radius:50%`) for a full-figure sprite: a transparent PNG anchored at the station, no circular crop.
   - Reuse the `POS` percent map — just retune each `{l,t}` to the figure's standing spot, and switch the anchor from center to bottom-center (`transform:translate(-50%,-100%)`) so figures "stand on the floor."
   - Keep the `.speaking` state, the audio preload loop, `AV` cache-buster, and every `voice_<agent>.mp3` **unchanged** — this is what preserves the original voices.
   - Bump the asset cache-buster when you replace images so the CDN doesn't serve stale art.
4. **Verify** against a real run (`?case=<id>` already flows through), then `git add` + commit on the VM when you're back.

### Path B — when you want them to actually talk (phase 2)

For each agent, upload `voice_<agent>.mp3` to HeyGen and render an Avatar-IV clip **driven by that audio** (so the voice is yours, the mouth is HeyGen's). Store the clips as `assets/talk_<agent>.mp4`. In `lab.html`, when an agent enters `.speaking`, cross-fade its static figure to its video clip and play — the audio layer stays the same file it is now. This is additive: Path A still renders if a clip is missing.

> Guardrail for both paths: the avatar work is **cosmetic**. It must not regenerate, replace, or re-voice any clip, and it must not add any language that reframes Navigator as diagnostic. Figures are lab researchers; captions stay research-only.

---

## Part 2 — Development roadmap (dual purpose: engineers **and** researchers)

The pilot already works end-to-end (8 agents → coordinator → evidence ledger → dossier + PDF, 100% top-1/top-5 on the three seeded public cases, 40 offline tests passing, genomic data-layer gate live on VCF uploads). The next steps split cleanly into "win the hackathon" and "make it a real tool."

### Track 1 — Hackathon hardening (now → Nov 4)

1. **Verify the Meta execution path end-to-end** — run at least one full case through the live Meta models (not just the dev endpoint) and capture the output; this is the single biggest open item in the status notes.
2. **Lock the demo** — Path A lab scene + the existing 3-minute video with the data-layer insert; confirm the live URL, the agent board, the evidence ledger, and the PDF download all work from a cold load.
3. **Scale story, honestly** — demo a ~100k-variant exome live (~35s through the gate) and show a **pre-computed** 5M-variant WGS artifact for scale; do not run 5M live.
4. **Submission package** — the writeups already exist (`WHY_SOLVED_CASES.md`, `DEMO_DATA_LAYER.md`, architecture map); assemble into the final submission with the research-use notice front and center.

### Track 2 — "Two-for" tooling (engineers + researchers, post-deadline)

**For researchers (the dossier consumers):**
- **Expand the benchmark** well beyond 3 cases — more solved public rare-disease cases across varied genes/inheritance, as already decided. This is the credibility metric.
- **Provenance & reproducibility** — every claim in a dossier already carries a source; harden it into a fixed, exportable evidence trail (inputs, model versions, retrieval snapshots) so a run is re-runnable and auditable.
- **Uncertainty surfacing** — keep and sharpen the uncertainty labels; researchers trust a tool that says "we're not sure" over one that doesn't.

**For engineers (the people who run/extend it):**
- **Annotate-survivors-only optimization** — the data-layer reduction (normalize → QC → rarity rank) is already sub-second; the ~17s at 50k is almost entirely the annotation join running over *all* variants. Reorder to annotate only the ~200 survivors → order-of-magnitude speedup on large inputs. (Offered earlier; not yet built.)
- **A clean researcher-facing API / CLI** — submit a VCF + phenotypes, get a dossier back; makes Navigator scriptable and embeddable, not just a web demo.
- **Evaluation harness** — one command to run the whole benchmark and print top-1/top-5 + per-agent timings, so every change is measured, not guessed.

### Track 3 — Path to real use (longer horizon)

Protocol first, patients never (per project decision): keep validating on solved public cases, then approach a **clinical research partner** for prospective, consented, de-identified evaluation — still as a research instrument producing evidence dossiers, never a diagnostic device. AWS remains the infrastructure foundation (S3 dossier storage is implemented but still needs verification).

### Suggested order of operations

1. Meta path verification (Track 1 #1) — unblocks the submission.
2. Path A lab avatars (Part 1) — the visible upgrade you asked for.
3. Lock + submit (Track 1 #2–4).
4. After Nov 4: annotate-survivors-only + benchmark expansion (Track 2), then Path B talking avatars.
