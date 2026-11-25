# The Heritage Short

A zero-cost, reproducible AI short film pipeline producing a 60–90 second Ethiopian heritage film in Amharic (`am`) with English (`en`) subtitles, original score, and `"Made with AI"` end card in both `9:16` and `16:9`.

## One-Command Run
```bash
cp .env.example .env   # fill in your local API keys (never commit .env)
make validate          # validate storyboard.json against JSON Schema 2020-12
make smoke             # 1-call-per-provider latency check
make film              # full reproducible end-to-end build
```

## Prerequisites
- Python 3.10+ (`jsonschema`, `google-genai`, `python-dotenv`, `requests`)
- FFmpeg (`ffmpeg` + `ffprobe` with `libx264`, `aac`, `subtitles`, `loudnorm`, `sidechaincompress`)
- Free-tier API keys in `.env`: `GEMINI_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `KAGGLE_API_TOKEN`

## Regenerating One Shot
Edit that single shot in `storyboard.json` (e.g., `narration.text` or `keyframe.prompt`) and re-run `make film` (or the relevant stage). Input-hash caching ensures **only the modified shot** regenerates while all unchanged shots hit cache.

## Cost
Zero out-of-pocket cost. See [COSTS.md](COSTS.md) for measured latencies and list-price equivalents.

## Repository Map
- `storyboard.json` & `schema/storyboard.schema.json` — single contract
- `pipeline/` — `validate.py`, `smoke.py`, `script.py`, `narration.py`, `keyframes.py`, `shots.py`, `music.py`, `assemble.py`
- `kaggle/` — notebooks/scripts for Wan 2.2 TI2V-5B and ACE-Step 1.5
- `runs.jsonl` — append-only structured call log
- `DESIGN.md`, `ARCHITECTURE.md`, `EXPERIMENTS.md`, `FAILURES.md`, `COSTS.md`, `ETHICS.md`
- `report/report.md` — final written project report

# video_generator_ai_agent
