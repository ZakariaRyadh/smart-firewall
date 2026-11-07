// Expanded view of one decision: the sentence, where it fell, and the attempt vs normal use.
import type { Bands, Decision, Features, Normal } from "../types";
import { CAP_SECONDS, fmtGap, why } from "../explain";
import { ScoreScale } from "./Scale";

interface Tile { label: string; value: string; out: boolean }

function tiles(f: Features, n: Normal, ts: string): Tile[] {
  const gap = f.time_since_last;
  return [
    { label: "Time", value: ts.slice(11, 16), out: f.hour < n.hour[0] || f.hour > n.hour[1] },
    { label: "Address", value: f.is_known_ip ? "Known" : "New", out: !f.is_known_ip && n.is_known_ip },
    {
      label: "Last login", value: gap >= CAP_SECONDS ? "Never" : `${fmtGap(gap)} ago`,
      out: gap < n.time_since_last[0] || (gap > n.time_since_last[1] && gap < CAP_SECONDS),
    },
    { label: "Tries in 5 min", value: String(f.attempts_last_5min + 1), out: f.attempts_last_5min > n.attempts_last_5min[1] },
  ];
}

function TileView({ t, allow }: { t: Tile; allow: boolean }) {
  // On an allowed login an unusual value is a warning, not a failure.
  const tone = allow ? "text-warn" : "text-acc";
  return (
    <div className="flex min-w-0 flex-col gap-[7px]">
      <span className="eyebrow">{t.label}</span>
      <span className={`font-mono text-[clamp(18px,2.8vh,26px)] leading-none font-bold ${t.out ? tone : "text-soft"}`}>{t.value}</span>
      <span className={`text-[13px] ${t.out ? `font-semibold ${tone}` : "text-mut"}`}>{t.out ? "⚠ Unusual" : "✓ Normal"}</span>
    </div>
  );
}

export function Detail({ d, bands, normal }: { d: Decision; bands: Bands | null; normal: Normal | null }) {
  const allow = d.action === "allow";
  return (
    <div
      data-act={d.action}
      className="flex animate-fade flex-col gap-[clamp(14px,2.6vh,26px)] border-t border-rule bg-panel pt-[clamp(16px,3vh,30px)] pr-8 pb-[clamp(18px,3.2vh,32px)] pl-9 max-lg:p-4"
    >
      <p className={`max-w-[30em] font-serif text-[clamp(22px,3.6vh,38px)] leading-[1.16] tracking-[-0.015em] ${allow ? "" : "text-acc"}`}>
        {why(d, normal)}
      </p>
      <ScoreScale d={d} bands={bands} />
      {d.features && normal && (
        <div className="grid grid-cols-4 gap-x-[22px] gap-y-3 border-t border-ink pt-3 max-lg:grid-cols-2">
          <span className="eyebrow col-span-full">Details</span>
          {tiles(d.features, normal, d.ts).map((t) => <TileView key={t.label} t={t} allow={allow} />)}
        </div>
      )}
    </div>
  );
}
