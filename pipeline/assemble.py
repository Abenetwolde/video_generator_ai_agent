"""Stage 5: Deterministic FFmpeg assembly (radio cut + final 9:16 & 16:9 exports)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from pipeline.common import (
    ROOT_DIR,
    append_run_log,
    compute_input_hash,
    load_env,
    validate_storyboard,
)
from pipeline.music import MUSIC_CHOICE_PATH, synthesize_pentatonic_placeholder

NARRATION_DIR = ROOT_DIR / "outputs" / "narration"
SHOTS_DIR = ROOT_DIR / "outputs" / "shots"
KEYFRAMES_DIR = ROOT_DIR / "outputs" / "keyframes"
FINAL_DIR = ROOT_DIR / "outputs" / "final"
SUBTITLES_DIR = ROOT_DIR / "subtitles"
TMP_DIR = ROOT_DIR / "outputs" / "tmp_assembly"


def ffprobe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(res.stdout.strip())


def format_srt_ts(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    hrs = ms_total // 3_600_000
    mins = (ms_total % 3_600_000) // 60_000
    secs = (ms_total % 60_000) // 1000
    ms = ms_total % 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def wrap_subtitle_lines(text: str, max_chars: int = 40, max_lines: int = 2) -> str:
    words = text.strip().split()
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1 :])]
    return "\n".join(lines)


def build_srt_and_timeline(
    storyboard: dict[str, Any],
    srt_path: Path,
) -> tuple[list[dict[str, Any]], float]:
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    safe = storyboard["assembly"]["subtitle_safe_area"]
    max_chars = int(safe["max_chars_per_line"])
    max_lines = int(safe["max_lines"])

    timeline: list[dict[str, Any]] = []
    srt_entries: list[str] = []
    cursor = 0.0

    for idx, shot in enumerate(storyboard["shots"], start=1):
        shot_id = shot["id"]
        nar_wav = NARRATION_DIR / f"{shot_id}.wav"
        if not nar_wav.exists():
            raise FileNotFoundError(f"Missing narration audio: {nar_wav}")
        nar_dur = ffprobe_duration(nar_wav)
        # Ensure each shot is at least long enough for its narration + 0.4s breathing room
        slot_dur = max(float(shot["duration_s"]), nar_dur + 0.4)
        start_s = cursor
        end_s = cursor + slot_dur
        cursor = end_s

        sub_lines = shot["subtitles"].get("lines")
        if sub_lines:
            sub_text = "\n".join(sub_lines[:max_lines])
        else:
            en_text = shot["narration"].get("english_translation", "")
            sub_text = wrap_subtitle_lines(en_text, max_chars=max_chars, max_lines=max_lines)

        srt_entries.append(
            f"{idx}\n{format_srt_ts(start_s + 0.1)} --> {format_srt_ts(end_s - 0.15)}\n{sub_text}\n"
        )
        timeline.append(
            {
                "shot": shot,
                "nar_wav": nar_wav,
                "nar_dur": nar_dur,
                "slot_dur": slot_dur,
                "start_s": start_s,
                "end_s": end_s,
            }
        )

    srt_path.write_text("\n".join(srt_entries), encoding="utf-8")
    return timeline, cursor


def concat_narration_track(timeline: list[dict[str, Any]], out_wav: Path) -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    padded_parts: list[Path] = []
    for item in timeline:
        shot_id = item["shot"]["id"]
        part_wav = TMP_DIR / f"{shot_id}_slot.wav"
        slot_dur = item["slot_dur"]
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(item["nar_wav"]),
                "-af",
                f"aresample=24000,apad=whole_dur={slot_dur:.3f}",
                "-t",
                f"{slot_dur:.3f}",
                "-c:a",
                "pcm_s16le",
                str(part_wav),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        padded_parts.append(part_wav)

    list_file = TMP_DIR / "narration_concat.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in padded_parts) + "\n", encoding="utf-8")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ensure_endcard_video(storyboard: dict[str, Any], width: int, height: int, fps: int, out_mp4: Path) -> Path:
    end_card = storyboard["end_card"]
    dur = float(end_card["duration_s"])
    title = end_card["text"].replace(":", "\\:")
    subtitle = end_card.get("subtitle", storyboard["meta"]["title"]).replace(":", "\\:")
    base_dim = min(width, height)
    title_size = max(36, int(base_dim * 0.065))
    sub_size = max(20, int(base_dim * 0.026))
    vf = (
        f"drawtext=text='{title}':fontcolor=white:fontsize={title_size}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-{int(title_size * 0.7)},"
        f"drawtext=text='{subtitle}':fontcolor=0xD8C7A8:fontsize={sub_size}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2+{int(title_size * 0.7)},"
        "fade=t=in:st=0:d=0.4,fade=t=out:st="
        f"{max(dur - 0.5, 0.5):.2f}:d=0.5,format=yuv420p"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x14110E:s={width}x{height}:r={fps}:d={dur:.3f}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=24000:cl=stereo:d={dur:.3f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(out_mp4),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return out_mp4


def two_pass_loudnorm_filter(input_wav: Path, target_lufs: float, true_peak: float) -> str:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_wav),
        "-af",
        f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11:print_format=json",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.DOTALL)
    if not m:
        return f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11"
    stats = json.loads(m.group(0))
    return (
        f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11:"
        f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
        f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
        f"offset={stats['target_offset']}:linear=true"
    )


def build_ducked_master_audio(
    narration_wav: Path,
    music_wav: Path,
    total_dur: float,
    endcard_dur: float,
    target_lufs: float,
    true_peak: float,
    out_wav: Path,
) -> None:
    mixed_raw = TMP_DIR / "mixed_raw.wav"
    full_dur = total_dur + endcard_dur
    filter_complex = (
        f"[0:a]apad=whole_dur={full_dur:.3f},aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[voice_sc][voice_mix];"
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{full_dur:.3f},aformat=sample_rates=48000:channel_layouts=stereo,volume=0.35[music_in];"
        "[music_in][voice_sc]sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500[music_ducked];"
        "[voice_mix][music_ducked]amix=inputs=2:duration=first:normalize=0[out]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(narration_wav),
            "-i",
            str(music_wav),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            str(mixed_raw),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Target -1.2 dBTP in PCM so lossy AAC encoding stays strictly <= -1.0 dBTP
    pcm_tp = min(true_peak, -1.2)
    ln_filter = two_pass_loudnorm_filter(mixed_raw, target_lufs, pcm_tp)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mixed_raw),
            "-af",
            ln_filter,
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def find_visual_source(shot_id: str) -> Path | None:
    shots = sorted(SHOTS_DIR.glob(f"{shot_id}_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if shots:
        return shots[0]
    kfs = sorted(KEYFRAMES_DIR.glob(f"{shot_id}_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return kfs[0] if kfs else None


def render_aspect_video(
    storyboard: dict[str, Any],
    timeline: list[dict[str, Any]],
    master_audio: Path,
    srt_path: Path,
    aspect: str,
    radio_cut: bool,
    out_mp4: Path,
) -> None:
    width, height = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    fps = int(storyboard["meta"]["fps"])
    safe = storyboard["assembly"]["subtitle_safe_area"]
    # libass maps SRT styles onto a virtual 384x288 canvas (PlayResY=288).
    # Scale pixel margins & font sizes accordingly so 9:16 fits cleanly in lower safe area.
    if aspect == "9:16":
        margin_v = max(24, int(round(int(safe["vertical_margin_v"]) * 288 / height)))
        margin_h = max(14, int(round(int(safe["horizontal_margin_v"]) * 384 / width)))
        font_size = 8
    else:
        margin_v = max(16, int(round(int(safe["vertical_margin_v"]) * 288 / (height * 2))))
        margin_h = max(12, int(round(int(safe["horizontal_margin_v"]) * 384 / width)))
        font_size = 15

    segment_mp4s: list[Path] = []
    for item in timeline:
        shot = item["shot"]
        shot_id = shot["id"]
        slot_dur = item["slot_dur"]
        seg_mp4 = TMP_DIR / f"{shot_id}_{aspect.replace(':', 'x')}.mp4"
        src = None if radio_cut else find_visual_source(shot_id)

        if src is None:
            label = f"{shot_id.upper()} | {shot['shot_size']} | {shot['camera']}".replace(":", "\\:")
            vf = (
                f"drawtext=text='{label}':fontcolor=0xA89F91:fontsize={int(height * 0.022)}:"
                "x=(w-text_w)/2:y=(h*0.18),format=yuv420p"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x101012:s={width}x{height}:r={fps}:d={slot_dur:.3f}",
                "-vf",
                vf,
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(seg_mp4),
            ]
        elif src.suffix.lower() == ".png":
            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(src),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},format=yuv420p",
                "-t",
                f"{slot_dur:.3f}",
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(seg_mp4),
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(src),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},format=yuv420p",
                "-t",
                f"{slot_dur:.3f}",
                "-r",
                str(fps),
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(seg_mp4),
            ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        segment_mp4s.append(seg_mp4)

    endcard_mp4 = TMP_DIR / f"endcard_{aspect.replace(':', 'x')}.mp4"
    ensure_endcard_video(storyboard, width, height, fps, endcard_mp4)
    if aspect == "9:16":
        endcard_png = ROOT_DIR / storyboard["end_card"]["path"]
        endcard_png.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "1.0", "-i", str(endcard_mp4), "-vframes", "1", str(endcard_png)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    segment_mp4s.append(endcard_mp4)

    vlist = TMP_DIR / f"video_concat_{aspect.replace(':', 'x')}.txt"
    vlist.write_text("\n".join(f"file '{p}'" for p in segment_mp4s) + "\n", encoding="utf-8")

    concat_video = TMP_DIR / f"concat_video_{aspect.replace(':', 'x')}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(vlist),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(concat_video),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    escaped_srt = str(srt_path).replace("\\", "\\\\").replace(":", "\\:")
    sub_style = (
        f"Fontsize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        f"BackColour=&H64000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,"
        f"MarginV={margin_v},MarginL={margin_h},MarginR={margin_h}"
    )

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(concat_video),
            "-i",
            str(master_audio),
            "-vf",
            f"subtitles={escaped_srt}:force_style='{sub_style}'",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(out_mp4),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Assemble radio cut or final 9:16 & 16:9 films.")
    parser.add_argument("--storyboard", type=Path, default=Path("storyboard.json"))
    parser.add_argument("--radio-cut", action="store_true", help="Assemble narration + temp score on black.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    sb_path = args.storyboard if args.storyboard.is_absolute() else ROOT_DIR / args.storyboard
    storyboard = validate_storyboard(sb_path)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)

    srt_path = ROOT_DIR / storyboard["shots"][0]["subtitles"]["srt_path"]
    timeline, total_dur = build_srt_and_timeline(storyboard, srt_path)

    narration_full = TMP_DIR / "narration_full.wav"
    concat_narration_track(timeline, narration_full)

    music_wav = TMP_DIR / "temp_score.wav"
    if not args.radio_cut and MUSIC_CHOICE_PATH.exists():
        choice = json.loads(MUSIC_CHOICE_PATH.read_text(encoding="utf-8"))
        candidate = ROOT_DIR / choice.get("chosen_candidate_path", "")
        if candidate.exists():
            music_wav = candidate
    if not music_wav.exists() or args.radio_cut:
        synthesize_pentatonic_placeholder(music_wav, total_dur + float(storyboard["end_card"]["duration_s"]) + 2.0, 76)

    master_audio = TMP_DIR / "master_audio.wav"
    build_ducked_master_audio(
        narration_full,
        music_wav,
        total_dur,
        float(storyboard["end_card"]["duration_s"]),
        float(storyboard["meta"]["loudness_target_lufs"]),
        float(storyboard["meta"]["true_peak_db"]),
        master_audio,
    )

    prefix = "radio_cut" if args.radio_cut else "film"
    for aspect in storyboard["meta"]["aspect_ratios"]:
        tag = aspect.replace(":", "x")
        out_mp4 = FINAL_DIR / f"{prefix}_{tag}.mp4"
        t0 = time.monotonic()
        render_aspect_video(storyboard, timeline, master_audio, srt_path, aspect, args.radio_cut, out_mp4)
        latency_ms = int((time.monotonic() - t0) * 1000)
        in_hash = compute_input_hash("assemble", "ffmpeg", f"{prefix}_{tag}", 0, {"aspect": aspect, "radio_cut": args.radio_cut})
        append_run_log(
            stage="assemble",
            shot_id=f"{prefix}_{tag}",
            model="ffmpeg-local",
            parameters={"aspect": aspect, "radio_cut": args.radio_cut, "fps": storyboard["meta"]["fps"]},
            seed=0,
            latency_ms=latency_ms,
            cost_estimate_usd=0.0,
            input_hash=in_hash,
            output_path=str(out_mp4.relative_to(ROOT_DIR)),
            status="ok",
            retry_count=0,
        )
        print(f"[ASSEMBLE] Built {out_mp4.relative_to(ROOT_DIR)} ({total_dur + storyboard['end_card']['duration_s']:.1f}s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

