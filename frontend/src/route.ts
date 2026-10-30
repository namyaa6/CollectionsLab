import { useEffect, useState } from "react";

// Hash routes: everything after "#" lives in the browser history, so Back/Forward and refresh
// work with no router library and no server configuration.
export type Route =
  | { name: "runs" }
  | { name: "compare" }
  | { name: "calls"; runId: number }
  | { name: "call"; runId: number; idx: number };

export const href = {
  runs: "#/runs",
  compare: "#/compare",
  calls: (runId: number) => `#/runs/${runId}/calls`,
  call: (runId: number, idx: number) => `#/runs/${runId}/calls/${idx}`,
};

export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "compare") return { name: "compare" };
  if (parts[0] === "runs" && parts[2] === "calls") {
    const runId = Number(parts[1]);
    const idx = Number(parts[3]);
    if (Number.isInteger(runId)) {
      return parts.length > 3 && Number.isInteger(idx) ? { name: "call", runId, idx } : { name: "calls", runId };
    }
  }
  return { name: "runs" };
}

export function navigate(to: string) {
  window.location.hash = to;
}

/** The current route; re-renders whenever the hash changes (link click, Back, typing a URL). */
export function useHashRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange); // unsubscribe on unmount
  }, []);
  return route;
}
