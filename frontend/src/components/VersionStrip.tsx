const STEPS = [
  { version: "v1", text: "basic" },
  { version: "v2", text: "speaks naturally" },
  { version: "v3", text: "checks facts and follows rules" },
  { version: "v4", text: "double-checks itself" },
];

/** The four prompt versions in one line; each adds one thing to the one before. */
export default function VersionStrip() {
  return (
    <ol className="version-strip" aria-label="Prompt versions, each adding to the last">
      {STEPS.map((s) => (
        <li key={s.version}>
          <span className="version">{s.version}</span> {s.text}
        </li>
      ))}
    </ol>
  );
}
