/** The API's comparability warnings, shown verbatim above the charts. */
export default function Warnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <div className="warnings" role="alert">
      <svg className="warn-icon" viewBox="0 0 20 20" aria-hidden="true">
        <path d="M10 2.5 18.5 17h-17L10 2.5Z" fill="none" stroke="currentColor" strokeWidth="1.6"
          strokeLinejoin="round" />
        <path d="M10 8v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="10" cy="14.4" r="0.9" fill="currentColor" />
      </svg>
      <div>
        <strong>Read these results with care</strong>
        <ul>
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
