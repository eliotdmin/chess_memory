#!/usr/bin/env python3
"""
Extract positions from PGN files and evaluate them with Stockfish.
Output: JSON file with FEN, eval, best move, and category (white/black/equal).

Only includes positions where one side is clearly better (|eval| >= 0.75).
Skips opening (move 1-13); focuses on middlegame and early endgame.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import chess
import chess.pgn

STOCKFISH_DEPTH = 20
EVAL_THRESHOLD = 0.75  # centipawns — only save positions with clear advantage
MIN_MOVE = 14  # skip opening (1-13); middlegame starts ~move 14
MAX_MOVE = 55  # include early endgame


def find_stockfish() -> str | None:
    """Find Stockfish binary (must be on PATH or common locations)."""
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


def get_evaluation(fen: str, depth: int = STOCKFISH_DEPTH) -> tuple[float, str | None]:
    """
    Run Stockfish on a position. Returns (centipawn_eval, best_move_uci).
    Eval is from White's perspective. Best move is UCI (e.g. "e2e4").
    """
    stockfish_path = find_stockfish()
    if not stockfish_path:
        raise RuntimeError(
            "Stockfish not found. Install it (brew install stockfish on macOS) and ensure it's on PATH."
        )

    # Avoid mate scores for our thresholding; use centipawn interpretation
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
    for _ in range(200):
        line = proc.stdout.readline()
        if not line:
            break
        output_lines.append(line)
        if "bestmove" in line:
            break
    proc.terminate()
    proc.wait(timeout=2)

    output = "".join(output_lines)
    eval_cp = 0.0
    best_move = None

    for line in output.split("\n"):
        if line.startswith("info ") and "score cp" in line:
            # Last info with score is the final one
            m = re.search(r"score cp (-?\d+)", line)
            if m:
                eval_cp = int(m.group(1)) / 100.0
        if line.startswith("info ") and "score mate" in line:
            # Mate: treat as very large eval
            m = re.search(r"score mate (-?\d+)", line)
            if m:
                mate_in = int(m.group(1))
                eval_cp = 10.0 if mate_in > 0 else -10.0
        if line.startswith("bestmove "):
            parts = line.split()
            if len(parts) >= 2 and parts[1] != "none":
                best_move = parts[1]

    return eval_cp, best_move


def category_from_eval(eval_cp: float) -> str:
    if eval_cp > EVAL_THRESHOLD:
        return "white"
    if eval_cp < -EVAL_THRESHOLD:
        return "black"
    return "equal"


def extract_positions_from_pgn(pgn_path: Path, limit: int = 100) -> list[dict]:
    """Extract positions from a PGN file (middlegame/early endgame, moves 14-55)."""
    positions = []
    game_count = 0

    with open(pgn_path) as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            game_count += 1
            board = game.board()
            move_count = 0
            for move in game.mainline_moves():
                board.push(move)
                move_count += 1
                if MIN_MOVE <= move_count <= MAX_MOVE:
                    fen = board.fen()
                    if not any(p.get("fen") == fen for p in positions):
                        positions.append(
                            {
                                "fen": fen,
                                "move_number": move_count,
                                "game_index": game_count,
                            }
                        )
                        if len(positions) >= limit:
                            return positions
            if len(positions) >= limit:
                break
    return positions


def main():
    # Check Stockfish first — don't overwrite anything if it's missing
    if not find_stockfish():
        print("Stockfish not found.")
        print("  Install: brew install stockfish (macOS)")
        print("  Ensure it's on your PATH.")
        print("\nExisting positions.json was not modified.")
        sys.exit(1)

    pgn_dir = Path(__file__).parent
    pgn_files = list(pgn_dir.glob("*.pgn"))
    if not pgn_files:
        print("No PGN files in data/. Add some .pgn files or run with sample data.")
        print("Creating sample positions from famous games...")
        # Generate a few positions from scratch using python-chess
        positions = generate_sample_positions()
    else:
        positions = []
        for pgn in pgn_files[:3]:
            positions.extend(extract_positions_from_pgn(pgn, limit=20))
        positions = positions[:50]

    if not positions:
        print("No positions extracted. Add PGN files to data/ or fix extraction.")
        sys.exit(1)

    print(f"Evaluating {len(positions)} positions with Stockfish (depth {STOCKFISH_DEPTH})...")
    print(f"Keeping only positions with |eval| >= {EVAL_THRESHOLD} (clear advantage)...")
    evaluated = []
    for i, p in enumerate(positions):
        fen = p["fen"]
        try:
            eval_cp, best_move = get_evaluation(fen)
            cat = category_from_eval(eval_cp)
            # Only save positions where one side is clearly better (skip "equal")
            if abs(eval_cp) >= EVAL_THRESHOLD:
                evaluated.append(
                    {
                        "fen": fen,
                        "eval_cp": round(eval_cp, 2),
                        "best_move": best_move,
                        "category": cat,
                    }
                )
                print(f"  [{i+1}/{len(positions)}] {cat} ({eval_cp:+.2f}) ✓")
            else:
                print(f"  [{i+1}/{len(positions)}] equal ({eval_cp:+.2f}) — skipped")
        except Exception as e:
            print(f"  [{i+1}] Error: {e}")

    out_path = pgn_dir / "positions.json"
    if not evaluated:
        print(f"\nNo positions passed the filter (|eval| >= {EVAL_THRESHOLD}).")
        print("Existing positions.json was NOT overwritten.")
        sys.exit(1)
    with open(out_path, "w") as f:
        json.dump(evaluated, f, indent=2)
    print(f"Saved {len(evaluated)} positions to {out_path}")


def generate_sample_positions() -> list[dict]:
    """Generate sample middlegame/early endgame positions when no PGN is available."""
    # Middlegame positions (piece count suggests move 14+) — last two FEN fields: halfmove, fullmove
    sample_fens = [
        # Sicilian middlegame — white advantage
        "r2qkb1r/1ppb1ppp/p1n1pn2/8/2BN4/4BP2/PPP2PPP/RN1QK2R w KQkq - 0 14",
        # Queen's Indian structure
        "r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/2N1PN2/PP3PPP/R1BQKB1R w KQ - 0 14",
        # Slav middlegame
        "r2qkb1r/ppp2ppp/2n1bn2/3p4/2PP4/2N2NP1/PP2PPBP/R1BQK2R w KQkq - 0 16",
        # French Tarrasch
        "r1bqkb1r/pp3ppp/2n1pn2/3p4/2PP4/2N2NP1/PP2PPBP/R1BQK2R w KQkq - 0 14",
        # Grünfeld
        "rnbqkb1r/pp2pp1p/5np1/2pP4/2P5/2N2N2/PP2PPPP/R1BQKB1R w KQkq - 0 14",
        # Catalan
        "r1bqkb1r/pp1n1ppp/2p1pn2/3p4/2PP4/2N1PN2/PP3PPP/R1BQKB1R w KQkq - 0 15",
        # King's Indian
        "r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/2N1PN2/PP3PPP/R1BQKB1R w KQ - 0 16",
        # Semi-Slav — black advantage
        "2kr1b1r/ppp2ppp/2n1bn2/3q4/3P4/2N2NP1/PP2PPBP/R1BQK2R w KQ - 0 18",
        # Ruy Lopez middlegame
        "r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/2N2NP1/PP2PPBP/R1BQK2R w KQ - 0 14",
        # Early endgame (pieces exchanged)
        "r4rk1/ppp2ppp/2n1bn2/3q4/3P4/2N2NP1/PP2PPBP/R1BQK2R w KQ - 0 20",
    ]
    return [{"fen": fen} for fen in sample_fens]


if __name__ == "__main__":
    main()
