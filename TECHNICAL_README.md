# Chess Eval Quiz — Technical Reference

Complete specs for data pipeline, API, and UI.

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18, Vite 5, react-chessboard, chess.js |
| Backend | Flask 3, flask-cors |
| Data | JSON (default) or SQLite |
| Engine | Stockfish (subprocess, dataset generation only) |
| PGN parsing | python-chess |

---

## Data Flow

```
PGN files → generate_dataset.py → positions.json | positions.db
                                        ↓
                              API (Flask) ← → React UI
```

The PGN is streamed once during generation. After that, only `positions.json` or `positions.db` is needed; the PGN can be deleted.

---

## Download Scripts

### download_lichess_sample.py

Fetches games via Lichess API. Small files, fast, shows progress bar.

| Flag | Default | Description |
|------|---------|-------------|
| `-u`, `--user` | DrNykterstein | Lichess username |
| `-n`, `--max-games` | 2000 | Max games to fetch |
| `-o`, `--output` | `data/lichess_sample.pgn` | Output path |

**Example:** `python data/download_lichess_sample.py -n 10000 -o data/lichess_sample.pgn`

### download_lichess_pgn.py

Downloads full Lichess monthly dumps (~5–20 GB compressed, ~25+ GB decompressed).

| Arg/Flag | Default | Description |
|----------|---------|-------------|
| `month` | 2024-06 | Year-month (YYYY-MM) |
| `-o`, `--output` | `data/` | Output directory |

**Example:** `python data/download_lichess_pgn.py 2024-06`

Requires `zstd` for decompression (`brew install zstd`).

---

## generate_dataset.py

Extracts positions from PGN, evaluates with Stockfish, outputs JSON or SQLite.

| Flag | Default | Description |
|------|---------|-------------|
| `pgn` | (required) | Path to PGN file or directory |
| `-n`, `--max-positions` | 150000 | Max positions to evaluate |
| `-d`, `--depth` | 18 | Stockfish depth (lower = faster) |
| `--min-move` | 14 | Skip opening; min move number |
| `--max-move` | 55 | Max move number |
| `--eval-min` | 0.5 | Min \|eval\| (centipawns) to save |
| `--eval-max` | 2.5 | Max \|eval\| (excludes obvious positions) |
| `--no-filter` | — | Save all positions (ignore filters) |
| `--sqlite` | — | Output SQLite DB instead of JSON |
| `-o`, `--output` | `data/positions.json` | Output path |

**Timing:** ~2–5 sec/position at depth 18; ~1–2 sec at depth 15. 100k positions ≈ 28–140 hours at depth 18.

**Examples:**
```bash
python data/generate_dataset.py data/lichess_sample.pgn -n 10000 -d 15
python data/generate_dataset.py data/lichess_db_standard_rated_2024-06.pgn -n 150000 --sqlite -o data/positions
```

---

## Eval Categories

Evaluations are bucketed into five categories (centipawns):

| Category | Eval range |
|----------|------------|
| white_winning | 1.25 – 2 |
| white_better | 0.5 – 1.25 |
| equal | -0.5 – 0.5 |
| black_better | -1.25 – -0.5 |
| black_winning | -2 – -1.25 |

With "Clear advantage only" filter (default): only positions with 0.5 ≤ \|eval\| ≤ 2.5 (no "equal" option in UI).

---

## Stored Position Format

Per position in JSON or SQLite:

| Field | Type | Description |
|-------|------|-------------|
| fen | string | Position FEN |
| eval_cp | float | Centipawn eval (Stockfish) |
| best_move | string | UCI best move |
| category | string | white_winning, white_better, equal, black_better, black_winning |
| pv_san | string | Best line in SAN |
| white | string | Player name (from PGN) |
| black | string | Player name |
| white_elo | string | Rating |
| black_elo | string | Rating |
| event | string | Event name |
| date | string | Game date |

---

## API

**Base URL:** `http://localhost:5001` (dev) or `/api` (production)

### GET /api/position

Returns a random position.

| Query param | Default | Description |
|-------------|---------|-------------|
| middlegame_only | 1 | Only positions with move ≥ 14 |
| clear_advantage_only | 1 | Only 0.5 ≤ \|eval\| ≤ 2.5 |

**Response:** `{ fen, white?, black?, white_elo?, black_elo?, event?, date? }`

### POST /api/guess

Submit a guess.

**Body:** `{ "fen": "...", "guess": "white_winning" | "white_better" | "equal" | "black_better" | "black_winning" }`

**Response:** `{ correct, actual, eval_cp, pv_san?, ... }`

Category is computed from `eval_cp` on each request, so old datasets display correctly.

---

## UI Behavior

- **Filters:** Middlegame only, Clear advantage only (toggles)
- **Guess options:** White winning (1), White better (2), Equal (3, hidden when clear-advantage filter on), Black better (4), Black winning (5)
- **Keyboard:** 1–5 to guess; Enter or N for next
- **Captured pieces:** Piece differential shown bottom-right, grouped by type (Q R B N P)
- **Data source:** API loads `positions.db` if present, else `positions.json`

---

## Project Structure

```
chess_memory/
├── api/server.py           # Flask API (port 5001)
├── data/
│   ├── download_lichess_pgn.py      # Full monthly PGN (~25 GB)
│   ├── download_lichess_sample.py   # API sample (progress bar)
│   ├── extract_positions.py         # Legacy
│   ├── generate_dataset.py          # PGN → positions
│   ├── positions.json               # Default positions
│   └── positions.db                 # SQLite (if --sqlite used)
├── src/
│   ├── App.jsx
│   ├── App.css
│   └── capturedPieces.js
├── package.json
├── requirements.txt
├── README.md
└── TECHNICAL_README.md
```

---

## License

Stockfish is GPL. Serving pre-computed positions does not require GPL compliance for the app.
