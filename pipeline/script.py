"""Stage 0/1 helper: inspect storyboard pacing or draft/refine shots with Gemini Flash."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from pipeline.common import (
    ROOT_DIR,
    compute_input_hash,
    load_env,
    retry_with_backoff,
    validate_storyboard,
)


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text.strip()))


def audit_narration(data: dict[str, Any]) -> None:
    shots = data["shots"]
    total_words = 0
    total_dur = 0.0
    print(f"{'Shot':<8} {'Dur(s)':>6} {'Words':>6} {'Amharic Text'}")
    print("-" * 72)
    for shot in shots:
        txt = shot["narration"]["text"]
        words = count_words(txt)
        dur = float(shot["duration_s"])
        total_words += words
        total_dur += dur
        preview = txt if len(txt) <= 48 else txt[:45] + "..."
        print(f"{shot['id']:<8} {dur:>6.1f} {words:>6} {preview}")

    est_sec_low = total_words / 2.5
    est_sec_high = total_words / 2.0
    print("-" * 72)
    print(f"Total duration: {total_dur:.1f}s | Total words: {total_words} (~{est_sec_low:.0f}–{est_sec_high:.0f}s spoken)")
    if not (130 <= total_words <= 220):
        print(
            f"WARNING: Total narration ({total_words} words) is outside the 130–220 word target "
            "for a 60–90s film (Amharic tends to have fewer whitespace-delimited words than English; "
            "verify actual TTS duration in the radio cut)."
        )


def draft_with_gemini(storyboard: dict[str, Any], story_brief: str, model: str) -> dict[str, Any]:
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=gemini_key)
    prompt = (
        "You are a film director drafting an 8-12 shot storyboard JSON update for 'The Heritage Short'.\n"
        f"Language: {storyboard['meta']['narration_language']} (narration) with English subtitles.\n"
        f"Audience: {storyboard['meta']['audience']}.\n"
        f"Target duration: {storyboard['meta']['target_total_seconds']} seconds.\n"
        f"Story brief:\n{story_brief}\n\n"
        "Return ONLY valid JSON matching the exact `shots` array structure of the current storyboard, "
        "preserving all required fields and keeping total narration between 130 and 220 words."
    )
    in_hash = compute_input_hash("script_draft", model, prompt, 42, {"temperature": 0.4})

    def _call() -> str:
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        return (resp.text or "").strip()

    raw = retry_with_backoff(
        _call,
        stage="script",
        shot_id="draft_shots",
        model=model,
        parameters={"temperature": 0.4},
        seed=42,
        input_hash=in_hash,
        output_path="storyboard.json (proposed)",
    )
    proposed_shots = json.loads(raw)
    updated = json.loads(json.dumps(storyboard))
    updated["shots"] = proposed_shots if isinstance(proposed_shots, list) else proposed_shots["shots"]
    return updated


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Audit or draft storyboard narration and shots.")
    parser.add_argument("--storyboard", type=Path, default=Path("storyboard.json"))
    parser.add_argument("--draft", type=str, default=None, help="3–5 sentence story brief to draft shots via Gemini.")
    parser.add_argument("--accept", action="store_true", help="Write drafted changes to storyboard.json.")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    sb_path = args.storyboard if args.storyboard.is_absolute() else ROOT_DIR / args.storyboard
    data = validate_storyboard(sb_path)

    if args.draft:
        proposed = draft_with_gemini(data, args.draft, args.model)
        old_lines = json.dumps(data, indent=2, ensure_ascii=False).splitlines(keepends=True)
        new_lines = json.dumps(proposed, indent=2, ensure_ascii=False).splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile="storyboard.json", tofile="proposed.json"))
        print(diff or "No changes proposed.")
        if args.accept:
            sb_path.write_text(json.dumps(proposed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            validate_storyboard(sb_path)
            print(f"Accepted and validated updated {sb_path}.")
        else:
            print("Dry run: pass --accept to apply this diff to storyboard.json.")
        return 0

    audit_narration(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

