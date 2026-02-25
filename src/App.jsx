import { useState, useEffect, useCallback } from "react";
import { Chessboard } from "react-chessboard";
import { getCapturedPieces } from "./capturedPieces";
import "./App.css";

// Use full URL so it works whether loaded via Vite dev server or otherwise
const API_BASE =
  import.meta.env.DEV ? "http://localhost:5001/api" : "/api";

function evalToHumanReadable(evalCp, actual) {
  if (evalCp == null) return "";
  const cat = (actual || "").toLowerCase();
  const formatCp = () => `${evalCp > 0 ? "+" : ""}${evalCp.toFixed(2)}`;
  if (cat === "white_winning") return `White is winning (${formatCp()})`;
  if (cat === "white_better") return `White is better (${formatCp()})`;
  if (cat === "black_winning") return `Black is winning (${formatCp()})`;
  if (cat === "black_better") return `Black is better (${formatCp()})`;
  if (cat === "equal") return `Roughly equal (${formatCp()})`;
  return `Roughly equal (${formatCp()})`;
}

export default function App() {
  const [position, setPosition] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [score, setScore] = useState({ correct: 0, total: 0, streak: 0 });
  const [filters, setFilters] = useState({
    middlegameOnly: true,
  });

  const loadPosition = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFeedback(null);
    const params = new URLSearchParams({
      middlegame_only: filters.middlegameOnly ? "1" : "0",
      clear_advantage_only: "1",
    });
    try {
      const res = await fetch(`${API_BASE}/position?${params}`);
      if (!res.ok) throw new Error("Failed to load position");
      const data = await res.json();
      setPosition(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filters.middlegameOnly]);

  const submitGuess = useCallback(async (guess) => {
    if (!position?.fen) return;
    try {
      const res = await fetch(`${API_BASE}/guess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fen: position.fen, guess }),
      });
      const data = await res.json();
      setFeedback(data);
      setScore((s) => ({
        correct: s.correct + (data.correct ? 1 : 0),
        total: s.total + 1,
        streak: data.correct ? s.streak + 1 : 0,
      }));
    } catch (e) {
      setFeedback({ correct: false, error: e.message });
    }
  }, [position]);

  useEffect(() => {
    loadPosition();
  }, [loadPosition]);

  useEffect(() => {
    const handleKey = (e) => {
      if (!position?.fen) return;
      if (feedback) {
        if (e.key === "Enter" || e.key === "n" || e.key === "N") loadPosition();
        return;
      }
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      const key = e.key;
      if (key === "1") submitGuess("white_winning");
      else if (key === "2") submitGuess("white_better");
      else if (key === "3") submitGuess("black_better");
      else if (key === "4") submitGuess("black_winning");
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [position, feedback, submitGuess, loadPosition]);

  if (loading && !position) {
    return (
      <div className="app">
        <header className="header">
          <h1>Chess Eval Quiz</h1>
          <p className="subtitle">Which side is better?</p>
        </header>
        <div className="loading">Loading position…</div>
      </div>
    );
  }

  if (error || (!loading && !position?.fen)) {
    return (
      <div className="app">
        <header className="header">
          <h1>Chess Eval Quiz</h1>
        </header>
        <div className="error">
          <p>{error || "No position received."}</p>
          <p className="hint">
            Make sure the API server is running: <code>python api/server.py</code>
          </p>
          <button onClick={loadPosition}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Chess Eval Quiz</h1>
        <p className="subtitle">Which side is better?</p>
        <p className="shortcuts-hint shortcuts-hint-header">Press <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> <kbd>4</kbd> to guess</p>
        <div className="filters">
          <label className="filter-toggle">
            <input
              type="checkbox"
              checked={filters.middlegameOnly}
              onChange={(e) =>
                setFilters((f) => ({ ...f, middlegameOnly: e.target.checked }))
              }
            />
            <span>Middlegame only (move 14+)</span>
          </label>
        </div>
        {score.total > 0 && (
          <div className="score-row">
            <span className="score">Score: {score.correct}/{score.total}</span>
            {score.streak > 0 && (
              <span className="streak">{score.streak} in a row</span>
            )}
          </div>
        )}
      </header>

      <main className="main">
        <div className="board-area">
          <div className="board-wrapper">
            <Chessboard
              boardWidth={480}
              position={position?.fen}
              boardOrientation={
                position?.fen?.includes(" w ") ? "white" : "black"
              }
              arePiecesDraggable={false}
              customDarkSquareStyle={{ backgroundColor: "#779952" }}
              customLightSquareStyle={{ backgroundColor: "#edeed1" }}
            />
          </div>
          <div className="captured-pieces">
            {(() => {
              const { white, black } = getCapturedPieces(position?.fen);
              return (
                <div className="captured-stack">
                  <div className="captured-row captured-black" title="Pieces Black has captured">
                    {black.length ? black.map((s, i) => <span key={i} className="piece-sym">{s}</span>) : "—"}
                  </div>
                  <div className="captured-row captured-white" title="Pieces White has captured">
                    {white.length ? white.map((s, i) => <span key={i} className="piece-sym">{s}</span>) : "—"}
                  </div>
                </div>
              );
            })()}
          </div>
          {!feedback ? (
          <div className="choices choices-four choices-sidebar">
            <button
              className="choice white winning"
              onClick={() => submitGuess("white_winning")}
              title="White winning (1)"
            >
              White winning <span className="range">(1.25–2)</span> <kbd>1</kbd>
            </button>
            <button
              className="choice white better"
              onClick={() => submitGuess("white_better")}
              title="White better (2)"
            >
              White better <span className="range">(0.5–1.25)</span> <kbd>2</kbd>
            </button>
            <button
              className="choice black better"
              onClick={() => submitGuess("black_better")}
              title="Black better (3)"
            >
              Black better <span className="range">(-1.25 to -0.5)</span> <kbd>3</kbd>
            </button>
            <button
              className="choice black winning"
              onClick={() => submitGuess("black_winning")}
              title="Black winning (4)"
            >
              Black winning <span className="range">(-2 to -1.25)</span> <kbd>4</kbd>
            </button>
          </div>
          ) : (
          <div className={`feedback feedback-sidebar ${feedback.correct ? "correct" : "wrong"}`}>
            <p className="result">
              {feedback.correct ? "Correct!" : "Incorrect."}
            </p>
            <p className="actual">
              {evalToHumanReadable(feedback.eval_cp, feedback.actual)}
            </p>
            {feedback.pv_san && (
              <p className="best-line">
                Best line: <span className="pv-san">{feedback.pv_san}</span>
              </p>
            )}
            <button className="next" onClick={loadPosition} title="Next (Enter)">
              Next position <kbd>↵</kbd>
            </button>
          </div>
          )}
        </div>

        <div className="bottom-row">
          {(position?.white || position?.black) ? (
            <div className="game-info">
              {position.white && (
                <span>
                  {position.white}
                  {position.white_elo && ` (${position.white_elo})`}
                </span>
              )}
              {position.white && position.black && <span> vs </span>}
              {position.black && (
                <span>
                  {position.black}
                  {position.black_elo && ` (${position.black_elo})`}
                </span>
              )}
              {(position?.event || position?.date) && (
                <span className="game-meta">
                  {[position.event, position.date].filter(Boolean).join(" · ")}
                </span>
              )}
            </div>
          ) : (
            <div />
          )}
        </div>
        <p className="to-move">
          {position?.fen?.includes(" w ") ? "White" : "Black"} to move
        </p>
      </main>
    </div>
  );
}
