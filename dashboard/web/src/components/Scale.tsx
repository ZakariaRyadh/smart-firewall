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
  const on = (a: Action) => !rule && a === d.action;
  const zones = [
    { a: "allow" as Action, from: 0, to: 100 - g.allow },
    { a: "harder_knock" as Action, from: 100 - g.allow, to: 100 - g.block },
    { a: "block" as Action, from: 100 - g.block, to: 100 },
  ];
  return (
    <div data-act={d.action} title={scoreTitle(d, bands)} className="flex max-w-[760px] flex-col gap-2.5">
      <div className="flex items-baseline justify-between gap-4">
        <span className="eyebrow">Risk</span>
        {rule && <span className="text-[13px] text-mut">Stopped by a safety rule</span>}
      </div>
      <div className="relative h-[52px]">
        {zones.map((z) => (
          <span
            key={z.a}
            className={`absolute top-[18px] h-2.5 border-r-2 border-panel ${on(z.a) ? "bg-acc" : "bg-track"} ${rule ? "opacity-35" : ""}`}
            style={{ left: `${z.from}%`, width: `${z.to - z.from}%` }}
          >
            <span className={`absolute inset-x-0 top-4 text-center text-[13px] whitespace-nowrap ${on(z.a) ? "font-bold text-acc" : "text-mut"}`}>
              {ACTION_WORD[z.a]}
            </span>
          </span>
        ))}
        {!rule && d.score !== null && (
          <span
            className="absolute top-[3px] size-0 -translate-x-1/2 border-x-8 border-t-[11px] border-x-transparent border-t-acc transition-[left] duration-[600ms] ease-soft"
            style={{ left: `${100 - scorePct(d.score, g)}%` }}
          />
        )}
      </div>
      <div className="-mt-1 flex justify-between text-xs text-mut" aria-hidden="true"><span>Low</span><span>High</span></div>
    </div>
  );
}
