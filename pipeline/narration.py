"""Stage 1: Generate per-shot narration audio via Gemini Flash TTS with hash caching."""

from __future__ import annotations

import argparse
import base64
import os
import sys
import wave
from pathlib import Path

from google import genai
from google.genai import types

from pipeline.common import (
    ROOT_DIR,
    check_cached_output,
    compute_input_hash,
    load_env,
    retry_with_backoff,
    validate_storyboard,
    write_cache_meta,
)

NARRATION_DIR = ROOT_DIR / "outputs" / "narration"
DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"


def save_pcm_as_wav(pcm_bytes: bytes, out_path: Path, sample_rate: int = 24000) -> float:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return len(pcm_bytes) / (sample_rate * 2)


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate or 24000)


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Generate per-shot TTS narration WAV files.")
    parser.add_argument("--storyboard", type=Path, default=Path("storyboard.json"))
    parser.add_argument("--model", type=str, default=DEFAULT_TTS_MODEL)
    parser.add_argument("--force", action="store_true", help="Regenerate even if cached hash matches.")
    args = parser.parse_args()

    sb_path = args.storyboard if args.storyboard.is_absolute() else ROOT_DIR / args.storyboard
    storyboard = validate_storyboard(sb_path)

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        print("ERROR: GEMINI_API_KEY is not set.", file=sys.stderr)
        return 1

    client = genai.Client(api_key=gemini_key)
    NARRATION_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0
    for shot in storyboard["shots"]:
        shot_id = shot["id"]
        nar = shot["narration"]
        text = nar["text"].strip()
        voice = nar["voice"]
        style = nar["style_instruction"]
        lang = nar["language"]

        out_path = NARRATION_DIR / f"{shot_id}.wav"
        meta_path = NARRATION_DIR / f"{shot_id}.meta.json"
        params = {
            "voice": voice,
            "style_instruction": style,
            "language": lang,
            "char_count": len(text),
        }
        in_hash = compute_input_hash("narration", args.model, text, 42, params)

        if not args.force and check_cached_output(out_path, in_hash, meta_path):
            dur = wav_duration_seconds(out_path)
            print(f"[CACHE HIT] {shot_id}: {out_path.relative_to(ROOT_DIR)} (hash={in_hash}, {dur:.2f}s)")
            skipped += 1
            continue

        prompt = (
            f"Speak in {lang} ({'Amharic' if lang == 'am' else lang}) with a {style} delivery. "
            f"Read ONLY the following line naturally without adding any extra words:\n{text}"
        )

        def _call() -> Path:
            resp = client.models.generate_content(
                model=args.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                        )
                    ),
                ),
            )
            if not resp.candidates or not resp.candidates[0].content or not resp.candidates[0].content.parts:
                raise RuntimeError("Gemini TTS returned empty candidates/content (transient API response).")
            part = resp.candidates[0].content.parts[0]
            audio_data = part.inline_data.data
            if isinstance(audio_data, str):
                audio_data = base64.b64decode(audio_data)
            mime = getattr(part.inline_data, "mime_type", "audio/L16") or ""
            if "wav" in mime:
                out_path.write_bytes(audio_data)
            else:
                save_pcm_as_wav(audio_data, out_path, sample_rate=24000)
            return out_path

        print(f"[TTS] Generating {shot_id} ({len(text)} chars, voice={voice})...")
        retry_with_backoff(
            _call,
            stage="narration",
            shot_id=shot_id,
            model=args.model,
            parameters=params,
            seed=42,
            input_hash=in_hash,
            output_path=str(out_path.relative_to(ROOT_DIR)),
            cost_estimate_usd=0.0,
        )
        dur = wav_duration_seconds(out_path)
        write_cache_meta(
            out_path,
            in_hash,
            meta_path,
            extra={"shot_id": shot_id, "duration_s": round(dur, 3), "char_count": len(text)},
        )
        print(f"  -> Saved {out_path.relative_to(ROOT_DIR)} ({dur:.2f}s vs target {shot['duration_s']}s)")
        generated += 1

    print(f"Narration complete: {generated} generated, {skipped} cached.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

