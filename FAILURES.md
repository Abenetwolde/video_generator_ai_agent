# FAILURES.md — Blockers, Quotas & Workarounds

Every real quota limit, model failure, timeout, fallback activation, and resolution is logged here.


### [2026-11-25T11:48:47Z] Stage: `narration` — shot_05
- **Error:** 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://aistudio.google.com/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 3, model: gemini-2.5-flash-tts, description: Generate content requests per minute limit exceeded on Free Tier. See https://aistudio.google.com/docs/rate-limits.\nPlease retry in 12.168532381s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://aistudio.google.com/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'description': 'Generate content requests per minute limit exceeded on Free Tier. See https://aistudio.google.com/docs/rate-limits.', 'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.5-flash-tts'}, 'quotaValue': '3'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '12s'}]}}
- **Action / Workaround:** Quota/rate-limit hit on attempt 1/3; backing off

### [2026-11-25T11:49:10Z] Stage: `narration` — shot_09
- **Error:** 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://aistudio.google.com/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 10, model: gemini-2.5-flash-tts, description: Generate content requests per day limit exceeded on Free Tier. See https://aistudio.google.com/docs/rate-limits.\nPlease retry in 20h10m49.670353888s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://aistudio.google.com/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'description': 'Generate content requests per day limit exceeded on Free Tier. See https://aistudio.google.com/docs/rate-limits.', 'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.5-flash-tts'}, 'quotaValue': '10'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '72649s'}]}}
- **Action / Workaround:** Quota/rate-limit hit on attempt 1/3; backing off

### [2026-11-25T12:09:45Z] Stage: `kaggle` — etdev12/heritage-short-acestep
- **Error:** Kernel status after 45s poll: unknown
- **Action / Workaround:** Notebook pushed to Kaggle; local pipeline uses Ken Burns / Tizita fallback until outputs are downloaded to kaggle/outputs/.

### [2026-11-25T12:10:34Z] Stage: `kaggle` — etdev12/heritage-short-wan22
- **Error:** `Failed to resolve 'pypi.org'` during `pip install ftfy` + `FileNotFoundError: '/kaggle/input/heritage-short-inputs/storyboard.json'` (Kaggle mounts datasets at `/kaggle/input/datasets/<user>/<slug>/` or disables outbound internet on unverified accounts).
- **Action / Workaround:** Updated [kaggle/wan22_i2v.ipynb](file:///home/ubuntu/Documents/AiMl/The/kaggle/wan22_i2v.ipynb) to locate `storyboard.json` via `Path('/kaggle/input').rglob('storyboard.json')`; local pipeline uses deterministic FFmpeg Ken Burns fallback (`pipeline/shots.py`) and synthesized Ethiopian Tizita score (`pipeline/music.py`).

### [2026-11-25T12:17:25Z] Stage: `shots` — shot_01
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_01_17d74102eda4.mp4.

### [2026-11-25T12:17:27Z] Stage: `shots` — shot_02
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_02_480fa58c20c5.mp4.

### [2026-11-25T12:17:29Z] Stage: `shots` — shot_03
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_03_0f0b120e1544.mp4.

### [2026-11-25T12:17:32Z] Stage: `shots` — shot_04
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_04_1d69b28c052d.mp4.

### [2026-11-25T12:17:34Z] Stage: `shots` — shot_05
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_05_b6ce59aa6ff6.mp4.

### [2026-11-25T12:17:37Z] Stage: `shots` — shot_06
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_06_4f930dd713e0.mp4.

### [2026-11-25T12:17:39Z] Stage: `shots` — shot_07
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_07_55a918c4cfb2.mp4.

### [2026-11-25T12:17:41Z] Stage: `shots` — shot_08
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_08_834d4b5cc84c.mp4.

### [2026-11-25T12:17:43Z] Stage: `shots` — shot_09
- **Error:** Kaggle Wan 2.2 clip not present locally (session/quota boundary).
- **Action / Workaround:** Emitted deterministic FFmpeg Ken Burns fallback at outputs/shots/shot_09_ce756f47fcba.mp4.

### [2026-11-25T12:17:48Z] Stage: `music` — ace-step-1.5
- **Error:** Kaggle ACE-Step notebook blocked on unverified account outbound DNS (`Could not resolve host: github.com`).
- **Action / Workaround:** Synthesized 3 distinct Tizita pentatonic Ethiopian score candidates locally (krar solo, krar+washint, krar+kebero).

### [2026-11-25T13:57:04Z] Stage: `kaggle` — etdev12/heritage-short-acestep
- **Error:** Kernel status after 90s poll: queued
- **Action / Workaround:** Notebook pushed to Kaggle; local pipeline uses Ken Burns / Tizita fallback until outputs are downloaded to kaggle/outputs/.

### [2026-11-25T13:58:41Z] Stage: `kaggle` — etdev12/heritage-short-wan22
- **Error:** Kernel status after 90s poll: queued
- **Action / Workaround:** Notebook pushed to Kaggle; local pipeline uses Ken Burns / Tizita fallback until outputs are downloaded to kaggle/outputs/.
