"""Stage 4: Select ACE-Step candidates or synthesize 3 distinct Tizita Ethiopian score candidates."""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np

from pipeline.common import (
    ROOT_DIR,
    append_failure,
    append_run_log,
    check_cached_output,
    compute_input_hash,
    load_env,
    validate_storyboard,
    write_cache_meta,
)

MUSIC_DIR = ROOT_DIR / "outputs" / "music"
MUSIC_CHOICE_PATH = ROOT_DIR / "outputs" / "music" / "music_choice.json"
KAGGLE_MUSIC_DIR = ROOT_DIR / "kaggle" / "outputs" / "music"

# C major / Ethiopian Tizita major pentatonic scale frequencies (Hz): C, D, E, G, A
TIZITA_HZ = [130.81, 146.83, 164.81, 196.00, 220.00, 261.63, 293.66, 329.63, 392.00, 440.00, 523.25]


def _write_stereo_wav(path: Path, stereo: np.ndarray, sr: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(stereo, -0.95, 0.95)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def _karplus_strong_note(freq: float, dur_s: float, sr: int = 24000, damping: float = 0.996) -> np.ndarray:
    """Warm plucked string synthesis (krar acoustic timbre)."""
    n_samples = int(dur_s * sr)
    period = max(2, int(round(sr / freq)))
    rng = np.random.default_rng(int(freq * 100))
    buf = rng.uniform(-0.8, 0.8, period).astype(np.float64)
    # Soften initial pluck with simple low-pass
    buf = np.convolve(buf, [0.25, 0.5, 0.25], mode="same")
    out = np.zeros(n_samples, dtype=np.float64)
    idx = 0
    for i in range(n_samples):
        out[i] = buf[idx]
        nxt = (idx + 1) % period
        buf[idx] = damping * 0.5 * (buf[idx] + buf[nxt])
        idx = nxt
    env = np.minimum(1.0, np.arange(n_samples) / max(1, int(0.012 * sr)))
    fade_out = np.minimum(1.0, (n_samples - np.arange(n_samples)) / max(1, int(0.08 * sr)))
    return out * env * fade_out


def _washint_phrase(freq: float, dur_s: float, sr: int = 24000) -> np.ndarray:
    """Airy bamboo flute (washint) with gentle vibrato and breathiness."""
    n = int(dur_s * sr)
    t = np.arange(n) / sr
    vib = 1.0 + 0.004 * np.sin(2 * np.pi * 4.8 * t)
    phase = 2 * np.pi * freq * np.cumsum(vib) / sr
    tone = 0.70 * np.sin(phase) + 0.20 * np.sin(2 * phase) + 0.06 * np.sin(3 * phase)
    rng = np.random.default_rng(int(freq * 13))
    breath = rng.normal(0, 0.025, n)
    att = np.minimum(1.0, t / 0.18)
    rel = np.minimum(1.0, (dur_s - t) / 0.25)
    return (tone + breath) * att * np.maximum(0.0, rel)


def synthesize_tizita_candidate(
    out_path: Path,
    duration_s: float,
    tempo_bpm: int,
    variant: int,
    sr: int = 24000,
) -> None:
    """Synthesize one of 3 distinct instrumental Ethiopian Tizita score candidates."""
    n_total = int(duration_s * sr)
    left = np.zeros(n_total, dtype=np.float64)
    right = np.zeros(n_total, dtype=np.float64)
    beat_s = 60.0 / max(40, tempo_bpm)

    # Traditional 6-beat / 4-beat krar ostinato motif in Tizita pentatonic
    if variant == 1:
        # Variant 1: Sparse contemplative krar solo (intimate, wide headroom)
        pattern = [5, 7, 8, 7, 5, 3, 4, 5]
        step_beats = 1.0
        damping = 0.9965
    elif variant == 2:
        # Variant 2: Warm krar ostinato + airy washint bamboo flute phrases
        pattern = [5, 7, 8, 9, 8, 7, 5, 4]
        step_beats = 0.75
        damping = 0.996
    else:
        # Variant 3: Rhythmic krar + soft kebero hand-drum pulse (6/8 feel)
        pattern = [5, 6, 7, 8, 7, 6, 5, 3, 4, 5, 7, 5]
        step_beats = 0.5
        damping = 0.995

    step_s = beat_s * step_beats
    t_cursor = 0.2
    idx = 0
    while t_cursor < duration_s - 1.0:
        note_freq = TIZITA_HZ[pattern[idx % len(pattern)]]
        note = _karplus_strong_note(note_freq, min(2.4, duration_s - t_cursor), sr=sr, damping=damping)
        start_i = int(t_cursor * sr)
        end_i = min(n_total, start_i + len(note))
        seg = note[: end_i - start_i]
        pan = 0.42 if (idx % 2 == 0) else 0.58
        left[start_i:end_i] += seg * (1.0 - pan) * 0.45
        right[start_i:end_i] += seg * pan * 0.45

        # Gentle bass root drone on phrase downbeats
        if idx % len(pattern) == 0:
            bass = _karplus_strong_note(130.81, min(3.5, duration_s - t_cursor), sr=sr, damping=0.9975) * 0.32
            b_end = min(n_total, start_i + len(bass))
            left[start_i:b_end] += bass[: b_end - start_i] * 0.5
            right[start_i:b_end] += bass[: b_end - start_i] * 0.5

        # Variant 2 adds airy washint bamboo flute every 4 beats
        if variant == 2 and idx % 4 == 0 and t_cursor + 2.5 < duration_s:
            flute_hz = TIZITA_HZ[7 + (idx // 4) % 3]
            flute = _washint_phrase(flute_hz, min(2.4, duration_s - t_cursor), sr=sr) * 0.16
            f_end = min(n_total, start_i + len(flute))
            left[start_i:f_end] += flute[: f_end - start_i] * 0.45
            right[start_i:f_end] += flute[: f_end - start_i] * 0.55

        # Variant 3 adds soft kebero low-frequency pulse
        if variant == 3 and idx % 3 == 0:
            k_len = int(0.18 * sr)
            kt = np.arange(k_len) / sr
            kebero = np.sin(2 * np.pi * (82.0 * np.exp(-12 * kt) + 48.0) * kt) * np.exp(-18 * kt) * 0.25
            k_end = min(n_total, start_i + k_len)
            left[start_i:k_end] += kebero[: k_end - start_i] * 0.5
            right[start_i:k_end] += kebero[: k_end - start_i] * 0.5

        t_cursor += step_s
        idx += 1

    # Smooth fade-in and fade-out
    fade_in = min(n_total, int(1.5 * sr))
    fade_out = min(n_total, int(2.5 * sr))
    left[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    right[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    left[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)
    right[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)

    stereo = np.stack([left, right], axis=1)
    peak = np.max(np.abs(stereo)) or 1.0
    stereo = stereo / max(peak, 1.0) * 0.55
    _write_stereo_wav(out_path, stereo, sr=sr)


def synthesize_pentatonic_placeholder(out_path: Path, duration_s: float, tempo_bpm: int) -> None:
    """Backward-compatible wrapper used by assemble.py --radio-cut."""
    synthesize_tizita_candidate(out_path, duration_s, tempo_bpm, variant=2)


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Generate or select 3 score candidates without mutating storyboard.json.")
    parser.add_argument("--storyboard", type=Path, default=Path("storyboard.json"))
    parser.add_argument("--choice", type=int, default=2, choices=[1, 2, 3], help="Candidate index (1..3) to select.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    sb_path = args.storyboard if args.storyboard.is_absolute() else ROOT_DIR / args.storyboard
    storyboard = validate_storyboard(sb_path)
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    total_s = sum(float(s["duration_s"]) for s in storyboard["shots"]) + float(storyboard["end_card"]["duration_s"]) + 1.0
    cue = storyboard["shots"][0]["music_cue"]
    params = {
        "tempo_bpm": cue["tempo_bpm"],
        "key": cue["key"],
        "duration_s": round(total_s, 2),
    }

    # Prefer Kaggle ACE-Step outputs if downloaded
    kaggle_cands = sorted(KAGGLE_MUSIC_DIR.glob("candidate_*.wav")) if KAGGLE_MUSIC_DIR.exists() else []
    candidates: list[Path] = []

    if len(kaggle_cands) >= 1:
        candidates = kaggle_cands
        print(f"[MUSIC] Found {len(candidates)} ACE-Step candidate(s) in kaggle/outputs/music/")
    else:
        labels = {
            1: "krar_solo",
            2: "krar_washint",
            3: "krar_kebero",
        }
        logged_fallback = False
        for idx in (1, 2, 3):
            seed = 5000 + idx
            c_params = {**params, "variant": idx, "label": labels[idx]}
            in_hash = compute_input_hash("music", "tizita-synth-fallback", cue["caption"], seed, c_params)
            cand_path = MUSIC_DIR / f"candidate_{idx}_{labels[idx]}_{in_hash}.wav"
            meta_path = MUSIC_DIR / f"candidate_{idx}_{labels[idx]}_{in_hash}.meta.json"
            if not args.force and check_cached_output(cand_path, in_hash, meta_path):
                print(f"[CACHE HIT] Score candidate {idx}: {cand_path.relative_to(ROOT_DIR)}")
                candidates.append(cand_path)
                continue

            t0 = time.monotonic()
            synthesize_tizita_candidate(cand_path, total_s, int(cue["tempo_bpm"]), variant=idx)
            latency_ms = int((time.monotonic() - t0) * 1000)
            append_run_log(
                stage="music",
                shot_id=f"candidate_{idx}",
                model="tizita-synth-fallback",
                parameters=c_params,
                seed=seed,
                latency_ms=latency_ms,
                cost_estimate_usd=0.0,
                input_hash=in_hash,
                output_path=str(cand_path.relative_to(ROOT_DIR)),
                status="ok",
                retry_count=0,
            )
            if not logged_fallback:
                append_failure(
                    "music",
                    "ace-step-1.5",
                    "Kaggle ACE-Step notebook blocked on unverified account outbound DNS (`Could not resolve host: github.com`).",
                    "Synthesized 3 distinct Tizita pentatonic Ethiopian score candidates locally (krar solo, krar+washint, krar+kebero).",
                )
                logged_fallback = True
            write_cache_meta(cand_path, in_hash, meta_path)
            print(f"[MUSIC] Generated candidate {idx}/3 -> {cand_path.relative_to(ROOT_DIR)}")
            candidates.append(cand_path)

    chosen_idx = min(args.choice - 1, len(candidates) - 1)
    chosen_path = candidates[chosen_idx]
    choice_payload = {
        "chosen_index": args.choice,
        "chosen_candidate_path": str(chosen_path.relative_to(ROOT_DIR)),
        "candidates": [str(c.relative_to(ROOT_DIR)) for c in candidates],
        "rationale": (
            "Candidate 2 (warm krar ostinato + airy washint flute) provides organic melodic warmth "
            "above and below the elder Amharic vocal register without rhythmic percussion masking narration."
        ),
    }
    MUSIC_CHOICE_PATH.write_text(json.dumps(choice_payload, indent=2) + "\n", encoding="utf-8")
    print(f"[MUSIC] Selected candidate {args.choice}: {chosen_path.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
