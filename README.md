# The Heritage Short

A zero-cost, reproducible AI short film pipeline producing an **81.5-second** Ethiopian heritage film (**"ድር ቢያብር አንበሳ ያስር" / *Dir Biyabir — When Spiderwebs Unite***) narrated in **Amharic (`am`)** with **English (`en`)** subtitles, an original Ethiopian Tizita-inspired instrumental score, and a `"Made with AI"` disclosure end card in both **`9:16`** and **`16:9`**.

## One-Command End-to-End Run
```bash
cp .env.example .env   # add your own free-tier keys (never commit .env)
make validate          # validate storyboard.json against schema/storyboard.schema.json
make smoke             # 1-call-per-provider latency check (Gemini text, Gemini TTS, Cloudflare FLUX)
make film              # full reproducible end-to-end build -> outputs/final/film_{9x16,16x9}.mp4
```

## Prerequisites
- **Python 3.10+** with `jsonschema`, `google-genai`, `python-dotenv`, `requests`, `numpy`
- **FFmpeg 4.4+** (`ffmpeg` + `ffprobe` with `libx264`, `aac`, `subtitles`, `loudnorm`, `sidechaincompress`)
- **Zero-cost environment variables** in `.env` (documented in [.env.example](.env.example)):
  - `GEMINI_API_KEY` (`gemini-2.5-flash` text + `gemini-2.5-flash-preview-tts` Amharic audio)
  - `CLOUDFLARE_ACCOUNT_ID` & `CLOUDFLARE_API_TOKEN` (`@cf/black-forest-labs/flux-2-klein-4b`, fallback `@cf/black-forest-labs/flux-1-schnell`)
  - `KAGGLE_API_TOKEN` (optional `2×T4` GPU notebooks for Wan 2.2 TI2V-5B and ACE-Step 1.5; local Ken Burns + Tizita fallbacks run automatically when offline or queued)

## Regenerating a Single Shot
Edit only the target shot in [storyboard.json](storyboard.json) (e.g., `shot_07.keyframe.prompt` or `shot_03.narration.text`) and run `make film`:
- Every stage hashes `(stage, model, prompt, seed, params, ref_file_sha256s)`.
- Unchanged shots print `[CACHE HIT]` and skip model calls; **only the edited shot** (and downstream assets referencing it) regenerates and logs to [runs.jsonl](runs.jsonl).

## Cost
**\$0.00 out-of-pocket** (~\$0.082 estimated list-price equivalent across all 61 logged calls). See [COSTS.md](COSTS.md) for per-stage latency and call counts.

## Repository Map
- [storyboard.json](storyboard.json) & [schema/storyboard.schema.json](schema/storyboard.schema.json) — single immutable contract between all stages
- [pipeline/](pipeline/common.py) — `validate.py`, `smoke.py`, `script.py`, `narration.py`, `keyframes.py`, `shots.py`, `music.py`, `assemble.py`
- [kaggle/](kaggle/README.md) — save-as-you-go Wan 2.2 TI2V-5B & ACE-Step 1.5 GPU notebooks + `push_and_run.py`
- [subtitles/film.srt](subtitles/film.srt) — generated English SRT
- [assets/refs/](assets/refs/golden_reference.png) & [assets/endcard/](assets/endcard/endcard.png) — golden reference sheet & `"Made with AI"` end card
- [runs.jsonl](runs.jsonl) — append-only structured log of every model/synthesis call
- [DESIGN.md](DESIGN.md), [ARCHITECTURE.md](ARCHITECTURE.md), [EXPERIMENTS.md](EXPERIMENTS.md), [FAILURES.md](FAILURES.md), [COSTS.md](COSTS.md), [ETHICS.md](ETHICS.md)
- [WALKTHROUGH.md](WALKTHROUGH.md), [PUBLIC_POST.md](PUBLIC_POST.md), and [report/report.md](report/report.md) (`report.pdf`, `report.docx`)
