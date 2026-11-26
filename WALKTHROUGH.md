# WALKTHROUGH.md — ≤5-Minute Live Demo & Architecture Script

## 1. Architecture Overview (~90 s)
- **Single Contract:** Show [storyboard.json](storyboard.json) validated against [schema/storyboard.schema.json](schema/storyboard.schema.json) (`make validate`) before every stage; no stage ever mutates `storyboard.json`.
- **Five Stages + Deterministic Assembly:**
  1. `pipeline/narration.py`: Gemini `gemini-2.5-flash-preview-tts` generates per-shot Amharic WAVs (`outputs/narration/shot_01..09.wav`, `71.17 s` spoken).
  2. `pipeline/keyframes.py`: Cloudflare Workers AI (`@cf/black-forest-labs/flux-2-klein-4b`) builds 3 character-sheet candidates → `assets/refs/golden_reference.png` → 9 centered `1024x1024` keyframes.
  3. `pipeline/shots.py`: Consumes Kaggle Wan 2.2 TI2V-5B clips when present, or emits deterministic FFmpeg `zoompan` Ken Burns clips (`24 fps`).
  4. `pipeline/music.py`: Consumes Kaggle ACE-Step 1.5 candidates or synthesizes 3 Ethiopian Tizita pentatonic candidates and writes selection to `outputs/music/music_choice.json`.
  5. `pipeline/assemble.py`: Sidechain ducking (`threshold=0.02, ratio=6, attack=300ms, release=1500ms`), `subtitles/film.srt`, two-pass `loudnorm` (`-14.02 LUFS`, `-1.15 dBTP`), `"Made with AI"` end card, and dual `9:16` + `16:9` MP4 exports.

## 2. One Hard Engineering Decision (~60 s)
- **Scoping `golden_reference.png` Conditioning to Character Shots Only:**
  - Initially, passing `golden_reference.png` + `character_description` to *all* 9 shots caused FLUX.2-klein-4b to paste the two-person portrait into landscape and macro shots (`shot_01`, `shot_03`, `shot_05`, `shot_07`).
  - Rather than abandoning identity conditioning, we modified `pipeline/keyframes.py` so `ref_images: []` omits `golden_reference` while keeping `style_block` uniform across every shot—preserving Ato Bekele & Selam's faces across character shots while restoring true shot-size variety (`extreme_wide`, `extreme_close`, `insert`).

## 3. Live Single-Shot Regeneration Proof (~90 s)
1. Change **only** `shot_07.keyframe.prompt` in `storyboard.json` (e.g., `"crimson, emerald, and gold Ethiopian tibeb patterned weft"`).
2. Run `make film`.
3. Point to stdout & [runs.jsonl](runs.jsonl):
   - `narration`: `[CACHE HIT]` on all `9/9` shots (`0 generated`).
   - `keyframes`: `[CACHE HIT]` on `8/9` shots; **only `shot_07`** generated (`outputs/keyframes/shot_07_6528f7ae891f.png`, `16,805 ms`).
   - `shots`: `[CACHE HIT]` on `8/9` shots; **only `shot_07`** rebuilt (`outputs/shots/shot_07_bc566b8fb9a3.mp4`, `1,739 ms`) because its upstream keyframe SHA-256 changed.
   - `music`: `[CACHE HIT]` on `3/3` candidates.
   - `assemble`: cleanly rebuilt `film_9x16.mp4` and `film_16x9.mp4` (`81.58 s`).

