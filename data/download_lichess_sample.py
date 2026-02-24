#!/usr/bin/env python3
"""
Download a small PGN sample (~1–5 MB) for fast pipeline testing.
Fetches recent games from Lichess via their public API — no auth required.
"""

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Prolific players — many games = good variety
# Using bot accounts that play constantly
DEFAULT_USER = "DrNykterstein"  # Magnus's account, many games
SAMPLE_USERS = ["DrNykterstein", "Lichess", "Fakefish"]  # fallbacks

DEFAULT_OUTPUT = Path(__file__).parent
MAX_GAMES = 2000  # ~2–5 MB, finishes in seconds
CHUNK_SIZE = 65536  # 64 KB
BATCH_SIZE = 800  # Smaller batches = less likely to hit connection limits
BATCH_DELAY = 2.0  # Seconds between batches (avoid rate limiting)
MAX_RETRIES = 4


def _progress_bar(downloaded: int, total: int | None, width: int = 40, prefix: str = "") -> None:
    """Print a simple text progress bar."""
    mb = downloaded / (1024 * 1024)
    if total is not None and total > 0:
        pct = min(100, 100 * downloaded / total)
        filled = int(width * downloaded / total)
        bar = "=" * filled + ">" * (1 if filled < width else 0) + " " * (width - filled - 1)
        total_mb = total / (1024 * 1024)
        sys.stdout.write(f"\r  {prefix}[{bar}] {pct:5.1f}%  {mb:.2f} / {total_mb:.2f} MB")
    else:
        sys.stdout.write(f"\r  {prefix}Downloading... {mb:.2f} MB")
    sys.stdout.flush()


def _fetch_batch(url: str, prefix: str = "") -> bytes:
    """Fetch from URL with progress bar. Raises on failure."""
    req = urllib.request.Request(url, headers={"Accept": "application/x-chess-pgn"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        total = resp.headers.get("Content-Length")
        total = int(total) if total else None
        chunks = []
        downloaded = 0
        while True:
            chunk = resp.read(CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
            downloaded += len(chunk)
            _progress_bar(downloaded, total, prefix=prefix)
    return b"".join(chunks)


def _extract_last_game_id(pgn_data: bytes) -> str | None:
    """Extract the last game ID from PGN (from Site header: https://lichess.org/ID)."""
    text = pgn_data.decode("utf-8", errors="ignore")
    # Find last [Site "https://lichess.org/ABC123"] - game ID is ABC123
    matches = list(re.finditer(r'\[Site\s+"https?://lichess\.org/([A-Za-z0-9]+)"\]', text))
    return matches[-1].group(1) if matches else None


def main():
    parser = argparse.ArgumentParser(
        description="Download a small PGN sample for testing (no overnight wait)"
    )
    parser.add_argument(
        "-u",
        "--user",
        default=DEFAULT_USER,
        help=f"Lichess username to fetch games from (default: {DEFAULT_USER})",
    )
    parser.add_argument(
        "-n",
        "--max-games",
        type=int,
        default=MAX_GAMES,
        help=f"Max games to fetch (default {MAX_GAMES})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT / "lichess_sample.pgn",
        help="Output PGN path",
    )
    args = parser.parse_args()

    out_path = args.output.resolve()
    max_games = args.max_games

    print(f"Fetching up to {max_games} games from {args.user}...")
    if max_games > BATCH_SIZE:
        print(f"  (Using batches of {BATCH_SIZE} to avoid connection drops)\n")
    else:
        print()

    all_pgns: list[bytes] = []
    total_games = 0
    batch_num = 0
    before = None

    while total_games < max_games:
        n = min(BATCH_SIZE, max_games - total_games)

        params = f"max={n}&format=pgn"
        if before:
            params += f"&before={before}"
        url = f"https://lichess.org/api/games/user/{args.user}?{params}"

        for attempt in range(MAX_RETRIES):
            try:
                if max_games > BATCH_SIZE:
                    batch_num += 1
                    total_batches = (max_games + BATCH_SIZE - 1) // BATCH_SIZE
                    prefix = f"Batch {batch_num}/{total_batches} "
                else:
                    prefix = ""
                print(f"  Connecting...", end="", flush=True)
                data = _fetch_batch(url, prefix=prefix)
                print()  # newline after progress bar
                if not data or len(data.strip()) < 100:
                    total_games = max_games  # exit loop
                    break
                games_in_batch = data.count(b"[Event ")
                all_pgns.append(data)
                total_games += games_in_batch
                if total_games >= max_games or games_in_batch < n:
                    total_games = max_games  # done
                    break
                before = _extract_last_game_id(data)
                if not before:
                    total_games = max_games
                    break
                time.sleep(BATCH_DELAY)
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    print(f"\n  User '{args.user}' not found. Try: -u Lichess")
                    return 1
                if attempt < MAX_RETRIES - 1:
                    print(f"\n  Connection issue (attempt {attempt + 1}/{MAX_RETRIES}), retrying in 3s...")
                    time.sleep(3)
                else:
                    print(f"\n  Download failed after {MAX_RETRIES} attempts: {e}")
                    return 1
            except urllib.error.URLError as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"\n  Connection error (attempt {attempt + 1}/{MAX_RETRIES}), retrying in 3s...")
                    time.sleep(3)
                else:
                    print(f"\n  Download failed after {MAX_RETRIES} attempts: {e}")
                    return 1
            except OSError as e:
                # ConnectionResetError, BrokenPipeError, etc.
                if attempt < MAX_RETRIES - 1:
                    print(f"\n  Connection error (attempt {attempt + 1}/{MAX_RETRIES}), retrying in 5s...")
                    time.sleep(5)
                else:
                    print(f"\n  Download failed after {MAX_RETRIES} attempts: {e}")
                    return 1
            except Exception as e:
                # RemoteDisconnected, IncompleteRead, and other connection drops
                err_name = type(e).__name__.lower()
                msg = str(e).lower()
                retryable = (
                    "incomplete" in err_name or "remote" in err_name or "connection" in err_name
                    or "connection" in msg or "closed" in msg or "reset" in msg
                )
                if retryable and attempt < MAX_RETRIES - 1:
                    print(f"\n  Connection dropped (attempt {attempt + 1}/{MAX_RETRIES}), retrying in 5s...")
                    time.sleep(5)
                else:
                    print(f"\n  Download failed: {e}")
                    return 1

        if not before:
            break

    if not all_pgns:
        print("  No games fetched.")
        return 1

    data = b"\n\n".join(all_pgns)
    out_path.write_bytes(data)
    size_mb = len(data) / (1024 * 1024)
    game_count = data.count(b"[Event ")
    print(f"  Saved {size_mb:.2f} MB ({game_count} games) to {out_path}")
    print(f"\nNext: python data/generate_dataset.py {out_path} -n 5000")
    return 0


if __name__ == "__main__":
    exit(main())
