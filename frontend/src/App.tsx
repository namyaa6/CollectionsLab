import { useState } from "react";
import CompareScreen from "./components/CompareScreen";
import RunsScreen from "./components/RunsScreen";

type Screen = "runs" | "compare";

export default function App() {
  // State lives here, above both screens, so the selection survives switching tabs.
  const [screen, setScreen] = useState<Screen>("runs");
  const [selected, setSelected] = useState<number[]>([]);

  function toggle(id: number) {
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true" />
            CollectionsLab
          </div>
          <nav className="tabs" aria-label="Screens">
            <button
              className={screen === "runs" ? "tab active" : "tab"}
              onClick={() => setScreen("runs")}
            >
              Runs
            </button>
            <button
              className={screen === "compare" ? "tab active" : "tab"}
              onClick={() => setScreen("compare")}
              disabled={selected.length === 0}
              title={selected.length === 0 ? "Select runs to compare first" : undefined}
            >
              Compare{selected.length > 0 && <span className="count">{selected.length}</span>}
            </button>
          </nav>
        </div>
      </header>

      <main className="page">
        {screen === "runs" ? (
          <RunsScreen
            selected={selected}
            onToggle={toggle}
            onClear={() => setSelected([])}
            onCompare={() => setScreen("compare")}
          />
        ) : (
          <CompareScreen ids={selected} onBack={() => setScreen("runs")} />
        )}
      </main>
    </div>
  );
}
