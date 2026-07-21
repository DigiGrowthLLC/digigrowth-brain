import React from "react";

// Without this, any uncaught render-time error (e.g. a third-party SDK
// callback throwing) unmounts the whole app to a blank white screen with no
// indication of what happened. This at least shows the error so it's
// diagnosable, and offers a reload instead of a dead tab.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Uncaught error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          height: "100vh", display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 12,
          background: "#090f26", color: "#f0f4ff", fontFamily: "'Space Grotesk', sans-serif",
          padding: 24, textAlign: "center",
        }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Something went wrong</div>
          <div style={{
            fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#8aaad0",
            maxWidth: 520, whiteSpace: "pre-wrap",
          }}>
            {this.state.error.message || String(this.state.error)}
          </div>
          <button onClick={() => window.location.reload()} style={{
            marginTop: 8, padding: "10px 24px", borderRadius: 8, fontSize: 13, fontWeight: 700,
            background: "rgba(58,123,213,0.15)", color: "#5a9bf0",
            border: "1px solid rgba(58,123,213,0.35)", cursor: "pointer",
          }}>Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}
