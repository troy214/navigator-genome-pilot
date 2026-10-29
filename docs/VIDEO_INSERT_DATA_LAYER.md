# Demo Video — ~30-Second Data-Layer Insert

A short insert to add the data-layer story to the existing 3-minute demo **without rewriting it**.
Written to match the current narration voice (the Dossier-Writer: "authoritative but warm lead
author"), spelled-out acronyms, research-only framing.

## Where it goes

Drop it **between the current segment 2 and segment 3** — right after the line
"...the true answer is usually buried among them" and before "Here is the team at work, in a live
research lab." Segment 2 already says a genome holds millions of variants, so this is the natural
hand-off: it answers "so how do you deal with millions?" before the agents appear.

## Visual

Full-screen the architecture map **`docs/data_layer_map_1680x830.png`** for the whole insert
(a slow push-in / Ken Burns works well). Optional: end the insert by dissolving from the map's
"candidate set" pill into the lab scene that opens segment 3.

## Narration script (the insert)

> "But no A-I should ever read millions of variants — and with Navigator, it doesn't have to.
> Before a single agent runs, a deterministic data layer does the heavy lifting: it cleans and
> standardizes every variant, drops the low-quality and the common ones, and ranks what's left
> against the patient's symptoms. Millions of variants become a focused shortlist — the same
> result every time. Only then do Meta's Muse agents take over, reasoning on the handful that
> actually matter. That's what lets Navigator work on a real genome, not just a demo."

- **Word count:** ~95 words → about **30–34 seconds** at the demo's narration pace.
- **Tight 25-second alternative** (if you need to protect the 3-minute total), cut the middle sentence:

> "But no A-I should ever read millions of variants — and with Navigator, it doesn't have to.
> Before a single agent runs, a deterministic data layer cleans, filters, and ranks them down to a
> focused shortlist — the same result every time. Only then do Meta's Muse agents reason on the
> handful that actually matter. That's what lets Navigator work on a real genome, not just a demo."

## How to record it in the same voice

Use the existing narration pipeline so the voice matches exactly:
- Voice ID: `hpp4J3VqNfWAUOO0d1Us` (the Dossier-Writer voice already used throughout).
- Model `eleven_multilingual_v2`; voice settings `stability 0.6, similarity_boost 0.85,
  use_speaker_boost true`; then loudnorm `I=-16:TP=-1.5:LRA=11` at 44.1 kHz / 192 kbps —
  identical to `docs/gen_dossier_voice.py` so it sits seamlessly next to the other segments.
- Per the standing plan, the actual cut/dissolve is done by hand in iMovie.

*Research use only — not a diagnostic system, not medical advice.*
