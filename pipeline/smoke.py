"""Smoke test: one call per provider (Gemini text, Gemini TTS, Cloudflare FLUX)."""

from __future__ import annotations

import base64
import os
import sys
import wave
from pathlib import Path

import requests
from google import genai
from google.genai import types

from pipeline.common import (
    ROOT_DIR,
    append_failure,
    compute_input_hash,
    load_env,
    redact_secrets,
    retry_with_backoff,
)

SMOKE_DIR = ROOT_DIR / "outputs" / "smoke"


def save_pcm_as_wav(pcm_bytes: bytes, out_path: Path, sample_rate: int = 24000) -> None:
    """Wrap raw 16-bit mono PCM bytes from Gemini TTS into a standard WAV container."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def smoke_gemini_text(client: genai.Client) -> tuple[bool, str]:
    candidates = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    prompt = "Translate this Ethiopian proverb into one concise English sentence: ድር ቢያብር አንበሳ ያስር"
    for model in candidates:
        in_hash = compute_input_hash("smoke_text", model, prompt, 42, {"max_output_tokens": 64})
        try:
            def _call() -> str:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(max_output_tokens=64, temperature=0.2),
                )
                return (resp.text or "").strip()

            text = retry_with_backoff(
                _call,
                stage="smoke",
                shot_id="smoke_gemini_text",
                model=model,
                parameters={"max_output_tokens": 64, "temperature": 0.2},
                seed=42,
                input_hash=in_hash,
                output_path="stdout",
                max_attempts=2,
            )
            return True, f"{model}: {text}"
        except Exception as exc:  # noqa: BLE001
            last_err = redact_secrets(str(exc))
    append_failure("smoke", "gemini_text", last_err, "All candidate Gemini text models failed during smoke test.")
    return False, last_err


def smoke_gemini_tts(client: genai.Client) -> tuple[bool, str]:
    model = "gemini-2.5-flash-preview-tts"
    text = "ሰላም። ድር ቢያብር አንበሳ ያስር።"
    voice = "Charon"
    out_path = SMOKE_DIR / "smoke_tts.wav"
    params = {"voice": voice, "response_modalities": ["AUDIO"], "language": "am"}
    in_hash = compute_input_hash("smoke_tts", model, text, 42, params)

    try:
        def _call() -> Path:
            resp = client.models.generate_content(
                model=model,
                contents=f"Speak warmly, calmly, and clearly in Amharic: {text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                        )
                    ),
                ),
            )
            part = resp.candidates[0].content.parts[0]
            audio_data = part.inline_data.data
            if isinstance(audio_data, str):
                audio_data = base64.b64decode(audio_data)
            mime = getattr(part.inline_data, "mime_type", "audio/L16") or ""
            if "wav" in mime:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(audio_data)
            else:
                save_pcm_as_wav(audio_data, out_path, sample_rate=24000)
            return out_path

        saved = retry_with_backoff(
            _call,
            stage="smoke",
            shot_id="smoke_gemini_tts",
            model=model,
            parameters=params,
            seed=42,
            input_hash=in_hash,
            output_path=str(out_path.relative_to(ROOT_DIR)),
            max_attempts=2,
        )
        return True, f"{model} -> {saved.relative_to(ROOT_DIR)} ({saved.stat().st_size} bytes)"
    except Exception as exc:  # noqa: BLE001
        err = redact_secrets(str(exc))
        append_failure("smoke", "gemini_tts", err, "Gemini TTS smoke test failed.")
        return False, err


def smoke_cloudflare_flux() -> tuple[bool, str]:
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not token:
        return False, "Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN"

    models = [
        "@cf/black-forest-labs/flux-2-klein-4b",
        "@cf/black-forest-labs/flux-1-schnell",
    ]
    prompt = "Traditional Ethiopian wooden loom in warm morning sunlight, cinematic photography"
    out_path = SMOKE_DIR / "smoke_flux.png"
    last_err = "unknown"

    for model in models:
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        params = {"steps": 4, "width": 512, "height": 512}
        in_hash = compute_input_hash("smoke_flux", model, prompt, 101, params)

        def _call() -> Path:
            headers = {"Authorization": f"Bearer {token}"}
            if "flux-2-klein" in model:
                # flux-2-klein accepts multipart/form-data or JSON depending on endpoint version
                resp = requests.post(
                    url,
                    headers=headers,
                    files={"prompt": (None, prompt), "steps": (None, "4"), "width": (None, "512"), "height": (None, "512")},
                    timeout=60,
                )
            else:
                resp = requests.post(
                    url,
                    headers=headers,
                    json={"prompt": prompt, "steps": 4, "seed": 101},
                    timeout=60,
                )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            ctype = resp.headers.get("Content-Type", "")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if "image/" in ctype:
                out_path.write_bytes(resp.content)
            else:
                payload = resp.json()
                img_b64 = payload.get("result", {}).get("image") or payload.get("image")
                if not img_b64:
                    raise RuntimeError(f"Unexpected JSON payload: {str(payload)[:300]}")
                out_path.write_bytes(base64.b64decode(img_b64))
            return out_path

        try:
            saved = retry_with_backoff(
                _call,
                stage="smoke",
                shot_id="smoke_cloudflare_flux",
                model=model,
                parameters=params,
                seed=101,
                input_hash=in_hash,
                output_path=str(out_path.relative_to(ROOT_DIR)),
                max_attempts=2,
            )
            return True, f"{model} -> {saved.relative_to(ROOT_DIR)} ({saved.stat().st_size} bytes)"
        except Exception as exc:  # noqa: BLE001
            last_err = redact_secrets(str(exc))

    append_failure("smoke", "cloudflare_flux", last_err, "All Cloudflare FLUX models failed during smoke test.")
    return False, last_err


def main() -> int:
    load_env()
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        print("ERROR: GEMINI_API_KEY not set.", file=sys.stderr)
        return 1

    client = genai.Client(api_key=gemini_key)
    results = []
    for label, fn in (
        ("Gemini Text", lambda: smoke_gemini_text(client)),
        ("Gemini TTS", lambda: smoke_gemini_tts(client)),
        ("Cloudflare FLUX", smoke_cloudflare_flux),
    ):
        ok, detail = fn()
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label}: {detail}")
        results.append(ok)

    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

