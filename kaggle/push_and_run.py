"""Upload storyboard + keyframes to Kaggle and push/poll GPU notebooks via KAGGLE_API_TOKEN."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import requests

from pipeline.common import ROOT_DIR, append_failure, load_env, redact_secrets

KAGGLE_API = "https://www.kaggle.com/api/v1"
DATASET_SLUG = "heritage-short-inputs"


def auth_headers() -> dict[str, str]:
    tok = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if not tok:
        raise RuntimeError("KAGGLE_API_TOKEN is not set.")
    return {"Authorization": f"Bearer {tok}"}


def get_username(headers: dict[str, str]) -> str:
    env_user = os.environ.get("KAGGLE_USERNAME", "").strip()
    if env_user:
        return env_user
    resp = requests.get(f"{KAGGLE_API}/hello", headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()["userName"]


def upload_inputs_dataset(headers: dict[str, str], username: str) -> str:
    """Create or update a private Kaggle dataset containing storyboard.json and keyframes."""
    tmp_zip = ROOT_DIR / "outputs" / "tmp_assembly" / "kaggle_inputs.zip"
    tmp_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(ROOT_DIR / "storyboard.json", arcname="storyboard.json")
        for png in sorted((ROOT_DIR / "outputs" / "keyframes").glob("shot_*.png")):
            zf.write(png, arcname=png.name)

    meta_bytes = tmp_zip.read_bytes()
    # Kaggle blob upload init
    init_resp = requests.post(
        f"{KAGGLE_API}/blobs/upload",
        headers=headers,
        json={"type": "DATASET", "name": tmp_zip.name, "contentLength": len(meta_bytes)},
        timeout=30,
    )
    if init_resp.status_code != 200:
        raise RuntimeError(f"Blob upload init failed ({init_resp.status_code}): {init_resp.text[:300]}")
    blob = init_resp.json()
    put_resp = requests.put(blob["createUrl"], data=meta_bytes, timeout=120)
    put_resp.raise_for_status()
    token = blob["token"]

    ds_ref = f"{username}/{DATASET_SLUG}"
    exists = requests.get(f"{KAGGLE_API}/datasets/view/{ds_ref}", headers=headers, timeout=20).status_code == 200
    if exists:
        ver_resp = requests.post(
            f"{KAGGLE_API}/datasets/create/version/{ds_ref}",
            headers=headers,
            json={"versionNotes": "Updated keyframes and storyboard", "files": [{"token": token}], "deleteOldVersions": False},
            timeout=30,
        )
        if ver_resp.status_code != 200:
            raise RuntimeError(f"Dataset version failed ({ver_resp.status_code}): {ver_resp.text[:300]}")
    else:
        create_resp = requests.post(
            f"{KAGGLE_API}/datasets/create/new",
            headers=headers,
            json={
                "ownerSlug": username,
                "slug": DATASET_SLUG,
                "title": "Heritage Short Inputs",
                "isPrivate": True,
                "licenses": [{"name": "CC0-1.0"}],
                "files": [{"token": token}],
            },
            timeout=30,
        )
        if create_resp.status_code != 200:
            raise RuntimeError(f"Dataset create failed ({create_resp.status_code}): {create_resp.text[:300]}")
    return ds_ref


def push_kernel(headers: dict[str, str], username: str, nb_path: Path, slug: str, ds_ref: str) -> str:
    nb_text = nb_path.read_text(encoding="utf-8")
    payload = {
        "slug": f"{username}/{slug}",
        "newTitle": slug.replace("-", " ").title(),
        "text": nb_text,
        "language": "python",
        "kernelType": "notebook",
        "isPrivate": True,
        "enableGpu": True,
        "enableTpu": False,
        "enableInternet": True,
        "datasetDataSources": [ds_ref],
        "competitionDataSources": [],
        "kernelDataSources": [],
    }
    resp = requests.post(f"{KAGGLE_API}/kernels/push", headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Kernel push failed ({resp.status_code}): {resp.text[:350]}")
    return f"{username}/{slug}"


def poll_kernel(headers: dict[str, str], ref: str, max_wait_s: int = 120) -> str:
    username, slug = ref.split("/", 1)
    deadline = time.monotonic() + max_wait_s
    status = "unknown"
    while time.monotonic() < deadline:
        resp = requests.get(
            f"{KAGGLE_API}/kernels/status?userName={username}&kernelSlug={slug}",
            headers=headers,
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "unknown")
            print(f"  [{ref}] status={status} {data.get('failureMessage', '')}")
            if status in ("complete", "error", "cancelAcknowledged"):
                return status
        time.sleep(15)
    return status


def download_kernel_outputs(headers: dict[str, str], ref: str, dest_dir: Path) -> list[Path]:
    username, slug = ref.split("/", 1)
    resp = requests.get(
        f"{KAGGLE_API}/kernels/output?userName={username}&kernelSlug={slug}",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    saved: list[Path] = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f_info in data.get("files", []):
        url = f_info.get("url")
        name = Path(f_info.get("fileName", "")).name
        if not url or not name or not (name.endswith(".mp4") or name.endswith(".wav")):
            continue
        out_path = dest_dir / name
        with requests.get(url, headers=headers, stream=True, timeout=120) as dl:
            dl.raise_for_status()
            with out_path.open("wb") as fh:
                for chunk in dl.iter_content(chunk_size=65536):
                    fh.write(chunk)
        saved.append(out_path)
    return saved


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Push Wan 2.2 and ACE-Step notebooks to Kaggle GPU.")
    parser.add_argument("--wait-seconds", type=int, default=90)
    args = parser.parse_args()

    try:
        headers = auth_headers()
        username = get_username(headers)
        print(f"Authenticated Kaggle user: {username}")
        ds_ref = upload_inputs_dataset(headers, username)
        print(f"Uploaded dataset: {ds_ref}")
        for nb_name, slug in (
            ("acestep_music.ipynb", "heritage-short-acestep"),
            ("wan22_i2v.ipynb", "heritage-short-wan22"),
        ):
            ref = push_kernel(headers, username, ROOT_DIR / "kaggle" / nb_name, slug, ds_ref)
            print(f"Pushed GPU notebook: {ref}")
            status = poll_kernel(headers, ref, max_wait_s=args.wait_seconds)
            if status != "complete":
                append_failure(
                    "kaggle",
                    ref,
                    f"Kernel status after {args.wait_seconds}s poll: {status}",
                    "Notebook pushed to Kaggle; local pipeline uses Ken Burns / Tizita fallback until outputs are downloaded to kaggle/outputs/.",
                )
    except Exception as exc:  # noqa: BLE001
        err = redact_secrets(str(exc))
        print(f"KAGGLE API NOTICE: {err}", file=sys.stderr)
        append_failure(
            "kaggle",
            "push_and_run",
            err,
            "Kaggle remote push blocked/unverified; notebooks remain ready in kaggle/ for manual GPU run, while local fallbacks keep pipeline green.",
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

