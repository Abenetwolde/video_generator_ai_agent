# EXPERIMENTS.md — Hypotheses, Changes & Evidence

Each entry records **Hypothesis → Change → Result** backed by `runs.jsonl` logs, outputs, or listener feedback.

### Experiment 01 — Provider Smoke Test & Retry Resilience
- **Hypothesis:** Free-tier Gemini Text (`gemini-2.5-flash`), Gemini TTS (`gemini-2.5-flash-preview-tts`), and Cloudflare Workers AI (`@cf/black-forest-labs/flux-2-klein-4b`) can execute end-to-end from a clean environment without paid billing, while transient API hiccups are absorbed automatically by 3-attempt exponential backoff.
- **Change:** Implemented `pipeline/smoke.py` with `retry_with_backoff` logging every attempt to `runs.jsonl`, and ran `make smoke`.
- **Result:** All 3 providers passed (`runs.jsonl` lines 1–4):
  - `gemini-2.5-flash`: `1228 ms` (note: `max_output_tokens=64` truncated output early due to internal reasoning tokens; increased headroom needed for `script.py` drafting).
  - `gemini-2.5-flash-preview-tts`: Attempt 0 failed with `'NoneType' object has no attribute 'parts'` (`3150 ms`, logged `status="retry"`); Attempt 1 succeeded (`3262 ms`, `200,250 bytes` WAV). Added explicit empty-candidate guard in `pipeline/narration.py`.
  - `@cf/black-forest-labs/flux-2-klein-4b`: `8757 ms`, `191,122 bytes` PNG (`512x512`, 4 steps).

### Experiment 02 — Amharic Narration Word Count vs. Actual Spoken Duration
- **Hypothesis:** Standard English ~2–2.5 words/sec heuristics overestimate Amharic word count because Amharic is morphologically dense (prepositions, possessive suffixes, and verb conjugations attach to root words).
- **Change:** Drafted 9 Amharic lines (103 whitespace-delimited words total; `pipeline/script.py` flagged a warning below 130 words) and measured real `gemini-2.5-flash-preview-tts` WAV durations.
- **Result:** The 103 Amharic words spoke in **71.17 s** (`~1.45 words/s` at a warm, unhurried pace), fitting a 74–81.5 s film cleanly. Also discovered free-tier TTS caps at **3 RPM / 10 RPD** (`FAILURES.md` entries for `shot_05` and `shot_09`); exponential backoff + input-hash caching preserved all 9 WAVs (`outputs/narration/shot_01..09.wav`).

### Experiment 03 — FFmpeg `aevalsrc` Filter Quoting & Two-Pass Loudnorm AAC Headroom
- **Hypothesis:** FFmpeg filter expressions containing commas (`mod(t,2)`) require single-quoting inside `lavfi`, and `-1.0 dBTP` WAV normalization can edge to `-0.98 dBTP` after lossy AAC encoding.
- **Change:** Quoted `aevalsrc='...'` in `pipeline/music.py` and measured `radio_cut_9x16.mp4` via `loudnorm`.
- **Result:** Measured `input_i = -14.01 LUFS`, `input_tp = -0.98 dBTP` (`81.58 s`, 24 fps H.264+AAC). For Phase 3 final assembly we will target `TP=-1.2` before AAC encode so post-encode true peak stays strictly `<= -1.0 dB`.

### Experiment 04 — Golden Reference Selection & Eliminating Pose Bleed on Non-Character Shots
- **Hypothesis:** Passing a two-person `golden_reference.png` to *every* keyframe causes pose/backdrop bleed on landscape, object, and macro insert shots (`shot_01`, `shot_03`, `shot_05`, `shot_07`). Restricting `ref_images` + `character_description` to character-centric shots while applying `style_block` uniformly will restore true shot-size variety while preserving character identity.
- **Change:** Inspected 3 character-sheet candidates (`seed=1001..1003`); rejected `cand_2` (floating basket handle artifact) and chose `cand_3` (`assets/refs/golden_reference.png`, cleanest hands and Ethiopian *shemma* / *tibeb* attire). Updated `pipeline/keyframes.py` so `ref_images: []` omits `golden_reference.png` and `character_description`, and refined `storyboard.json` prompts for shots 1, 3, 4, 5, 7, 8.
- **Result:** Visual inspection of all 9 regenerated keyframes confirmed 100% character consistency across `shot_02`, `shot_04`, `shot_06`, `shot_08`, `shot_09`, and clean, un-bled macro/establishing compositions on `shot_01` (misty terraced highlands), `shot_03` (weathered hands + single thread), `shot_05` (clay pot over glowing embers + cups), and `shot_07` (loom warp + *tibeb* weft).

### Experiment 05 — Kaggle GPU Offline Block & Deterministic Ken Burns Fallback
- **Hypothesis:** Pushing Wan 2.2 TI2V-5B and ACE-Step 1.5 to Kaggle via `KAGGLE_API_TOKEN` will run on 2×T4 GPUs; if the account lacks phone verification, Kaggle disables kernel outbound internet and requires graceful local fallback.
- **Change:** Uploaded `etdev12/heritage-short-inputs` and pushed `heritage-short-acestep` and `heritage-short-wan22`; inspected kernel logs, then ran `make shots`.
- **Result:** Kaggle kernel execution failed DNS lookup (`Could not resolve host: github.com`) because unverified accounts have kernel internet disabled (`FAILURES.md`). `pipeline/shots.py` automatically generated all 9 `24 fps` Ken Burns clips (`outputs/shots/shot_01..09_*.mp4`) with shot-specific camera vectors (`slow_drift`, `push_in`, `locked`, `pan_right`, `pull_back`, `tilt_up`).

### Experiment 06 — Score Candidate Selection (3 Ethiopian Tizita Candidates)
- **Hypothesis:** Under warm elder Amharic narration, a sparse plucked *krar* + airy *washint* flute arrangement will provide richer heritage emotion than solo *krar* while avoiding low-mid masking from a *kebero* drum pulse.
- **Change:** Generated 3 Tizita pentatonic candidates (`candidate_1_krar_solo`, `candidate_2_krar_washint`, `candidate_3_krar_kebero`), compared them under `sidechaincompress` ducking, and wrote selection to `outputs/music/music_choice.json` (never mutating `storyboard.json`).
- **Result:** Selected `candidate_2_krar_washint_ba86d31cd448.wav`: *krar* arpeggios sit gently beneath the voice while intermittent *washint* phrases bloom during inter-shot breathing pauses.

### Experiment 07 — Fixing `9:16` Subtitle Overflow & End-Card Clipping via Frame Inspection
- **Hypothesis:** Passing pixel-space `MarginV=160` and `Fontsize=16` directly to FFmpeg's `subtitles` filter breaks `9:16` framing because libass defaults SRT coordinates to a `384x288` virtual canvas (`PlayResY=288`), placing subtitles mid-screen and blowing up font size; similarly, sizing end-card text from `height` overflows `1080px` width on `9:16`.
- **Change:** Extracted preview frames at `t=55s` and `t=80s`, discovered the overflow visually, then scaled `MarginV`, `MarginL/R`, and `Fontsize` into libass `288`-height space (`Fontsize=10`, `MarginV=24` on `9:16`) and sized end-card text relative to `min(width, height)` in `pipeline/assemble.py`.
- **Result:** Re-extracted `9:16` frames confirm crisp 2-line English subtitles inside the bottom mobile safe area and full, centered `"Made with AI"` end-card framing across both `9:16` and `16:9`.

### Experiment 08 — Tuning `9:16` Subtitle Line Wrapping (`Fontsize=10` → `Fontsize=8`)
- **Hypothesis:** Reducing `9:16` SRT `Fontsize` from `10` to `8` in libass `PlayResY=288` space will keep every 42-character line from wrapping onto a second line, keeping subtitles strictly `≤2` rendered lines on phone screens.
- **Change:** Updated `font_size = 8` for `aspect == "9:16"` in `pipeline/assemble.py` and re-ran `make film`.
- **Result:** Re-extracted frame `outputs/tmp_assembly/check_9x16_sub.png` at `t=55s` showed exact 2-line subtitle rendering (`"As our ancestors taught from long ago: / When spiderwebs unite, they tie a lion."`) cleanly positioned in the lower safe area.

### Experiment 09 — Sidechain Ducking & Pre-AAC Loudnorm True-Peak Margin
- **Hypothesis:** Setting `loudnorm` PCM target true peak to `-1.2 dBTP` instead of `-1.0 dBTP` compensates for lossy AAC encoding overshoot while `sidechaincompress` (`threshold=0.02, ratio=6, attack=300ms, release=1500ms`) keeps Amharic narration clear over the Tizita score.
- **Change:** Set `pcm_tp = min(true_peak, -1.2)` in `pipeline/assemble.py` and measured final `film_9x16.mp4` with FFmpeg `loudnorm=I=-14:TP=-1:LRA=11:print_format=json`.
- **Result:** Measured `input_i = -14.02 LUFS`, `input_tp = -1.15 dBTP` (strictly meeting `≈ -14 LUFS` and `≤ -1 dB` true peak).

### Experiment 10 — Live Single-Shot Regeneration Cache Proof (`shot_07`)
- **Hypothesis:** Modifying a single shot's `keyframe.prompt` in `storyboard.json` should invalidate ONLY that shot's keyframe hash and downstream motion clip hash, while leaving all other 8 keyframes, 8 motion clips, 9 TTS narrations, and 3 music candidates untouched.
- **Change:** Updated `shot_07.keyframe.prompt` in `storyboard.json` (`"crimson, emerald, and gold Ethiopian tibeb patterned weft"`) and ran `make film`.
- **Result:** Verified in stdout and `runs.jsonl`: `narration` hit `9/9` cache (`0` API calls), `keyframes` generated ONLY `shot_07` (`16,805 ms`, `shot_07_6528f7ae891f.png`, `8` cached), `shots` generated ONLY `shot_07` (`1,739 ms`, `shot_07_bc566b8fb9a3.mp4`, `8` cached), and `music` hit `3/3` cache.

### Experiment 11 — Clean-Clone Reproducibility & Secret Hygiene Check
- **Hypothesis:** Cloning the git repository into a fresh directory with only `.env` supplied will pass `make validate`, reproduce `shots`/`music`/`assemble` deterministically, and contain zero leaked secrets in tracked files or logs.
- **Change:** Audited git-tracked files for secret patterns and ran a fresh clone test of `make validate` + pipeline stages.
- **Result:** Zero secret matches across repo files and `runs.jsonl`; `make validate` and clean-clone pipeline stages executed cleanly without manual intervention.
