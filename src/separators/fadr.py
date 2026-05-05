import os
import time
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

from src.separators.base import StemSeparator

load_dotenv()

BASE_URL = "https://api.fadr.com"

# Fadr metaData.stemType → canonical stem name (None = skip)
STEM_MAP = {
    "vocals": "vocals",
    "drums": "drums",
    "bass": "bass",
    "other": "other",
    "instrumental": None,
}


def _load_config() -> dict:
    config_path = Path(__file__).parents[2] / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class FadrSeparator(StemSeparator):
    def __init__(self, config: dict = None):
        self.api_key = os.environ["FADR_API_KEY"]
        cfg = config or _load_config()
        fadr_cfg = cfg["separators"]["fadr"]
        self.poll_interval = fadr_cfg["poll_interval_s"]
        self.timeout = fadr_cfg["timeout_s"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    # ── Upload ────────────────────────────────────────────────────────────────

    def _upload_asset(self, local_path: Path) -> str:
        """Upload WAV via Fadr's presigned S3 URL; return registered asset _id."""
        r = requests.post(
            f"{BASE_URL}/assets/upload2",
            json={"name": local_path.stem, "extension": "wav"},
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        upload_url: str = body["url"]
        s3_path: str = body["s3Path"]

        with open(local_path, "rb") as f:
            put = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": "audio/wav"},
                timeout=600,
            )
            put.raise_for_status()

        r = requests.post(
            f"{BASE_URL}/assets",
            json={
                "s3Path": s3_path,
                "name": local_path.stem,
                "extension": "wav",
                "group": "benchmark",
            },
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["asset"]["_id"]

    # ── Stem task ─────────────────────────────────────────────────────────────

    def _start_stem_task(self, asset_id: str) -> str:
        r = requests.post(
            f"{BASE_URL}/assets/analyze/stem",
            json={"_id": asset_id, "stemType": "main"},
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["task"]["_id"]

    def _poll_task(self, task_id: str) -> dict:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            r = requests.get(
                f"{BASE_URL}/tasks/{task_id}",
                headers=self._headers(),
                timeout=30,
            )
            r.raise_for_status()
            task = r.json()["task"]
            progress = task["status"].get("progress", "?")
            print(f"  progress {progress}%", end="\r", flush=True)
            if task["status"]["complete"]:
                print()
                return task
            time.sleep(self.poll_interval)
        raise TimeoutError(f"Task {task_id} did not complete within {self.timeout}s")

    # ── Download stems ────────────────────────────────────────────────────────

    def _get_stem_type(self, stem_asset_id: str) -> str:
        r = requests.get(
            f"{BASE_URL}/assets/{stem_asset_id}",
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["asset"]["metaData"]["stemType"]

    def _download_stem(self, stem_asset_id: str, dest: Path, retries: int = 3) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, retries + 1):
            try:
                r = requests.get(
                    f"{BASE_URL}/assets/download/{stem_asset_id}/download",
                    headers=self._headers(),
                    timeout=30,
                )
                r.raise_for_status()
                download_url: str = r.json()["url"]

                with requests.get(download_url, stream=True, timeout=300) as dl:
                    dl.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in dl.iter_content(chunk_size=65536):
                            f.write(chunk)
                return
            except requests.HTTPError as exc:
                if attempt == retries:
                    raise
                wait = attempt * 10
                print(f"  download attempt {attempt} failed ({exc}), retrying in {wait}s")
                time.sleep(wait)

    # ── Public interface ──────────────────────────────────────────────────────

    def separate(self, mixture_path: str, output_dir: str) -> dict:
        mixture_path = Path(mixture_path)
        output_dir = Path(output_dir)

        asset_id = self._upload_asset(mixture_path)
        task_id = self._start_stem_task(asset_id)
        task = self._poll_task(task_id)

        # task["asset"] is the full populated asset object, not just an ID
        stem_asset_ids = task["asset"]["stems"]

        results = {}
        asset_id_map = {}
        for stem_asset_id in stem_asset_ids:
            stem_type = self._get_stem_type(stem_asset_id)
            canonical = STEM_MAP.get(stem_type)
            asset_id_map[stem_type] = stem_asset_id
            if canonical is None:
                continue
            dest = output_dir / f"{canonical}.wav"
            self._download_stem(stem_asset_id, dest)
            results[canonical] = str(dest)

        # Save asset IDs so individual stems can be re-downloaded without re-separating
        import json
        ids_path = output_dir / "asset_ids.json"
        with open(ids_path, "w") as f:
            json.dump(asset_id_map, f, indent=2)

        return results
