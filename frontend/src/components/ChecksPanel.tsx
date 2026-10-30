import type { CallSummary, Checks } from "../callTypes";
import { words } from "../format";
import { scrollToTurn } from "./TranscriptView";

function inr(n: number | null | undefined): string {
  return n == null ? "—" : `₹${n.toLocaleString("en-IN")}`;
}

function SummaryCard({ summary }: { summary: CallSummary | null }) {
  return (
    <div className="panel side-card">
      <div className="card-head"><h3>Summary record</h3></div>
      {!summary ? (
        <p className="muted small">No summary stored.</p>
      ) : (
        <>
          <dl className="kv">
            <dt>Outcome</dt><dd>{words(summary.outcome)}</dd>
            <dt>Promise date</dt><dd>{summary.promise_date ?? "—"}</dd>
            <dt>Amount</dt><dd>{inr(summary.amount_inr)}</dd>
            {summary.installment_plan && (
              <>
                <dt>Installments</dt>
                <dd>{summary.installment_plan.map((p) => `${inr(p.amount_inr)} on ${p.date}`).join(", ")}</dd>
              </>
            )}
            {summary.payment_claim && (
              <>
                <dt>Payment claim</dt>
                <dd>{inr(summary.payment_claim.amount_inr)} on {summary.payment_claim.date} · UTR {summary.payment_claim.utr}</dd>
              </>
            )}
            {summary.dispute_reason && <><dt>Dispute</dt><dd>{summary.dispute_reason}</dd></>}
            <dt>Escalated</dt><dd>{summary.escalated ? "Yes" : "No"}</dd>
            <dt>Next action</dt><dd>{summary.next_action ?? "—"}</dd>
          </dl>
          {summary.discrepancies.length > 0 && (
            <div className="discrepancies">
              <div className="sc-label">Discrepancies</div>
              <ul>{summary.discrepancies.map((d, i) => <li key={i}>{d}</li>)}</ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FactsCard({ checks }: { checks: Checks }) {
  const { facts } = checks;
  return (
    <div className="panel side-card">
      <div className="card-head">
        <h3>Fact check</h3>
        <span className="hint">{facts.matched} matched · {facts.unverified} unverified</span>
      </div>
      {facts.items.length === 0 ? (
        <p className="muted small">The agent stated no amounts, dates or day counts.</p>
      ) : (
        <ul className="fact-list">
          {facts.items.map((f, i) => (
            <li key={i}>
              <button className="turn-link mono" onClick={() => scrollToTurn(f.turn)}>#{f.turn}</button>
              <span className="muted">{f.kind}</span>
              <span className="fact-snippet">{f.snippet}</span>
              <span className={f.status === "matched" ? "chip chip-good" : "chip chip-bad"}>{f.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PolicyCard({ checks }: { checks: Checks }) {
  const v = checks.policy_violations;
  return (
    <div className="panel side-card">
      <div className="card-head">
        <h3>Policy check</h3>
        <span className="hint">{v.length === 0 ? "no violations" : `${v.length} violation${v.length > 1 ? "s" : ""}`}</span>
      </div>
      {v.length > 0 && (
        <ul className="policy-list">
          {v.map((p, i) => (
            <li key={i}><span className="chip chip-bad">{words(p.rule)}</span> {p.detail}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ChecksPanel({ checks, summary }: { checks: Checks | null; summary: CallSummary | null }) {
  return (
    <>
      {checks ? (
        <>
          <FactsCard checks={checks} />
          <PolicyCard checks={checks} />
        </>
      ) : (
        <div className="panel side-card"><p className="muted small">No code checks stored for this call.</p></div>
      )}
      <SummaryCard summary={summary} />
    </>
  );
}
