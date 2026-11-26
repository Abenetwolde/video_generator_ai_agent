# The Heritage Short — Project Report

## 1. What I Set Out to Make and For Whom
I set out to build **two linked deliverables** at **\$0.00 out-of-pocket cost** (requiring no payment card and usable from Ethiopia):
1. An **81.5-second** Amharic-narrated short film with English subtitles, an original Ethiopian Tizita-inspired instrumental score, and a `"Made with AI"` end card, exported in both **`9:16`** (`1080×1920`) and **`16:9`** (`1920×1080`) for **educated Ethiopian and diaspora viewers** across mobile and desktop portals.
2. A **reproducible, contract-driven pipeline** where `storyboard.json` (validated against JSON Schema Draft 2020-12) is the single source of truth across script auditing, Amharic TTS narration, FLUX keyframe generation, motion clip synthesis/ingestion, music selection, and FFmpeg assembly.

To respect the ethics gate (`ETHICS.md`), no real person's face, likeness, or voice was depicted or cloned. Instead, the film tells the traditional Ethiopian proverb **"ድር ቢያብር አንበሳ ያስር"** (*Dir Biyabir Anbesa Yasir* — *"When spiderwebs unite, they tie a lion"*) through two fictional highland archetypes: elder weaver **Ato Bekele** and his young apprentice **Selam**.

---

## 2. What I Learned From Testing and Iteration
- **Amharic Pacing vs. Word Count:** Listening to the Phase 1 radio cut (`outputs/final/radio_cut_9x16.mp4`) confirmed that 103 Amharic words speak in **71.17 seconds** (`~1.45 words/s`), leaving natural 0.4 s breathing pauses between shots for an **81.58 s** total runtime with the 2.5 s end card.
- **Visual & Safe-Area Review:** Inspecting extracted frames from the rough cut revealed two real mobile UX failures that automated exit codes never catch:
  1. Libass interprets SRT `MarginV` and `Fontsize` in a virtual `384×288` coordinate space (`PlayResY=288`), pushing raw pixel margins (`MarginV=160`) above mid-screen on `9:16` and wrapping 2-line cues into 4–7 lines. Scaling into `288`-height space (`Fontsize=8`, `MarginV=24`) restored clean 2-line captions in the lower mobile safe area.
  2. Sizing the `"Made with AI"` end card by `height` clipped horizontally on `1080px`-wide vertical frames; sizing by `min(width, height)` fixed centering on both `9:16` and `16:9`.
- **Near-Final Cut Audience Test:** Structured in `DESIGN.md` for ≥3 educated Ethiopian/diaspora viewers to verify native pronunciation of flagged terms (*ድር ቢያብር አንበሳ ያስር*, *ሸማኔ*, *ጀበና*, *አቶ በቀለ*, *ሰላም*) and emotional resonance prior to public release.

---

## 3. The Hardest Problem and How I Solved It
Two coupled constraints defined the hardest engineering challenge: **identity consistency vs. shot variety**, and **free-tier provider boundaries**.

First, passing `assets/refs/golden_reference.png` and `character_description` to every keyframe caused `@cf/black-forest-labs/flux-2-klein-4b` to paste both characters standing side-by-side into landscape (`shot_01`), macro thread (`shot_03`), *jebena* coffee (`shot_05`), and loom insert (`shot_07`) shots. Modifying `pipeline/keyframes.py` so `ref_images: []` omits character reference conditioning while applying `style_block` uniformly preserved Ato Bekele and Selam's identity across character shots (`shot_02`, `shot_04`, `shot_06`, `shot_08`, `shot_09`) while restoring true cinematic shot-size variety.

Second, free-tier endpoints enforce tight ceilings: Gemini TTS hit `3 RPM` and `10 RPD` (`429 RESOURCE_EXHAUSTED`), and Kaggle kernels initially hit offline DNS blocks before phone verification and later remained in `status=queued` for >2 hours after verification. Building 3-attempt exponential backoff with jitter, strict input-hash caching (`compute_input_hash`), deterministic FFmpeg `zoompan` Ken Burns fallbacks (`pipeline/shots.py`), and a 3-candidate Ethiopian Tizita synthesizer (`pipeline/music.py`) guaranteed the pipeline shipped cleanly at \$0.00.

---

## 4. One Practice That Beat My Instinct — and One That Did Not
- **Beat My Instinct — Input-Hash Caching + Pre-Assembly Frame Inspection:** At first, hashing every prompt, seed, parameter dict, and reference-image SHA-256 felt like extra plumbing. In practice, it saved the project: when Gemini TTS hit its 10 RPD ceiling on `shot_09` and when we iterated `shot_07`'s *tibeb* weft prompt in Phase 3, `make film` hit `9/9` narration cache, `8/9` keyframe cache, `8/9` motion cache, and `3/3` music cache—regenerating **only** `shot_07` (`16,805 ms` keyframe + `1,739 ms` motion clip, evidenced in `runs.jsonl`).
- **Did Not Beat My Instinct — Applying English Word-Count Rules & Blanket Reference Conditioning:**
  1. `pipeline/script.py` warned that 103 words fell short of the `130–220` word heuristic for 60–90 s. Because Amharic packs prepositions, pronouns, and tense markers into single words, 103 words actually filled **71.17 s**; expanding to 150+ words would have broken the 90 s ceiling.
  2. Blanket-conditioning all 9 keyframes on `golden_reference.png` degraded composition on 5 of 9 shots until scoped exclusively to character-bearing shots.

---

## 5. Ceiling Work & Measured Results
- **Audio Engineering:** Sidechain ducking (`threshold=0.02`, `ratio=6`, `attack=300 ms`, `release=1500 ms`) plus two-pass `loudnorm` targeting `-1.2 dBTP` pre-AAC yielded **`-14.02 LUFS`** and **`-1.15 dBTP`** on the final MP4 (solving the `+0.02 dB` AAC encode overshoot observed when targeting `-1.0 dBTP` in Phase 1).
- **Compute & Cost:** Across **61 logged calls** in `runs.jsonl` (`57` ok, `4` retries absorbed automatically), out-of-pocket spend was **\$0.00** (~\$0.082 commercial list-price equivalent).
- **Remaining Ceiling:** Kaggle GPU notebooks (`wan22_i2v.ipynb`, `acestep_music.ipynb`) remained queued >2 hours on free tier; local fallbacks shipped a complete narrated, scored, subtitled film on schedule.

---

## 6. What I Would Build Next
1. Pull completed **Wan 2.2 TI2V-5B** (`720p`) clips and **ACE-Step 1.5** stems from Kaggle once a T4×2 slot clears, and run `make film` to swap them in via existing stage hooks without changing `storyboard.json`.
2. Add optional **Remotion** animated Amharic/Ge'ez title typography (`ድር ቢያብር አንበሳ ያስር`) for the opening shot and end card.
3. Complete the 3-person native Amharic speaker check (`DESIGN.md` User Test 2) and selectively regenerate only flagged lines via input-hash caching.
