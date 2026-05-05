"""S3 presigned URL helpers for uploading mixtures and downloading separated stems."""

import os
from pathlib import Path

import boto3
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()


def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def _config() -> dict:
    config_path = Path(__file__).parents[2] / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)["storage"]


def upload(local_path: str | Path) -> str:
    """Upload a file to S3 and return a presigned GET URL."""
    cfg = _config()
    bucket = os.environ.get("STORAGE_BUCKET") or cfg["bucket"]
    ttl = cfg.get("presigned_url_ttl_s", 3600)
    key = Path(local_path).name

    s3 = _s3_client()
    s3.upload_file(str(local_path), bucket, key)
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=ttl,
    )
    return url


def download(url: str, dest: str | Path) -> Path:
    """Download from any URL to a local path."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return dest


def delete(key: str) -> None:
    """Remove an object from the bucket (cleanup after separation)."""
    cfg = _config()
    bucket = os.environ.get("STORAGE_BUCKET") or cfg["bucket"]
    _s3_client().delete_object(Bucket=bucket, Key=key)
