// Where a score sits against the model bands. Numbers only on hover, for us.
import type { Action, Bands, Decision } from "../types";
import { ACTION_WORD, fmtScore, isRule } from "../explain";

interface Geometry { min: number; max: number; block: number; allow: number }

export function geometry(b: Bands): Geometry {
  const min = b.block_below - 0.15;
  const max = b.allow_above + 0.3;
  const pct = (v: number) => ((v - min) / (max - min)) * 100;
  return { min, max, block: pct(b.block_below), allow: pct(b.allow_above) };
}

export function scorePct(score: number, g: Geometry): number {
  const v = Math.min(Math.max(score, g.min), g.max);
  return ((v - g.min) / (g.max - g.min)) * 100;
}

/** Hover text with the raw numbers (for the report, not for viewers). */
export function scoreTitle(d: Decision, b: Bands | null): string {
  if (isRule(d) || d.score === null) return `Rule: ${d.reason}`;
  const cuts = b ? ` (allow above ${fmtScore(b.allow_above)}, block below ${fmtScore(b.block_below)})` : "";
  return `Model score ${fmtScore(d.score)}${cuts}`;
}

/** Risk bar: safe on the left, risky on the right, arrow where this attempt fell. */
export function ScoreScale({ d, bands }: { d: Decision; bands: Bands | null }) {
  if (!bands) return null;
  const g = geometry(bands);
  const rule = isRule(d) || d.score === null;
  const zones = [
    { a: "allow" as Action, from: 0, to: 100 - g.allow },
    { a: "harder_knock" as Action, from: 100 - g.allow, to: 100 - g.block },
    { a: "block" as Action, from: 100 - g.block, to: 100 },
  ];
  return (
    <div className={`scale${rule ? " scale--dim" : ""}`} data-act={d.action} title={scoreTitle(d, bands)}>
      <div className="scale__head">
        <span className="eyebrow">Risk</span>
        {rule && <span className="scale__note">Stopped by a safety rule</span>}
      </div>
      <div className="scale__track">
        {zones.map((z) => (
          <span
            key={z.a}
            className={`scale__zone${!rule && z.a === d.action ? " on" : ""}`}
            data-zone={z.a}
            style={{ left: `${z.from}%`, width: `${z.to - z.from}%` }}
          >
            <span className="scale__label">{ACTION_WORD[z.a]}</span>
          </span>
        ))}
        {!rule && d.score !== null && (
          <span className="scale__marker" style={{ left: `${100 - scorePct(d.score, g)}%` }} />
        )}
      </div>
      <div className="scale__ends" aria-hidden="true"><span>Low</span><span>High</span></div>
    </div>
  );
}
