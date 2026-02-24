# Chess Eval Quiz

Train your ability to evaluate chess positions. You're shown a board and must guess who is better — **White winning**, **White better**, **Equal**, **Black better**, or **Black winning**. Evaluations come from Stockfish.

## Quick Start

**Prerequisites:** Node.js, Python 3.10+, Stockfish (`brew install stockfish` on macOS)

```bash
# Terminal 1
pip install -r requirements.txt
python api/server.py

# Terminal 2
npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173). A pre-computed `positions.json` is included.

---

## Getting More Positions

**Recommended: Small sample** (minutes, no huge files)

```bash
python data/download_lichess_sample.py -n 10000   # Progress bar, ~10–30 MB
python data/generate_dataset.py data/lichess_sample.pgn -n 10000 -d 15
```

**Large scale** (100k+ positions, hours of compute)

1. Download Lichess monthly dump: `python data/download_lichess_pgn.py 2024-06`
2. Generate: `python data/generate_dataset.py data/lichess_db_standard_rated_2024-06.pgn -n 150000`
3. Delete the PGN when done — the app only needs `positions.json` (or `positions.db` with `--sqlite`)

See [TECHNICAL_README.md](TECHNICAL_README.md) for full specs. To deploy so others can play: [DEPLOY.md](DEPLOY.md).
