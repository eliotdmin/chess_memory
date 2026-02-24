import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

class ErrorBoundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error("React error:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: "2rem", fontFamily: "sans-serif", background: "#0f0f12", color: "#e8e6e3", minHeight: "100vh" }}>
          <h1 style={{ color: "#c9a227" }}>Something went wrong</h1>
          <pre style={{ background: "#1e1e24", padding: "1rem", overflow: "auto" }}>{this.state.error.toString()}</pre>
          <p>Check the browser console (F12) for details.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
