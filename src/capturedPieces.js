/**
 * Compute captured pieces from FEN (piece differential).
 * Returns { white: [...], black: [...] } — pieces each side has captured from opponent.
 * white = what White captured (Black's missing pieces), black = what Black captured (White's missing).
 * Pieces are grouped by type (Q R B N P) so similar pieces appear adjacent.
 */
const STARTING = { P: 8, N: 2, B: 2, R: 2, Q: 1, K: 1 };
const PIECE_ORDER = ["Q", "R", "B", "N", "P"]; // display order, K never captured

const SYMBOLS = { P: "♙", N: "♘", B: "♗", R: "♖", Q: "♕", K: "♔", p: "♟", n: "♞", b: "♝", r: "♜", q: "♛", k: "♚" };

function groupPieces(arr) {
  return [...arr].sort((a, b) => {
    const order = (s) => {
      const u = Object.entries(SYMBOLS).find(([, v]) => v === s);
      if (!u) return 99;
      const p = u[0];
      const idx = PIECE_ORDER.indexOf(p.toUpperCase());
      return idx >= 0 ? idx : 99;
    };
    return order(a) - order(b);
  });
}

export function getCapturedPieces(fen) {
  if (!fen) return { white: [], black: [] };
  const placement = fen.split(" ")[0].replace(/\d/g, (d) => ".".repeat(parseInt(d, 10)));
  const count = { P: 0, N: 0, B: 0, R: 0, Q: 0, K: 0, p: 0, n: 0, b: 0, r: 0, q: 0, k: 0 };
  for (const c of placement) {
    if (c !== "." && count[c] !== undefined) count[c]++;
  }
  const white = [];
  const black = [];
  for (const piece of PIECE_ORDER) {
    const pl = piece.toLowerCase();
    const wCount = count[piece] ?? 0;
    const bCount = count[pl] ?? 0;
    const start = STARTING[piece];
    for (let i = wCount; i < start; i++) black.push(SYMBOLS[pl]);
    for (let i = bCount; i < start; i++) white.push(SYMBOLS[piece]);
  }
  return { white: groupPieces(white), black: groupPieces(black) };
}
