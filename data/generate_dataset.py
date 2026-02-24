#!/usr/bin/env python3
"""
Large-scale one-time data dump: chess positions with Stockfish evaluations and best lines.
Target: 100,000+ positions from PGN files.

Output: positions.json with fen, eval_cp, best_move, category, pv_san (best line in SAN).
Filters: |eval| >= threshold, move >= min_move (both applied during generation).
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import chess
import chess.pgn

DEFAULT_DEPTH = 18
DEFAULT_EVAL_THRESHOLD = 0.5
DEFAULT_EVAL_MAX = 2.5  # exclude obvious positions
DEFAULT_MIN_MOVE = 14
DEFAULT_MAX_MOVE = 55
PV_LENGTH = 6  # number of half-moves (plies) to include in best line


def find_stockfish() -> str | None:
    for name in ["stockfish", "Stockfish"]:
        try:
            result = subprocess.run(
                [name, "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return name
        except FileNotFoundError:
            continue
    return None


def get_eval_and_pv(
    fen: str,
    depth: int,
) -> tuple[float, str | None, list[str]]:
    """Returns (eval_cp, best_move_uci, pv_uci_list)."""
    stockfish_path = find_stockfish()
    if not stockfish_path:
        raise RuntimeError("Stockfish not found on PATH.")

    proc = subprocess.Popen(
        [stockfish_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    commands = [
        "uci",
        "setoption name UCI_AnalyseMode value false",
        f"position fen {fen}",
        f"go depth {depth}",
    ]
    proc.stdin.write("\n".join(commands) + "\n")
    proc.stdin.flush()

    output_lines = []
    for _ in range(300):
        line = proc.stdout.readline()
        if not line:
            break
        output_lines.append(line)
        if "bestmove" in line:
            break
    proc.terminate()
    proc.wait(timeout=5)

    output = "".join(output_lines)
    eval_cp = 0.0
    best_move = None
    pv_uci: list[str] = []

    # Find the last info line with a full PV (depth completion)
    last_pv_line = None
    for line in output.split("\n"):
        if line.startswith("info ") and "score cp" in line:
            m = re.search(r"score cp (-?\d+)", line)
            if m:
                eval_cp = int(m.group(1)) / 100.0
        if line.startswith("info ") and "score mate" in line:
            m = re.search(r"score mate (-?\d+)", line)
            if m:
                mate_in = int(m.group(1))
                eval_cp = 10.0 if mate_in > 0 else -10.0
        if " pv " in line:
            last_pv_line = line
        if line.startswith("bestmove "):
            parts = line.split()
            if len(parts) >= 2 and parts[1] != "none":
                best_move = parts[1]

    if last_pv_line:
        idx = last_pv_line.find(" pv ")
        if idx >= 0:
            pv_part = last_pv_line[idx + 4 :].strip()
            pv_uci = pv_part.split()[: PV_LENGTH * 2]  # max plies

    return eval_cp, best_move, pv_uci


def uci_pv_to_san(fen: str, pv_uci: list[str]) -> str:
    """Convert UCI move list to SAN with move numbers (e.g. '1. e4 e5 2. Nf3')."""
    if not pv_uci:
        return ""
    try:
        board = chess.Board(fen)
        san_moves: list[str] = []
        for uci in pv_uci:
            if len(uci) < 4:
                continue
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                break
            if board.turn:
                san_moves.append(f"{board.fullmove_number}. {board.san(move)}")
            else:
                san_moves.append(board.san(move))
            board.push(move)
        return " ".join(san_moves)
    except Exception:
        return " ".join(pv_uci[: PV_LENGTH * 2])


def _game_metadata(game) -> dict:
    """Extract game metadata from PGN headers."""
    h = game.headers
    return {
        "white": h.get("White", ""),
        "black": h.get("Black", ""),
        "white_elo": h.get("WhiteElo", ""),
        "black_elo": h.get("BlackElo", ""),
        "event": h.get("Event", ""),
        "date": h.get("Date", ""),
    }


def extract_positions_from_pgn(
    pgn_path: Path,
    min_move: int,
    max_move: int,
    seen_fens: set[str],
    limit: int,
) -> list[dict]:
    """Extract positions from a PGN file with game metadata."""
    positions = []
    with open(pgn_path, encoding="utf-8", errors="ignore") as f:
        while len(positions) < limit:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            meta = _game_metadata(game)
            board = game.board()
            move_count = 0
            for move in game.mainline_moves():
                board.push(move)
                move_count += 1
                if min_move <= move_count <= max_move:
                    fen = board.fen()
                    if fen not in seen_fens:
                        seen_fens.add(fen)
                        positions.append({
                            "fen": fen,
                            "move_number": move_count,
                            **meta,
                        })
                        if len(positions) >= limit:
                            return positions
    return positions


def category_from_eval(eval_cp: float) -> str:
    """Map eval to: white_winning (1.25-2), white_better (0.5-1.25), equal, black_better (-1.25--0.5), black_winning (-2--1.25)."""
    if eval_cp >= 1.25:
        return "white_winning"
    if eval_cp >= 0.5:
        return "white_better"
    if eval_cp >= -0.5:
        return "equal"
    if eval_cp >= -1.25:
        return "black_better"
    return "black_winning"


def main():
    parser = argparse.ArgumentParser(
        description="Generate a large dataset of chess positions with Stockfish eval and best line (SAN)."
    )
    parser.add_argument(
        "pgn",
        type=Path,
        help="Path to PGN file or directory of PGN files",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).parent / "positions.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "-n",
        "--max-positions",
        type=int,
        default=150_000,
        help="Max positions to evaluate (default 150000)",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=DEFAULT_DEPTH,
        help="Stockfish depth (default 18, lower=faster)",
    )
    parser.add_argument(
        "--min-move",
        type=int,
        default=DEFAULT_MIN_MOVE,
        help="Skip opening: min move number (default 14)",
    )
    parser.add_argument(
        "--max-move",
        type=int,
        default=DEFAULT_MAX_MOVE,
        help="Max move number (default 55)",
    )
    parser.add_argument(
        "--eval-min",
        type=float,
        default=DEFAULT_EVAL_THRESHOLD,
        help="Min |eval| to save (default 0.5)",
    )
    parser.add_argument(
        "--eval-max",
        type=float,
        default=DEFAULT_EVAL_MAX,
        help="Max |eval| to save, excludes obvious (default 2.5)",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Save all positions (ignore eval and move filters)",
    )
    parser.add_argument(
        "--sqlite",
        action="store_true",
        help="Output SQLite DB instead of JSON (efficient for 100k+ positions)",
    )
    args = parser.parse_args()

    if not find_stockfish():
        print("Stockfish not found. Install: brew install stockfish")
        sys.exit(1)

    pgn_path = args.pgn.resolve()
    if not pgn_path.exists():
        print(f"Path not found: {pgn_path}")
        sys.exit(1)

    pgn_files: list[Path] = []
    if pgn_path.is_file():
        pgn_files = [pgn_path]
    else:
        pgn_files = sorted(pgn_path.glob("**/*.pgn"))

    if not pgn_files:
        print("No PGN files found.")
        sys.exit(1)

    print(f"Found {len(pgn_files)} PGN file(s). Extracting positions (move {args.min_move}-{args.max_move})...")
    seen = set()
    positions: list[dict] = []
    for pf in pgn_files:
        extracted = extract_positions_from_pgn(
            pf, args.min_move, args.max_move, seen, args.max_positions - len(positions)
        )
        positions.extend(extracted)
        if len(positions) >= args.max_positions:
            break

    positions = positions[: args.max_positions]
    print(f"Extracted {len(positions)} unique positions. Evaluating with Stockfish (depth {args.depth})...")
    if not args.no_filter:
        print(f"Keeping positions with {args.eval_min} <= |eval| <= {args.eval_max}")

    evaluated: list[dict] = []
    interval = max(1, len(positions) // 100)

    for i, p in enumerate(positions):
        fen = p["fen"]
        try:
            eval_cp, best_move, pv_uci = get_eval_and_pv(fen, args.depth)
            pv_san = uci_pv_to_san(fen, pv_uci)
            cat = category_from_eval(eval_cp)
            abs_eval = abs(eval_cp)

            if args.no_filter or (args.eval_min <= abs_eval <= args.eval_max):
                entry = {
                    "fen": fen,
                    "eval_cp": round(eval_cp, 2),
                    "best_move": best_move,
                    "category": cat,
                    "pv_san": pv_san,
                }
                for k in ("white", "black", "white_elo", "black_elo", "event", "date"):
                    if p.get(k):
                        entry[k] = p[k]
                evaluated.append(entry)

            if (i + 1) % interval == 0:
                print(f"  Progress: {i+1}/{len(positions)} — saved {len(evaluated)}")
        except Exception as e:
            if (i + 1) % interval == 0:
                print(f"  Progress: {i+1}/{len(positions)} — error: {e}")

    out = args.output.resolve()
    if args.sqlite:
        out = out.with_suffix(".db") if out.suffix != ".db" else out
        conn = sqlite3.connect(out)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                fen TEXT PRIMARY KEY, eval_cp REAL, best_move TEXT, category TEXT,
                pv_san TEXT, white TEXT, black TEXT, white_elo TEXT, black_elo TEXT,
                event TEXT, date TEXT
            )
        """)
        conn.executemany(
            """INSERT OR REPLACE INTO positions VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    e.get("fen"), e.get("eval_cp"), e.get("best_move"), e.get("category"),
                    e.get("pv_san", ""), e.get("white", ""), e.get("black", ""),
                    e.get("white_elo", ""), e.get("black_elo", ""),
                    e.get("event", ""), e.get("date", ""),
                )
                for e in evaluated
            ],
        )
        conn.commit()
        conn.close()
        print(f"Saved {len(evaluated)} positions to {out} (SQLite)")
    else:
        with open(out, "w") as f:
            json.dump(evaluated, f, indent=2)
        print(f"Saved {len(evaluated)} positions to {out}")


if __name__ == "__main__":
    main()
