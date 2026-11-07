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

function TileView({ t }: { t: Tile }) {
  return (
    <div className={`tile${t.out ? " tile--out" : ""}`}>
      <span className="eyebrow">{t.label}</span>
      <span className="tile__value">{t.value}</span>
      <span className="tile__usual">{t.out ? "⚠ Unusual" : "✓ Normal"}</span>
    </div>
  );
}

export function Detail({ d, bands, normal }: { d: Decision; bands: Bands | null; normal: Normal | null }) {
  return (
    <div className="detail" data-act={d.action}>
      <p className="detail__why">{why(d, normal)}</p>
      <ScoreScale d={d} bands={bands} />
      {d.features && normal && (
        <div className="tiles">
          <span className="eyebrow tiles__title">Details</span>
          {tiles(d.features, normal, d.ts).map((t) => <TileView key={t.label} t={t} />)}
        </div>
      )}
    </div>
  );
}
