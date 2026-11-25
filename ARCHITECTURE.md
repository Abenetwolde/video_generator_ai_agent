# ARCHITECTURE.md — Pipeline Design & Boundaries

## 1. Single Contract (`storyboard.json`)
`storyboard.json` is the **only** contract between stages (`script`, `narration`, `keyframes`, `shots`, `music`, `assemble`).
Every stage validates `storyboard.json` against `schema/storyboard.schema.json` (JSON Schema Draft 2020-12) before execution and never mutates it. Sidecar state (such as `outputs/music/music_choice.json` or `.meta.json` cache manifests) lives outside `storyboard.json`.

## 2. Five-Stage Pipeline
1. `pipeline/script.py`: Audits word counts (~2–2.5 words/s) or drafts proposed shot changes with Gemini Flash (`--draft` / `--accept`).
2. `pipeline/narration.py`: Generates one WAV file per shot via Gemini Flash TTS (`outputs/narration/<shot_id>.wav`), preserving per-shot `style_instruction`, `voice`, and `language`.
3. `pipeline/keyframes.py`: Generates 3 character/style reference sheet candidates (`assets/refs/`), selects `golden_reference`, and generates centered `1024x1024` per-shot keyframes via Cloudflare Workers AI (FLUX.2 klein 4B, fallback FLUX.1 schnell).
4. `pipeline/shots.py`: Consumes Wan 2.2 TI2V-5B clips produced on Kaggle 2×T4 (`kaggle/outputs/shots/`), or falls back gracefully to deterministic FFmpeg `zoompan` Ken Burns clips (`outputs/shots/<shot_id>_<hash>.mp4`).
5. `pipeline/music.py`: Reads ACE-Step 1.5 candidates (`outputs/music/` or `kaggle/outputs/music/`), records selection in `outputs/music/music_choice.json`, or synthesizes a Tizita pentatonic placeholder.
6. `pipeline/assemble.py`: Deterministic FFmpeg assembly — builds `subtitles/film.srt`, pads/concatenates narration, sidechain-ducks score (`threshold=0.02`, `ratio=6`, `attack=300ms`, `release=1500ms`), applies two-pass EBU R128 `loudnorm` (`-14 LUFS`, `-1 dBTP`), appends `"Made with AI"` end card, and exports both `9:16` and `16:9` MP4s.

## 3. Caching, Retries, and Failure Handling
- **Input-Hash Caching:** `compute_input_hash` computes a 12-char SHA-256 over stage, model, prompt, seed, parameters, and SHA-256 hashes of all referenced images. Changing one shot invalidates only that shot's hash.
- **Retries:** `retry_with_backoff` performs 3 attempts with exponential backoff + jitter and logs `ok` / `retry` / `failed` records to `runs.jsonl`.
- **Quotas & Fallbacks:** Rate-limit/quota errors are logged to `FAILURES.md`; `keyframes.py` falls back to FLUX.1 schnell, and `shots.py` falls back to FFmpeg Ken Burns so an end-to-end film always ships.

