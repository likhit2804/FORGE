"""Download annual IMD 0.25-degree daily rainfall NetCDF files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DOWNLOAD_ENDPOINT = "https://www.imdpune.gov.in/cmpg/Griddata/RF25.php"
SOURCE_PAGE = "https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html"
MAX_FILE_BYTES = 100 * 1024 * 1024
NETCDF_SIGNATURES = (b"CDF\x01", b"CDF\x02", b"CDF\x05", b"\x89HDF\r\n\x1a\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_netcdf(path: Path) -> bool:
    with path.open("rb") as stream:
        signature = stream.read(8)
    return any(signature.startswith(magic) for magic in NETCDF_SIGNATURES)


def download_year(year: int, output_dir: Path, timeout: int = 120) -> dict:
    if not 1901 <= year <= 2025:
        raise ValueError("year must be between 1901 and 2025")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"RF25_ind{year}_rfp25.nc"
    if destination.is_file():
        if not is_netcdf(destination):
            raise ValueError(f"existing file is not NetCDF: {destination}")
        return {"year": year, "path": str(destination), "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination), "status": "already_present"}

    request = Request(
        DOWNLOAD_ENDPOINT,
        data=urlencode({"RF25": str(year)}).encode("ascii"),
        headers={"User-Agent": "MonsoonImpactNavigator/0.1", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    temp_path = None
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError(f"IMD returned HTTP {status} for {year}")
            with tempfile.NamedTemporaryFile(prefix=f"imd-{year}-", suffix=".part",
                                             dir=output_dir, delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                total = 0
                first_bytes = b""
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_FILE_BYTES:
                        raise RuntimeError(f"IMD response exceeded {MAX_FILE_BYTES} bytes")
                    if len(first_bytes) < 8:
                        first_bytes += chunk[:8 - len(first_bytes)]
                    temp_file.write(chunk)
        if total < 1024 or not any(first_bytes.startswith(magic) for magic in NETCDF_SIGNATURES):
            preview = first_bytes.decode("ascii", errors="replace")
            raise RuntimeError(f"IMD response for {year} is not a valid NetCDF file (header={preview!r})")
        os.replace(temp_path, destination)
        temp_path = None
        return {"year": year, "path": str(destination), "bytes": total,
                "sha256": sha256_file(destination), "status": "downloaded"}
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/imd_gridded"))
    args = parser.parse_args()
    if args.end_year < args.start_year:
        parser.error("--end-year must be at least --start-year")
    try:
        results = [download_year(year, args.output_dir) for year in range(args.start_year, args.end_year + 1)]
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    manifest = {
        "source": SOURCE_PAGE, "download_endpoint": DOWNLOAD_ENDPOINT,
        "dataset": "IMD daily gridded rainfall, 0.25-degree, NetCDF",
        "citation": "Pai et al. (2014), MAUSAM, 65(1), pp. 1-18",
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": results,
        "notice": "Retain attribution and verify data-use terms before redistribution.",
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['year']}: {result['status']}, {result['bytes']} bytes, sha256={result['sha256']}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
