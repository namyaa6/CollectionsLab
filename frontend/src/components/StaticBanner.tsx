import { getMeta } from "../api";
import { useApi } from "../useApi";

const REPO_URL = "https://github.com/namyaa6/CollectionsLab#how-to-run";

/** Static (GitHub Pages) build only: says this is a frozen snapshot, not live data. */
export default function StaticBanner() {
  const { data } = useApi((signal) => getMeta(signal), "meta");
  const date = data?.snapshot_date
    ? new Date(data.snapshot_date).toLocaleDateString("en-US",
      { month: "short", day: "numeric", year: "numeric" })
    : null;
  return (
    <div className="static-banner" role="note">
      Read-only snapshot of results{date ? ` from ${date}` : ""} ·{" "}
      <a href={REPO_URL}>run locally</a> for live data
    </div>
  );
}
