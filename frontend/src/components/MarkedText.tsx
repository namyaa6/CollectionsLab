import { buildSegments, type Mark } from "../highlight";

/** Turn text with highlights. Segments are rendered back to back with no separators, so the
 *  visible text is exactly `text` (marks also have no horizontal padding in Transcript.css). */
export default function MarkedText({ text, marks }: { text: string; marks: Mark[] }) {
  return (
    <>
      {buildSegments(text, marks).map((s, k) =>
        s.mark ? <mark key={k} className={`m-${s.mark.kind}`} title={s.mark.label}>{s.text}</mark> : s.text,
      )}
    </>
  );
}
