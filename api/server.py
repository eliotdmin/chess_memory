"""
Flask API for the chess position evaluation quiz.
Serves random positions and records user guesses.
Supports positions.json or positions.db (SQLite).
In production, also serves the built React frontend from dist/.
"""

import json
import os
import random
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DIST_DIR = Path(__file__).resolve().parent.parent / "dist"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POSITIONS_FILE = DATA_DIR / "positions.json"
POSITIONS_DB = DATA_DIR / "positions.db"

EVAL_MIN = 0.5
EVAL_MAX = 2.5
MIN_MOVE = 14

VALID_GUESSES = ("white_winning", "white_better", "equal", "black_better", "black_winning")


def category_from_eval(eval_cp: float) -> str:
    """white_winning (1.25-2), white_better (0.5-1.25), black_better (-1.25--0.5), black_winning (-2--1.25)."""
    if eval_cp >= 1.25:
        return "white_winning"
    if eval_cp >= 0.5:
        return "white_better"
    if eval_cp >= -0.5:
        return "equal"
    if eval_cp >= -1.25:
        return "black_better"
    return "black_winning"


def _move_number_from_fen(fen: str) -> int:
    parts = fen.split()
    if len(parts) >= 6:
        try:
            return int(parts[5])
        except ValueError:
            pass
    return 0


def _load_from_json():
    if not POSITIONS_FILE.exists():
        return []
    with open(POSITIONS_FILE) as f:
        return json.load(f)


def _load_from_sqlite():
    if not POSITIONS_DB.exists():
        return []
    conn = sqlite3.connect(POSITIONS_DB)
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    rows = conn.execute("SELECT * FROM positions").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_positions(middlegame_only=True, clear_advantage_only=True):
    if POSITIONS_DB.exists():
        all_pos = _load_from_sqlite()
    elif POSITIONS_FILE.exists():
        all_pos = _load_from_json()
    else:
        return []
    if not middlegame_only and not clear_advantage_only:
        return all_pos
    filtered = all_pos
    if middlegame_only:
        filtered = [p for p in filtered if _move_number_from_fen(p.get("fen", "")) >= MIN_MOVE]
    if clear_advantage_only:
        ev = lambda p: abs(p.get("eval_cp", 0))
        filtered = [p for p in filtered if EVAL_MIN <= ev(p) <= EVAL_MAX]
    return filtered if filtered else all_pos


@app.route("/api/position")
def get_position():
    """Return a random position. Query params: middlegame_only, clear_advantage_only (default 1)."""
    middlegame = request.args.get("middlegame_only", "1").lower() in ("1", "true", "yes")
    clear_adv = request.args.get("clear_advantage_only", "1").lower() in ("1", "true", "yes")
    positions = load_positions(middlegame_only=middlegame, clear_advantage_only=clear_adv)
    if not positions:
        return jsonify({"error": "No positions loaded or none match filters."}), 500
    pos = random.choice(positions)
    payload = {"fen": pos["fen"]}
    for k in ("white", "black", "white_elo", "black_elo", "event", "date"):
        if pos.get(k):
            payload[k] = pos[k]
    return jsonify(payload)


@app.route("/api/guess", methods=["POST"])
def submit_guess():
    """
    Submit a guess and get feedback.
    Body: { "fen": "...", "guess": "white" | "black" | "equal" }
    """
    data = request.get_json() or {}
    fen = data.get("fen")
    guess = data.get("guess")
    if not fen or not guess:
        return jsonify({"error": "fen and guess required"}), 400
    if guess not in VALID_GUESSES:
        return jsonify({"error": f"guess must be one of: {', '.join(VALID_GUESSES)}"}), 400

    # Map legacy categories to new (for old positions.json)
    def normalize_cat(c):
        if c in VALID_GUESSES:
            return c
        if c == "white":
            return "white_better"  # legacy
        if c == "black":
            return "black_better"
        return "equal"

    # Search in unfiltered data so we can find any position
    all_pos = load_positions(middlegame_only=False, clear_advantage_only=False)
    pos = next((p for p in all_pos if p["fen"] == fen), None)
    if not pos:
        return jsonify({"error": "Position not found"}), 404

    raw_cat = pos.get("category", "")
    eval_cp = pos.get("eval_cp")
    # Compute actual category from eval so we're correct even with old dataset
    actual = category_from_eval(eval_cp) if eval_cp is not None else normalize_cat(raw_cat)
    correct = actual.lower() == guess.lower()
    payload = {
        "correct": correct,
        "actual": actual,
        "eval_cp": pos.get("eval_cp"),
        "best_move": pos.get("best_move"),
        "pv_san": pos.get("pv_san", ""),
    }
    for k in ("white", "black", "white_elo", "black_elo", "event", "date"):
        if pos.get(k):
            payload[k] = pos[k]
    return jsonify(payload)


# Serve React build (production). Must be last so /api routes take precedence.
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if not DIST_DIR.exists():
        return "Frontend not built. Run: npm run build", 503
    file_path = DIST_DIR / path if path else DIST_DIR / "index.html"
    if path and file_path.is_file():
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, "index.html")


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5001)), debug=True)
