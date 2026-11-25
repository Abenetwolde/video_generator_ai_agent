# ETHICS.md — Consent, Licences, Provenance, and AI Labelling

## 1. Consent Record (Hard Gate)
**Status:** CLEARED — No real person depicted or voiced.

| Subject / Character | Real Person? | Likeness / Voice Used? | Consent / Basis | Agreed Scope |
|---|---|---|---|---|
| **Ato Bekele** (elder highland weaver, fictional archetype) | No | None (fictional stylized character; synthetic TTS voice) | User directive: *"no i dont use the real person just pic one person famos person proverbe"* (2026-11-25) | Fictional Ethiopian elder illustrating the traditional proverb *"ድር ቢያብር አንበሳ ያስር"* (*Dir Biyabir Anbesa Yasir*) |
| **Selam** (young apprentice / granddaughter archetype, fictional) | No | None (fictional stylized character; no voice cloning) | Same as above | Fictional apprentice learning the loom |

> **Rule:** If any real person's face, likeness, or voice is added later during revisions, generation is **blocked** until a signed/recorded consent entry (identifying person, likeness/voice scope, and agreed narration words) is added above and confirmed by the project owner.

---

## 2. Model & Tool Licences
| Component | Model / Tool | Licence / Terms | Commercial / Attribution Notes |
|---|---|---|---|
| Script drafting & TTS | Google Gemini API (Flash / Flash TTS) | Google Gemini API Terms of Service (free tier) | SynthID watermarking applied by Google where applicable; do not submit sensitive PII to free endpoints |
| Keyframe generation | FLUX.2 klein 4B (via Cloudflare Workers AI) | Apache 2.0 (note: FLUX.2 klein 9B is non-commercial — we strictly use 4B) | Check Cloudflare Workers AI Terms of Service; free daily neuron allowance |
| Keyframe fallback | FLUX.1 schnell (via Cloudflare Workers AI) | Apache 2.0 | Open weights, commercial use permitted |
| Video generation (I2V) | Wan 2.2 TI2V-5B (via Kaggle 2×T4) | Apache 2.0 | Open weights; Kaggle Terms apply to notebook compute |
| Music generation | ACE-Step 1.5 (via Kaggle/Colab) | MIT Licence | Commercial use permitted; instrumental score only |
| Local assembly & fallback | FFmpeg (`zoompan`, `loudnorm`, `sidechaincompress`) | LGPL / GPL depending on build | Local execution, zero external data transfer |

---

## 3. Labelling & Provenance Plan
1. **In-video End Card:** Explicit `"Made with AI"` end card (2.5 s) appended to both `9:16` and `16:9` exports (`assets/endcard/`).
2. **Platform AI Label:** Enable the platform's AI-generated content disclosure toggle when publishing on social/video platforms (TikTok, YouTube Shorts, Instagram Reels, YouTube).
3. **Watermark & Metadata Preservation:** Retain upstream SynthID/C2PA provenance where generated, and avoid stripping container metadata intentionally during final export.

---

## 4. Private-Data & Free-Endpoint Note
Because this pipeline uses zero-cost/free-tier APIs (Google Gemini free tier, Cloudflare Workers AI free tier, Kaggle public/private notebooks), **no private personal data, real family photos, or sensitive PII** are transmitted to external endpoints. All story text and prompts describe fictional archetypes and shared Ethiopian cultural heritage.

