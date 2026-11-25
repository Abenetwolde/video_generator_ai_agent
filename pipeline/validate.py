"""CLI validator for storyboard.json against schema/storyboard.schema.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.common import StoryboardValidationError, validate_storyboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate storyboard.json contract.")
    parser.add_argument("--storyboard", type=Path, default=Path("storyboard.json"))
    args = parser.parse_args()

    try:
        data = validate_storyboard(args.storyboard)
    except StoryboardValidationError as exc:
        print(f"VALIDATION ERROR:\n{exc}", file=sys.stderr)
        return 1

    shots = data["shots"]
    total_s = sum(s["duration_s"] for s in shots)
    print(
        f"OK: {args.storyboard} valid ({len(shots)} shots, {total_s:.1f}s total, "
        f"language={data['meta']['narration_language']}, subtitles={data['meta']['subtitle_language']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

