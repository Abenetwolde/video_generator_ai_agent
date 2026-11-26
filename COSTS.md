# COSTS.md — Measured Latency, Compute & Zero-Cost Accounting

All API and compute usage is parsed directly from the 61 records in [runs.jsonl](runs.jsonl). Out-of-pocket spend: **\$0.00**.

| Stage | Provider / Model | Total Calls (incl. retries) | Success Calls | Avg Success Latency (ms) | GPU Minutes | Out-of-Pocket Cost | List-Price Equivalent (Est.) |
|---|---|---|---|---|---|---|---|
| `smoke` (text) | Google `gemini-2.5-flash` | 1 | 1 | 1,228 | 0 | \$0.00 | < \$0.001 |
| `smoke` (TTS) | Google `gemini-2.5-flash-preview-tts` | 2 (1 retry) | 1 | 3,262 | 0 | \$0.00 | < \$0.001 |
| `smoke` (image) | Cloudflare `@cf/black-forest-labs/flux-2-klein-4b` | 1 | 1 | 8,757 | 0 | \$0.00 | ~\$0.003 |
| `narration` (9 shots) | Google `gemini-2.5-flash-preview-tts` | 11 (2 retries) | 9 | 5,564 | 0 | \$0.00 | ~\$0.012 |
| `keyframes` (refs + shots) | Cloudflare `@cf/black-forest-labs/flux-2-klein-4b` | 23 (1 retry) | 22 | 7,896 | 0 | \$0.00 | ~\$0.066 |
| `shots` (Ken Burns fallback) | Local FFmpeg 4.4.2 (`zoompan`) | 10 | 10 | 2,214 | 0 (Kaggle queued >2h) | \$0.00 | \$0.00 (local CPU) |
| `music` (3 Tizita candidates) | Local NumPy/SciPy Tizita synth | 3 | 3 | 5,792 | 0 (Kaggle queued >2h) | \$0.00 | \$0.00 (local CPU) |
| `assemble` (radio + rough + final ×2) | Local FFmpeg 4.4.2 | 10 | 10 | 72,095 | 0 | \$0.00 | \$0.00 (local CPU) |
| **Project Total** | — | **61** | **57** | — | **0** | **\$0.00** | **~\$0.082** |

## Frontier Commercial Comparison (Estimated)
Producing the same 9-shot, 81.5 s bilingual film using paid frontier APIs (e.g., commercial TTS + commercial text-to-image + commercial 5–10 s I2V video clips + commercial AI music) typically costs ~\$4–\$15 per iteration including retakes. Input-hash caching also avoided re-paying for 8/9 keyframes and 9/9 narrations during final single-shot iteration (`shot_07`).
