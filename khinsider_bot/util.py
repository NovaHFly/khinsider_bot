from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from random import randint
from shutil import rmtree

from .constants import ROOT_DOWNLOADS_PATH


@contextmanager
def setup_download(existing_downloads: dict | None = None) -> Iterator[Path]:
    """Setup download path and remove it when done."""
    if existing_downloads is None:
        existing_downloads = {}

    while (
        download_id := randint(1, 999999)
    ) and download_id in existing_downloads:
        pass

    download_dir = (ROOT_DOWNLOADS_PATH) / str(download_id)
    existing_downloads[download_id] = download_dir

    try:
        yield download_dir
    finally:
        rmtree(download_dir, ignore_errors=True)
        existing_downloads.pop(download_id, None)
