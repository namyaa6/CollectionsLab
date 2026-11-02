import { useState } from "react";
import CallScreen from "./components/CallScreen";
import CallsScreen from "./components/CallsScreen";
import CompareScreen from "./components/CompareScreen";
import Footer from "./components/Footer";
import "./components/Landing.css";
import RunsScreen from "./components/RunsScreen";
import StaticBanner from "./components/StaticBanner";
import { href, navigate, useHashRoute } from "./route";
import { IS_STATIC } from "./staticApi";

export default function App() {
  // The URL hash says which screen is open; selection lives here, above every screen,
  // so it survives moving between them.
  const route = useHashRoute();
  const [selected, setSelected] = useState<number[]>([]);
  const [showAllJudges, setShowAllJudges] = useState(false);

  function toggle(id: number) {
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function compareRuns(ids: number[]) {
    setSelected(ids);
    navigate(href.compare);
  }

  const runsTabActive = route.name !== "compare";

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true" />
            CollectionsLab
          </div>
          <nav className="tabs" aria-label="Screens">
            <a className={runsTabActive ? "tab active" : "tab"} href={href.runs}>
              Runs
            </a>
            <button
              className={route.name === "compare" ? "tab active" : "tab"}
              onClick={() => navigate(href.compare)}
              disabled={selected.length === 0}
              title={selected.length === 0 ? "Select runs to compare first" : undefined}
            >
              Compare{selected.length > 0 && <span className="count">{selected.length}</span>}
            </button>
          </nav>
        </div>
      </header>
      {IS_STATIC && <StaticBanner />}

      <main className="page">
        {route.name === "runs" && (
          <RunsScreen
            selected={selected}
            onToggle={toggle}
            onClear={() => setSelected([])}
            onCompare={() => navigate(href.compare)}
            onCompareRuns={compareRuns}
          />
        )}
        {route.name === "compare" &&
          (selected.length > 0 ? (
            <CompareScreen ids={selected} onBack={() => navigate(href.runs)} />
          ) : (
            <div className="panel status">
              No runs selected. <a href={href.runs}>Pick runs to compare</a>.
            </div>
          ))}
        {route.name === "calls" && <CallsScreen key={route.runId} runId={route.runId} />}
        {route.name === "call" && (
          <CallScreen
            key={`${route.runId}/${route.idx}`}
            runId={route.runId}
            idx={route.idx}
            showAllJudges={showAllJudges}
            onToggleAllJudges={setShowAllJudges}
          />
        )}
      </main>
      <Footer />
    </div>
  );
}
