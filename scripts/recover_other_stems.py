"""
Download the missing 'other' stem for tracks that have bass/drums/vocals but not other.
Queries the Fadr account's existing assets to avoid re-separating (and re-paying).
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

BASE_URL = "https://api.fadr.com"
SEP_ROOT = Path("data/separated/fadr")


def headers():
    return {"Authorization": f"Bearer {os.environ['FADR_API_KEY']}"}


def get_download_url(asset_id: str) -> str:
    r = requests.get(
        f"{BASE_URL}/assets/download/{asset_id}/download",
        headers=headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["url"]


def download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)


def find_incomplete_tracks() -> list:
    return [
        d for d in sorted(SEP_ROOT.iterdir())
        if d.is_dir() and not (d / "other.wav").exists()
    ]


def fetch_account_assets(page_size: int = 100) -> list:
    """Fetch all assets from the account, paginated."""
    assets = []
    skip = 0
    while True:
        r = requests.get(
            f"{BASE_URL}/assets",
            params={"limit": page_size, "skip": skip},
            headers=headers(),
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json().get("assets", [])
        if not batch:
            break
        assets.extend(batch)
        skip += len(batch)
        if len(batch) < page_size:
            break
    return assets


def main():
    incomplete = find_incomplete_tracks()
    if not incomplete:
        print("All tracks already have 4 stems.")
        return

    print(f"Found {len(incomplete)} tracks missing 'other' stem — fetching account assets...")
    all_assets = fetch_account_assets()
    print(f"Retrieved {len(all_assets)} total assets from account.")

    # Index assets named "mixture-other" by their parent (look up stems of upload assets)
    other_stems = [a for a in all_assets if a.get("metaData", {}).get("stemType") == "other"]
    print(f"Found {len(other_stems)} 'other' stem assets.\n")

    # Match each incomplete track to an other-stem asset by checking sibling stems
    # The other stem's name is "mixture-other"; we identify which track it belongs to
    # by cross-referencing the upload asset name against track directory names.
    upload_assets = {a["_id"]: a for a in all_assets if a.get("assetType") == "upload"}

    matched = 0
    for stem_asset in other_stems:
        # Find the parent upload asset via the stem's parent reference
        parent_id = stem_asset.get("parent") or stem_asset.get("uploadAsset")
        parent = upload_assets.get(parent_id, {})
        parent_name = parent.get("name", "")

        # Match against an incomplete track directory name
        for track_dir in incomplete:
            if track_dir.name == parent_name or parent_name.startswith(track_dir.name):
                dest = track_dir / "other.wav"
                print(f"Downloading {track_dir.name} → other.wav ... ", end="", flush=True)
                try:
                    url = get_download_url(stem_asset["_id"])
                    download(url, dest)
                    print("done")
                    matched += 1
                    incomplete.remove(track_dir)
                except Exception as e:
                    print(f"FAILED: {e}")
                break

    print(f"\nRecovered {matched} 'other' stems.")
    if incomplete:
        print(f"Still missing ({len(incomplete)} tracks — will need re-separation):")
        for d in incomplete:
            print(f"  {d.name}")


if __name__ == "__main__":
    main()
