// App.tsx — the root component: the app "shell".
//
// The shell is everything that stays put while you move around the app:
// the header, the bottom tab bar, and the health indicator. The middle
// area swaps between the three screens (Today / Goals / History).
//
// Navigation approach: a piece of React state holds which tab is active,
// and we render the matching screen component. For a three-tab app this is
// simpler and more instructive than pulling in a routing library; if we
// ever need shareable URLs per screen, react-router can replace it.

import { useEffect, useState } from "react";
import { fetchHealth } from "./api";
import Today from "./screens/Today";
import Goals from "./screens/Goals";
import History from "./screens/History";

// The three possible tabs, as a TypeScript union type: the compiler now
// guarantees `tab` can never hold anything except these three strings.
type Tab = "today" | "goals" | "history";

function App() {
  // useState = give this component a piece of memory that survives
  // re-renders. Changing it (setTab) makes React re-draw the component.
  const [tab, setTab] = useState<Tab>("today"); // the app opens on Today

  // Backend connectivity: "checking" until the health call answers.
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");

  // useEffect = run side-effect code after the component appears on screen.
  // The empty [] dependency list means "run once on mount", not on every
  // re-render — without it, we'd ping /health in an infinite loop.
  useEffect(() => {
    fetchHealth()
      .then(() => setApiStatus("ok"))
      .catch(() => setApiStatus("down")); // network error or non-200 answer
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>🥗 Calorie Tracker</h1>
        {/* Tiny status dot: green = backend reachable, red = not.
            title= shows an explanation when hovering / long-pressing. */}
        <span
          className={`status-dot ${apiStatus}`}
          title={
            apiStatus === "ok"
              ? "Backend connected"
              : apiStatus === "down"
                ? "Backend unreachable — is the API server running?"
                : "Checking backend…"
          }
        />
      </header>

      {/* The screen area. Only the active tab's component is rendered. */}
      <main className="app-content">
        {tab === "today" && <Today />}
        {tab === "goals" && <Goals />}
        {tab === "history" && <History />}
      </main>

      {/* Bottom tab bar — bottom because that's where thumbs are on a
          phone. aria-current tells screen readers (and our CSS) which tab
          is active. */}
      <nav className="tab-bar">
        <button
          type="button"
          aria-current={tab === "today"}
          onClick={() => setTab("today")}
        >
          📋 Today
        </button>
        <button
          type="button"
          aria-current={tab === "goals"}
          onClick={() => setTab("goals")}
        >
          🎯 Goals
        </button>
        <button
          type="button"
          aria-current={tab === "history"}
          onClick={() => setTab("history")}
        >
          📈 History
        </button>
      </nav>
    </div>
  );
}

export default App;
