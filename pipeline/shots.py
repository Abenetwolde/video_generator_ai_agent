"""Stage 3: Image-to-video per shot (Wan 2.2 on Kaggle or pre-rendered clips, with FFmpeg Ken Burns fallback)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

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

KEYFRAMES_DIR = ROOT_DIR / "outputs" / "keyframes"
SHOTS_DIR = ROOT_DIR / "outputs" / "shots"
KAGGLE_EXPORTS_DIR = ROOT_DIR / "kaggle" / "outputs" / "shots"


def find_latest_keyframe(shot_id: str) -> Path | None:
    matches = sorted(KEYFRAMES_DIR.glob(f"{shot_id}_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def render_ken_burns_fallback(
    keyframe_path: Path,
    out_path: Path,
    duration_s: float,
    camera: str,
    fps: int = 24,
) -> None:
    """Deterministic FFmpeg zoompan fallback when I2V GPU generation is unavailable."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(int(round(duration_s * fps)), fps)

    if camera in ("push_in", "slow_drift"):
        z_expr = "min(zoom+0.0012,1.12)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif camera == "pull_back":
        z_expr = "if(lte(zoom,1.0),1.12,max(1.0,zoom-0.0012))"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif camera == "pan_right":
        z_expr = "1.08"
        x_expr = f"(iw-iw/zoom)*on/{frames}"
        y_expr = "ih/2-(ih/zoom/2)"
    elif camera == "pan_left":
        z_expr = "1.08"
        x_expr = f"(iw-iw/zoom)*(1-on/{frames})"
        y_expr = "ih/2-(ih/zoom/2)"
    else:
        z_expr = "min(zoom+0.0005,1.04)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    vf = (
        f"scale=1280:1280:force_original_aspect_ratio=increase,crop=1280:1280,"
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s=1024x1024:fps={fps},"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(keyframe_path),
        "-vf",
        vf,
        "-t",
        f"{duration_s:.3f}",
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Ingest Kaggle Wan 2.2 clips or render Ken Burns fallback.")
    parser.add_argument("--storyboard", type=Path, default=Path("storyboard.json"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--prefer-fallback", action="store_true", help="Force Ken Burns fallback even if Kaggle clips absent.")
    args = parser.parse_args()

    sb_path = args.storyboard if args.storyboard.is_absolute() else ROOT_DIR / args.storyboard
    storyboard = validate_storyboard(sb_path)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    fps = int(storyboard["meta"]["fps"])

    produced = 0
    cached = 0
    for shot in storyboard["shots"]:
        shot_id = shot["id"]
        kf_path = find_latest_keyframe(shot_id)
        if kf_path is None:
            print(f"[SKIP] {shot_id}: no keyframe found in outputs/keyframes/ yet.")
            continue

        motion = shot["motion"]
        params = {
            "duration_s": shot["duration_s"],
            "camera": shot["camera"],
            "draft_resolution": motion["draft_resolution"],
            "final_resolution": motion["final_resolution"],
            "fps": fps,
        }
        in_hash = compute_input_hash(
            "shots",
            motion["model"],
            motion["prompt"],
            int(motion["seed"]),
            params,
            ref_files=[kf_path],
        )
        out_path = SHOTS_DIR / f"{shot_id}_{in_hash}.mp4"
        meta_path = SHOTS_DIR / f"{shot_id}_{in_hash}.meta.json"

        if not args.force and check_cached_output(out_path, in_hash, meta_path):
            print(f"[CACHE HIT] {shot_id}: {out_path.relative_to(ROOT_DIR)}")
            cached += 1
            continue

        # Check if Kaggle notebook export exists for this shot
        kaggle_clip = KAGGLE_EXPORTS_DIR / f"{shot_id}.mp4"
        t0 = time.monotonic()
        if not args.prefer_fallback and kaggle_clip.exists() and kaggle_clip.stat().st_size > 0:
            shutil.copy2(kaggle_clip, out_path)
            latency_ms = int((time.monotonic() - t0) * 1000)
            append_run_log(
                stage="shots",
                shot_id=shot_id,
                model=motion["model"],
                parameters=params,
                seed=int(motion["seed"]),
                latency_ms=latency_ms,
                cost_estimate_usd=0.0,
                input_hash=in_hash,
                output_path=str(out_path.relative_to(ROOT_DIR)),
                status="ok",
                retry_count=0,
                extra={"source": "kaggle_wan22_export"},
            )
            write_cache_meta(out_path, in_hash, meta_path, extra={"source": "kaggle_wan22_export"})
            print(f"[SHOT] Imported Kaggle clip {out_path.relative_to(ROOT_DIR)}")
            produced += 1
            continue

        # Graceful fallback: FFmpeg Ken Burns from keyframe
        render_ken_burns_fallback(
            kf_path,
            out_path,
            duration_s=float(shot["duration_s"]),
            camera=shot["camera"],
            fps=fps,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        append_run_log(
            stage="shots",
            shot_id=shot_id,
            model="ffmpeg-ken-burns-fallback",
            parameters=params,
            seed=int(motion["seed"]),
            latency_ms=latency_ms,
            cost_estimate_usd=0.0,
            input_hash=in_hash,
            output_path=str(out_path.relative_to(ROOT_DIR)),
            status="ok",
            retry_count=0,
            extra={"source": "ken_burns_fallback"},
        )
        append_failure(
            "shots",
            shot_id,
            "Kaggle Wan 2.2 clip not present locally (session/quota boundary).",
            f"Emitted deterministic FFmpeg Ken Burns fallback at {out_path.relative_to(ROOT_DIR)}.",
        )
        write_cache_meta(out_path, in_hash, meta_path, extra={"source": "ken_burns_fallback"})
        print(f"[FALLBACK] {shot_id}: Ken Burns still clip -> {out_path.relative_to(ROOT_DIR)}")
        produced += 1

    print(f"Shots complete: {produced} produced, {cached} cached.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

