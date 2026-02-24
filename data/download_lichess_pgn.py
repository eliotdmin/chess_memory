#!/usr/bin/env python3
"""
One-time download of Lichess games for dataset generation.
Downloads a monthly PGN dump (Standard, rated games) and decompresses it.

Usage:
  python data/download_lichess_pgn.py                    # downloads current month
  python data/download_lichess_pgn.py 2024-01           # downloads Jan 2024
  python data/download_lichess_pgn.py 2024-01 -o ./     # custom output dir

Files are large (~5–20 GB compressed). Ensure enough disk space.
"""

import argparse
import subprocess
import sys
from pathlib import Path

BASE_URL = "https://database.lichess.org/standard"
DEFAULT_OUTPUT = Path(__file__).parent


def main():
    import urllib.request

    parser = argparse.ArgumentParser(
        description="Download Lichess monthly PGN for dataset generation"
    )
    parser.add_argument(
        "month",
        nargs="?",
        default="2024-06",
        help="Year-month, e.g. 2024-01 (default: current month)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory to save the PGN file",
    )
    args = parser.parse_args()

    if args.month:
        year_month = args.month
    else:
        from datetime import date

        today = date.today()
        year_month = today.strftime("%Y-%m")

    filename = f"lichess_db_standard_rated_{year_month}.pgn.zst"
    url = f"{BASE_URL}/{filename}"
    # Full URL format: https://database.lichess.org/standard/lichess_db_standard_rated_YYYY-MM.pgn.zst

    out_dir = args.output.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    zst_path = out_dir / filename
    pgn_path = out_dir / filename.replace(".zst", "")

    print(f"Downloading {filename} from Lichess...")
    print(f"  URL: {url}")
    print(f"  Save to: {zst_path}")
    print("\n  (This can take 10–60+ minutes depending on connection. Files are ~5–20 GB.)")
    print()

    try:
        urllib.request.urlretrieve(url, zst_path, reporthook=_progress)
    except Exception as e:
        print(f"\nDownload failed: {e}")
        if "404" in str(e) or "Not Found" in str(e).lower():
            print(f"\n  Month {year_month} may not be available. Try e.g. 2024-06")
        sys.exit(1)

    print("\n\nDecompressing (zstd)...")
    try:
        subprocess.run(
            ["zstd", "-d", str(zst_path)],
            check=True,
        )
        print(f"Done. PGN saved to: {pgn_path}")
        print(f"\nNext step: python data/generate_dataset.py {pgn_path} -n 150000")
    except FileNotFoundError:
        print("  zstd not found. Install: brew install zstd")
        print(f"  Or decompress manually: zstd -d {zst_path}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"  Decompression failed: {e}")
        sys.exit(1)


def _progress(block_num, block_size, total_size):
    if total_size <= 0:
        return
    downloaded = block_num * block_size
    pct = min(100, 100 * downloaded / total_size)
    mb = downloaded / (1024 * 1024)
    total_mb = total_size / (1024 * 1024)
    print(f"\r  {pct:.1f}% — {mb:.1f} / {total_mb:.1f} MB", end="", flush=True)


if __name__ == "__main__":
    main()
