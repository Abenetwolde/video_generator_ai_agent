# COSTS.md — Measured Latency, Compute & Zero-Cost Accounting

All API and compute usage is tracked from `runs.jsonl`. Out-of-pocket cost: **\$0.00**.

| Stage | Provider / Model | Calls (incl. retries) | Avg Success Latency (ms) | GPU Minutes | Out-of-Pocket Cost | List-Price Equivalent (Est.) |
|---|---|---|---|---|---|---|
| `smoke` (text) | Google `gemini-2.5-flash` | 1 | 1,228 | 0 | \$0.00 | < \$0.001 |
| `smoke` (TTS) | Google `gemini-2.5-flash-preview-tts` | 2 (1 retry) | 3,262 | 0 | \$0.00 | < \$0.001 |
| `smoke` (image) | Cloudflare `@cf/black-forest-labs/flux-2-klein-4b` | 1 | 8,757 | 0 | \$0.00 | ~\$0.003 |
| `narration` (9 shots) | Google `gemini-2.5-flash-preview-tts` | 11 (2 retries) | 5,564 | 0 | \$0.00 | ~\$0.01 |
| `keyframes` (refs + shots) | Cloudflare `@cf/black-forest-labs/flux-2-klein-4b` | 22 (1 retry) | 7,472 | 0 | \$0.00 | ~\$0.066 |
| `shots` (9 Ken Burns clips) | Local FFmpeg 4.4.2 (`zoompan`) | 9 | 2,266 | 0 (Kaggle offline block) | \$0.00 | \$0.00 (local CPU) |
| `music` (3 Tizita candidates) | Local NumPy/SciPy Tizita synth | 3 | 5,792 | 0 (Kaggle offline block) | \$0.00 | \$0.00 (local CPU) |
| `assemble` (radio + rough cut ×2) | Local FFmpeg 4.4.2 | 6 | ~67,000 | 0 | \$0.00 | \$0.00 (local CPU) |
| **Phase 1 + 2 Total** | — | **55** | — | **0** | **\$0.00** | **~\$0.08** |

*(Note: Kaggle `2×T4` GPU notebooks are uploaded and ready in `kaggle/` for optional Wan 2.2 + ACE-Step runs once the `etdev12` account completes phone verification for outbound internet access.)*
