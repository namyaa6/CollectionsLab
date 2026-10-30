// Shared test fixture: run 1, call 3, turn 0, with the voice linter's padded snippets for it.
import { locateSnippet, type Mark } from "./highlight";

export const TURN = "Hello, am I speaking with Mr. Imran Deshpande at Narmada Packaging Pvt Ltd? Good morning, " +
  "Mr. Deshpande. My name is Asha, calling on behalf of Meridian Receivables regarding invoice " +
  "INV-2026-1022 for Narmada Packaging. I'm calling about the outstanding balance of ₹1,70,300 which is " +
  "currently 84 days overdue. How are you today, and when can we expect payment for this balance?";

const LINT_SNIPPETS = [
  "balance of ₹1,70,300 whi", "balance of ₹1,70,300 which is cu", "ing invoice INV-2026-1022 for Narmada",
];

export function lintMarks(): Mark[] {
  return LINT_SNIPPETS.map((s, i) => ({ ...locateSnippet(TURN, s)!, kind: "lint" as const, label: `L${i}` }));
}
