"""Stage 2: Generate character/style reference sheet and per-shot keyframes via Cloudflare FLUX."""

from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Any

import requests

from pipeline.common import (
    ROOT_DIR,
    append_failure,
    check_cached_output,
    compute_input_hash,
    is_quota_or_rate_error,
    load_env,
    retry_with_backoff,
    validate_storyboard,
    write_cache_meta,
)

KEYFRAMES_DIR = ROOT_DIR / "outputs" / "keyframes"
REFS_DIR = ROOT_DIR / "assets" / "refs"
FALLBACK_MODEL = "@cf/black-forest-labs/flux-1-schnell"


def invoke_cloudflare_flux(
    account_id: str,
    token: str,
    model: str,
    prompt: str,
    negative_prompt: str,
    seed: int,
    width: int,
    height: int,
    steps: int = 4,
    ref_images: list[Path] | None = None,
) -> bytes:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {token}"}

    if "flux-2" in model:
        files: list[tuple[str, tuple[str | None, Any, str | None] | tuple[None, str]]] = [
            ("prompt", (None, prompt)),
            ("negative_prompt", (None, negative_prompt)),
            ("seed", (None, str(seed))),
            ("width", (None, str(width))),
            ("height", (None, str(height))),
            ("steps", (None, str(steps))),
        ]
        for idx, ref_path in enumerate((ref_images or [])[:4]):
            if ref_path.exists():
                files.append((f"input_image_{idx}", (ref_path.name, ref_path.read_bytes(), "image/png")))
        resp = requests.post(url, headers=headers, files=files, timeout=90)
    else:
        payload = {
            "prompt": prompt,
            "seed": seed,
            "num_steps": steps,
            "width": width,
            "height": height,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=90)

    if resp.status_code != 200:
        raise RuntimeError(f"Cloudflare HTTP {resp.status_code}: {resp.text[:350]}")

    ctype = resp.headers.get("Content-Type", "")
    if "image/" in ctype:
        return resp.content
    data = resp.json()
    img_b64 = data.get("result", {}).get("image") or data.get("image")
    if not img_b64:
        raise RuntimeError(f"Missing image in Cloudflare response: {str(data)[:300]}")
    return base64.b64decode(img_b64)


def generate_reference_sheet(
    storyboard: dict[str, Any],
    account_id: str,
    token: str,
    force: bool = False,
) -> Path:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    style = storyboard["style"]
    golden_path = ROOT_DIR / style["golden_reference"]
    char_desc = style.get("character_description", "")
    style_block = style["style_block"]
    neg = style["negative_prompt"]
    model = storyboard["shots"][0]["keyframe"]["model"]

    candidates = []
    for idx, seed in enumerate((1001, 1002, 1003), start=1):
        cand_path = REFS_DIR / f"character_sheet_cand_{idx}.png"
        prompt = (
            f"Character and style reference sheet, three views (front, three-quarter, hands detail) "
            f"on neutral warm linen background. {char_desc}. {style_block}"
        )
        params = {"width": 1024, "height": 768, "steps": 4, "candidate": idx}
        in_hash = compute_input_hash("keyframes_ref", model, prompt, seed, params)
        meta_path = REFS_DIR / f"character_sheet_cand_{idx}.meta.json"

        if not force and check_cached_output(cand_path, in_hash, meta_path):
            print(f"[CACHE HIT] ref candidate {idx}: {cand_path.relative_to(ROOT_DIR)}")
            candidates.append(cand_path)
            continue

        print(f"[REF] Generating character/style sheet candidate {idx}/3 (seed={seed})...")
        img_bytes = retry_with_backoff(
            lambda m=model, p=prompt, n=neg, s=seed: invoke_cloudflare_flux(
                account_id, token, m, p, n, s, width=1024, height=768, steps=4
            ),
            stage="keyframes",
            shot_id=f"ref_cand_{idx}",
            model=model,
            parameters=params,
            seed=seed,
            input_hash=in_hash,
            output_path=str(cand_path.relative_to(ROOT_DIR)),
        )
        cand_path.write_bytes(img_bytes)
        write_cache_meta(cand_path, in_hash, meta_path)
        candidates.append(cand_path)

    if not golden_path.exists() and candidates:
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_bytes(candidates[0].read_bytes())
        print(
            f"[REF] Default golden_reference written to {golden_path.relative_to(ROOT_DIR)} "
            "(inspect all 3 candidates and replace golden_reference with your preferred one before Phase 2b)."
        )
    return golden_path


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Generate character reference sheet and per-shot keyframes.")
    parser.add_argument("--storyboard", type=Path, default=Path("storyboard.json"))
    parser.add_argument("--refs-only", action="store_true", help="Only generate the character/style reference sheet.")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    sb_path = args.storyboard if args.storyboard.is_absolute() else ROOT_DIR / args.storyboard
    storyboard = validate_storyboard(sb_path)

    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not token:
        print("ERROR: CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN not set.", file=sys.stderr)
        return 1

    golden_ref = generate_reference_sheet(storyboard, account_id, token, force=args.force)
    if args.refs_only:
        return 0

    KEYFRAMES_DIR.mkdir(parents=True, exist_ok=True)
    style = storyboard["style"]
    style_block = style["style_block"]
    char_desc = style.get("character_description", "")

    generated = 0
    skipped = 0
    for shot in storyboard["shots"]:
        shot_id = shot["id"]
        kf = shot["keyframe"]
        model = kf["model"]
        seed = int(kf["seed"])
        neg = kf["negative_prompt"] or style["negative_prompt"]
        ref_paths: list[Path] = []
        for r in kf.get("ref_images", []):
            rp = ROOT_DIR / r if not Path(r).is_absolute() else Path(r)
            if rp.exists():
                ref_paths.append(rp)

        char_clause = f" {char_desc}." if ref_paths and char_desc else ""
        full_prompt = (
            f"{kf['prompt']}.{char_clause} {style_block}. "
            "Centered main subject composition suitable for both 9:16 vertical and 16:9 horizontal framing."
        ).strip()

        params = {"width": args.width, "height": args.height, "steps": 4, "negative_prompt": neg}
        in_hash = compute_input_hash("keyframes", model, full_prompt, seed, params, ref_files=ref_paths)
        out_path = KEYFRAMES_DIR / f"{shot_id}_{in_hash}.png"
        meta_path = KEYFRAMES_DIR / f"{shot_id}_{in_hash}.meta.json"

        if not args.force and check_cached_output(out_path, in_hash, meta_path):
            print(f"[CACHE HIT] {shot_id}: {out_path.relative_to(ROOT_DIR)}")
            skipped += 1
            continue

        print(f"[KEYFRAME] Generating {shot_id} (model={model}, seed={seed})...")
        try:
            img_bytes = retry_with_backoff(
                lambda m=model, p=full_prompt, n=neg, s=seed, refs=ref_paths: invoke_cloudflare_flux(
                    account_id, token, m, p, n, s, width=args.width, height=args.height, steps=4, ref_images=refs
                ),
                stage="keyframes",
                shot_id=shot_id,
                model=model,
                parameters=params,
                seed=seed,
                input_hash=in_hash,
                output_path=str(out_path.relative_to(ROOT_DIR)),
            )
        except Exception as exc:  # noqa: BLE001
            if is_quota_or_rate_error(exc):
                append_failure("keyframes", shot_id, str(exc), "Quota exhausted; continuing with remaining shots.")
                continue
            print(f"[FALLBACK] {shot_id}: retrying with {FALLBACK_MODEL} after {model} failed: {exc}")
            try:
                fb_hash = compute_input_hash("keyframes", FALLBACK_MODEL, full_prompt, seed, params, ref_files=ref_paths)
                out_path = KEYFRAMES_DIR / f"{shot_id}_{fb_hash}.png"
                meta_path = KEYFRAMES_DIR / f"{shot_id}_{fb_hash}.meta.json"
                img_bytes = retry_with_backoff(
                    lambda p=full_prompt, n=neg, s=seed: invoke_cloudflare_flux(
                        account_id, token, FALLBACK_MODEL, p, n, s, width=args.width, height=args.height, steps=4
                    ),
                    stage="keyframes",
                    shot_id=shot_id,
                    model=FALLBACK_MODEL,
                    parameters=params,
                    seed=seed,
                    input_hash=fb_hash,
                    output_path=str(out_path.relative_to(ROOT_DIR)),
                )
                in_hash = fb_hash
            except Exception as fb_exc:  # noqa: BLE001
                append_failure("keyframes", shot_id, str(fb_exc), "Both primary and fallback FLUX models failed.")
                continue

        out_path.write_bytes(img_bytes)
        write_cache_meta(out_path, in_hash, meta_path, extra={"shot_id": shot_id})
        print(f"  -> Saved {out_path.relative_to(ROOT_DIR)}")
        generated += 1

    print(
        f"Keyframes complete: {generated} generated, {skipped} cached. "
        "REMINDER: Inspect faces, hands, and loom/cultural details before spending Kaggle GPU time!"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

