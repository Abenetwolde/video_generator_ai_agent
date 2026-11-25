"""Shared utilities for validation, hashing, retries, logging, and caching."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv
from jsonschema import Draft202012Validator

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT_DIR / "schema" / "storyboard.schema.json"
RUNS_LOG_PATH = ROOT_DIR / "runs.jsonl"
FAILURES_PATH = ROOT_DIR / "FAILURES.md"
ETHICS_PATH = ROOT_DIR / "ETHICS.md"

T = TypeVar("T")


def load_env() -> None:
    """Load environment variables from .env if present without overwriting exported ones."""
    load_dotenv(ROOT_DIR / ".env", override=False)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redact_secrets(text: str) -> str:
    """Strip any known API secrets from error strings before logging."""
    for var in (
        "GEMINI_API_KEY",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "KAGGLE_API_TOKEN",
        "KAGGLE_KEY",
    ):
        val = os.environ.get(var, "").strip()
        if val and len(val) > 4:
            text = text.replace(val, f"<REDACTED:{var}>")
    return text


def sha256_file(path: Path) -> str:
    """Compute hex SHA-256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_input_hash(
    stage: str,
    model: str,
    prompt: str,
    seed: int | None,
    parameters: dict[str, Any],
    ref_files: list[str | Path] | None = None,
) -> str:
    """Deterministic 12-char SHA-256 hash of stage inputs and reference image contents."""
    ref_hashes: list[dict[str, str]] = []
    for ref in ref_files or []:
        p = Path(ref)
        if not p.is_absolute():
            p = ROOT_DIR / p
        if p.exists() and p.is_file():
            ref_hashes.append({"path": str(ref), "sha256": sha256_file(p)})
        else:
            ref_hashes.append({"path": str(ref), "sha256": "MISSING"})

    payload = {
        "stage": stage,
        "model": model,
        "prompt": prompt,
        "seed": seed,
        "parameters": parameters,
        "refs": ref_hashes,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def check_cached_output(output_path: Path, expected_hash: str, meta_path: Path | None = None) -> bool:
    """Return True if output exists, is non-empty, and matches expected_hash."""
    if not output_path.exists() or output_path.stat().st_size == 0:
        return False
    if meta_path is not None:
        if not meta_path.exists():
            return False
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        if meta.get("input_hash") != expected_hash:
            return False
        if meta.get("output_sha256") != sha256_file(output_path):
            return False
        return True
    return expected_hash in output_path.stem


def write_cache_meta(output_path: Path, input_hash: str, meta_path: Path, extra: dict[str, Any] | None = None) -> None:
    """Persist sidecar metadata verifying output integrity against input_hash."""
    payload: dict[str, Any] = {
        "input_hash": input_hash,
        "output_path": str(output_path.relative_to(ROOT_DIR)) if output_path.is_relative_to(ROOT_DIR) else str(output_path),
        "output_sha256": sha256_file(output_path),
        "updated_at": utc_now_iso(),
    }
    if extra:
        payload.update(extra)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_run_log(
    *,
    stage: str,
    model: str,
    parameters: dict[str, Any],
    seed: int | None,
    latency_ms: int,
    cost_estimate_usd: float,
    input_hash: str,
    output_path: str,
    status: str,
    retry_count: int,
    shot_id: str | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one structured JSONL record to runs.jsonl."""
    record: dict[str, Any] = {
        "timestamp": utc_now_iso(),
        "stage": stage,
        "shot_id": shot_id,
        "model": model,
        "parameters": parameters,
        "seed": seed,
        "latency_ms": latency_ms,
        "cost_estimate_usd": round(cost_estimate_usd, 6),
        "input_hash": input_hash,
        "output_path": output_path,
        "status": status,
        "retry_count": retry_count,
    }
    if error:
        record["error"] = redact_secrets(error)
    if extra:
        record.update(extra)

    with RUNS_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_failure(stage: str, subject: str, error_msg: str, action_taken: str) -> None:
    """Append a readable blocker/fallback entry to FAILURES.md."""
    clean_err = redact_secrets(error_msg).strip().replace("\n", " ")
    entry = (
        f"\n### [{utc_now_iso()}] Stage: `{stage}` — {subject}\n"
        f"- **Error:** {clean_err}\n"
        f"- **Action / Workaround:** {action_taken}\n"
    )
    if not FAILURES_PATH.exists():
        FAILURES_PATH.write_text("# FAILURES.md — Blockers, Quotas & Workarounds\n", encoding="utf-8")
    with FAILURES_PATH.open("a", encoding="utf-8") as f:
        f.write(entry)


def is_quota_or_rate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        tok in msg
        for tok in ("429", "quota", "rate limit", "rate_limit", "resourceexhausted", "exceeded", "neurons", "limit reached")
    )


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    stage: str,
    model: str,
    parameters: dict[str, Any],
    seed: int | None,
    input_hash: str,
    output_path: str,
    shot_id: str | None = None,
    cost_estimate_usd: float = 0.0,
    max_attempts: int = 3,
    base_delay_s: float = 2.0,
) -> T:
    """Execute fn with up to max_attempts, exponential backoff + jitter, and runs.jsonl logging."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        t0 = time.monotonic()
        try:
            result = fn()
            latency_ms = int((time.monotonic() - t0) * 1000)
            append_run_log(
                stage=stage,
                shot_id=shot_id,
                model=model,
                parameters=parameters,
                seed=seed,
                latency_ms=latency_ms,
                cost_estimate_usd=cost_estimate_usd,
                input_hash=input_hash,
                output_path=output_path,
                status="ok",
                retry_count=attempt,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            latency_ms = int((time.monotonic() - t0) * 1000)
            is_last = attempt == max_attempts - 1
            append_run_log(
                stage=stage,
                shot_id=shot_id,
                model=model,
                parameters=parameters,
                seed=seed,
                latency_ms=latency_ms,
                cost_estimate_usd=0.0,
                input_hash=input_hash,
                output_path=output_path,
                status="failed" if is_last else "retry",
                retry_count=attempt,
                error=str(exc),
            )
            if is_quota_or_rate_error(exc):
                append_failure(
                    stage,
                    shot_id or model,
                    str(exc),
                    f"Quota/rate-limit hit on attempt {attempt + 1}/{max_attempts}; "
                    + ("backing off" if not is_last else "falling back / halting item."),
                )
            if not is_last:
                delay = base_delay_s * (2**attempt) + random.uniform(0.2, 1.0)
                time.sleep(delay)

    assert last_exc is not None
    raise last_exc


class StoryboardValidationError(ValueError):
    """Raised when storyboard.json violates schema or pipeline contracts."""


def validate_storyboard(storyboard_path: Path | None = None) -> dict[str, Any]:
    """Load and strictly validate storyboard.json against schema and cross-field invariants."""
    sb_path = storyboard_path or (ROOT_DIR / "storyboard.json")
    if not sb_path.exists():
        raise StoryboardValidationError(f"Storyboard not found: {sb_path}")
    if not SCHEMA_PATH.exists():
        raise StoryboardValidationError(f"Schema not found: {SCHEMA_PATH}")

    try:
        data = json.loads(sb_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryboardValidationError(f"Invalid JSON in {sb_path}: {exc}") from exc

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        formatted = "\n".join(
            f"  - {'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
            for err in errors[:15]
        )
        raise StoryboardValidationError(f"Schema validation failed for {sb_path}:\n{formatted}")

    shots = data["shots"]
    orders = [s["order"] for s in shots]
    if orders != list(range(1, len(shots) + 1)):
        raise StoryboardValidationError(f"Shot orders must be sequential 1..{len(shots)}, got {orders}")

    ids = [s["id"] for s in shots]
    if len(set(ids)) != len(ids):
        raise StoryboardValidationError(f"Duplicate shot IDs found: {ids}")

    total_s = sum(float(s["duration_s"]) for s in shots)
    if not (60.0 <= total_s <= 90.0):
        raise StoryboardValidationError(
            f"Total shot duration ({total_s:.1f}s) must be within 60–90 seconds."
        )

    for s in shots:
        if not s["reason"].strip():
            raise StoryboardValidationError(f"Shot {s['id']} has an empty reason.")
        if s["music_cue"]["end_s"] <= s["music_cue"]["start_s"]:
            raise StoryboardValidationError(f"Shot {s['id']} music_cue end_s must exceed start_s.")

    if not ETHICS_PATH.exists():
        raise StoryboardValidationError("ETHICS.md missing — ethics gate requires consent/archetype record.")

    return data

