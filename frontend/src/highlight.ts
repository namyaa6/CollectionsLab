// Locating judge quotes, lint snippets and fact snippets inside turn text, and splitting
// the text into plain and marked segments for rendering.

/**
 * Same normalization as backend/eval/judge.py _norm (lowercase, punctuation -> space,
 * collapse whitespace, trim), plus map[k] = index in `text` of normalized char k,
 * so a match in the normalized string can be mapped back onto the original text.
 */
export function normalizeWithMap(text: string): { norm: string; map: number[] } {
  let norm = "";
  const map: number[] = [];
  for (let i = 0; i < text.length; i++) {
    const lower = text[i].toLowerCase();
    const ch = lower.length === 1 ? lower : text[i];
    const isWord = /[\p{L}\p{N}_]/u.test(ch);
    if (isWord) {
      norm += ch;
      map.push(i);
    } else if (norm.length > 0 && !norm.endsWith(" ")) {
      norm += " ";
      map.push(i);
    }
  }
  if (norm.endsWith(" ")) {
    norm = norm.slice(0, -1);
    map.pop();
  }
  return { norm, map };
}

export interface QuoteLocation {
  turn: number;
  start: number;
  end: number;
}

// The judge reads lines like "[4] AGENT: text", so a quote sometimes starts with that prefix.
const SPEAKER_PREFIX = /^\s*(\[\d+\]\s*)?(agent|debtor)\s*:\s*/i;

/** First turn whose text contains the quote (judge-style matching); null if empty or not
 *  found inside a single turn (e.g. the quote spans two turns or quotes a tool line). */
export function findQuote(texts: string[], quote: string): QuoteLocation | null {
  const target = normalizeWithMap(quote.replace(SPEAKER_PREFIX, "")).norm;
  if (!target) return null;
  for (let turn = 0; turn < texts.length; turn++) {
    const { norm, map } = normalizeWithMap(texts[turn]);
    const pos = norm.indexOf(target);
    if (pos >= 0) {
      return { turn, start: map[pos], end: map[pos + target.length - 1] + 1 };
    }
  }
  return null;
}

export interface ToolQuoteLocation {
  turn: number;
  tool: number;
}

interface ToolCallLike {
  tool: string;
  args: unknown;
  result: unknown;
}

/** A tool call as the judge saw it (backend/eval/judge.py render_for_judge). JSON spacing differs
 *  from Python's json.dumps, but normalization turns all punctuation into single spaces anyway. */
export function toolLine(c: ToolCallLike): string {
  return `${c.tool}(${JSON.stringify(c.args)}) -> ${JSON.stringify(c.result)}`;
}

/** First tool call whose rendered line contains the quote; null when none does. */
export function findToolQuote(toolCalls: ToolCallLike[][], quote: string): ToolQuoteLocation | null {
  const target = normalizeWithMap(quote.replace(SPEAKER_PREFIX, "")).norm;
  if (!target) return null;
  for (let turn = 0; turn < toolCalls.length; turn++) {
    const tool = toolCalls[turn].findIndex((c) => normalizeWithMap(toolLine(c)).norm.includes(target));
    if (tool >= 0) return { turn, tool };
  }
  return null;
}

/** Exact snippet position (the backend replaces newlines with spaces and trims); null if absent. */
export function locateSnippet(text: string, snippet: string): { start: number; end: number } | null {
  const s = snippet.trim();
  if (!s) return null;
  const pos = text.replace(/\n/g, " ").indexOf(s);
  return pos < 0 ? null : { start: pos, end: pos + s.length };
}

export type MarkKind = "quote" | "lint" | "fact";
export interface Mark {
  start: number;
  end: number;
  kind: MarkKind;
  label: string;
}
export interface Segment {
  text: string;
  mark: Mark | null;
}

const PRIORITY: Record<MarkKind, number> = { quote: 3, lint: 2, fact: 1 };

const isWord = (c: string | undefined) => c !== undefined && /[\p{L}\p{N}_]/u.test(c);
const isSpace = (c: string | undefined) => c !== undefined && /\s/.test(c);

/**
 * Lint snippets carry +-12 chars of context, so they often start or end inside a word
 * ("regard|ing invoice"). Drop a partial word at either edge and trim whitespace; if that
 * leaves nothing, widen the range to the whole words it touches instead.
 */
export function snapToWords(text: string, start: number, end: number): { start: number; end: number } {
  let s = Math.max(0, start);
  let e = Math.min(text.length, end);
  if (isWord(text[s - 1]) && isWord(text[s])) while (s < e && isWord(text[s])) s++;
  if (isWord(text[e - 1]) && isWord(text[e])) while (e > s && isWord(text[e - 1])) e--;
  while (s < e && isSpace(text[s])) s++;
  while (e > s && isSpace(text[e - 1])) e--;
  if (s < e) return { start: s, end: e };
  s = Math.max(0, start);
  e = Math.min(text.length, end);
  while (s > 0 && isWord(text[s - 1])) s--;
  while (e < text.length && isWord(text[e])) e++;
  return { start: s, end: e };
}

/** Snap every mark, then merge marks of the same kind that overlap or are separated only by
 *  whitespace, so one highlight is never split into several elements. */
export function prepareMarks(text: string, marks: Mark[]): Mark[] {
  const snapped = marks
    .map((m) => ({ ...m, ...snapToWords(text, m.start, m.end) }))
    .filter((m) => m.start < m.end)
    .sort((a, b) => a.kind.localeCompare(b.kind) || a.start - b.start);
  const out: Mark[] = [];
  for (const m of snapped) {
    const last = out[out.length - 1];
    const touching = last && last.kind === m.kind && text.slice(last.end, m.start).trim() === "";
    if (last && touching) {
      last.end = Math.max(last.end, m.end);
      if (!last.label.split(" · ").includes(m.label)) last.label += ` · ${m.label}`;
    } else {
      out.push({ ...m });
    }
  }
  return out;
}

/** Where marks of different kinds overlap, each character takes the highest-priority mark.
 *  The segments' texts always join back to exactly `text`: nothing is added or dropped. */
export function buildSegments(text: string, marks: Mark[]): Segment[] {
  const owner: (Mark | null)[] = Array.from({ length: text.length }, () => null);
  for (const m of prepareMarks(text, marks)) {
    for (let i = Math.max(0, m.start); i < Math.min(text.length, m.end); i++) {
      const cur = owner[i];
      if (!cur || PRIORITY[m.kind] > PRIORITY[cur.kind]) owner[i] = m;
    }
  }
  const out: Segment[] = [];
  for (let i = 0; i < text.length; i++) {
    const last = out[out.length - 1];
    if (last && last.mark === owner[i]) last.text += text[i];
    else out.push({ text: text[i], mark: owner[i] });
  }
  return out;
}
