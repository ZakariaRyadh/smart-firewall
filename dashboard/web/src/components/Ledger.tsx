// The table of decisions, newest first, with one row open.
import { useEffect } from "react";
import type { Action, Bands, Decision, Normal } from "../types";
import { ACTION_WORD, dateLong, timeOf, whyShort } from "../explain";
import { scoreTitle } from "./Scale";
import { Detail } from "./Detail";
import { Mark } from "./Mark";

export type Filter = "all" | Action;

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "allow", label: "Allowed" },
  { key: "harder_knock", label: "Extra check" },
  { key: "block", label: "Blocked" },
];

const CHIP_ON: Record<Filter, string> = {
  all: "border-ink text-ink",
  allow: "border-ok text-ok",
  harder_knock: "border-warn text-warn",
  block: "border-bad text-bad",
};

// Same columns for the header and every row.
const GRID = "grid items-center gap-[18px] grid-cols-[5.6em_9.6em_8.6em_minmax(0,1fr)]";

// Left edge and tint per result (an open row gets bg-panel instead of the tint).
const ROW_EDGE: Record<Action, string> = {
  allow: "border-l-transparent",
  harder_knock: "border-l-warn",
  block: "border-l-bad",
};
const ROW_TINT: Record<Action, string> = { allow: "", harder_knock: "bg-warn/[0.06]", block: "bg-bad/[0.06]" };

interface Props {
  rows: Decision[];
  openId: number | null;
  fresh: Set<number>;
  bands: Bands | null;
  normal: Normal | null;
  filter: Filter;
  counts: Record<Action, number>;
  loaded: boolean;
  onFilter: (f: Filter) => void;
  onOpen: (id: number) => void;
}

export function Ledger({ rows, openId, fresh, bands, normal, filter, counts, loaded, onFilter, onOpen }: Props) {
  const total = counts.allow + counts.harder_knock + counts.block;
  const perDay = new Map<string, number>();
  for (const d of rows) perDay.set(d.ts.slice(0, 10), (perDay.get(d.ts.slice(0, 10)) ?? 0) + 1);
  // Bring the opened row into view (also when opened from the "Last blocked" card).
  useEffect(() => {
    if (openId !== null) document.getElementById(`d-${openId}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [openId]);

  return (
    <section className="flex min-h-0 min-w-0 flex-col">
      <div className="flex flex-none flex-wrap items-center gap-2 border-b border-rule px-8 py-3.5 max-lg:px-4" role="tablist" aria-label="Filter by result">
        {FILTERS.map((f) => {
          const on = filter === f.key;
          return (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => onFilter(f.key)}
              className={`inline-flex items-center gap-2 border px-3 py-1.5 text-sm transition-colors ${
                on ? `bg-raise ${CHIP_ON[f.key]}` : "border-rule text-soft hover:border-band"
              }`}
            >
              {f.label}
              <span className="font-mono text-xs leading-none text-mut">{f.key === "all" ? total : counts[f.key]}</span>
            </button>
          );
        })}
      </div>

      <div className={`${GRID} h-10 flex-none border-b border-ink pr-8 pl-9 text-[11px] tracking-[0.14em] text-mut uppercase max-lg:hidden`} aria-hidden="true">
        <span>Time</span><span>Address</span><span>Result</span><span>Why</span>
      </div>

      <ul className="flex-1 overflow-y-auto [scrollbar-color:var(--band)_transparent] [scrollbar-width:thin]">
        {rows.length === 0 && (
          <li className="px-9 py-10 font-serif text-xl text-mut">{loaded ? "Waiting for logins…" : "Connecting…"}</li>
        )}
        {rows.map((d, i) => {
          const open = d.id === openId;
          const isNew = fresh.has(d.id);
          const day = d.ts.slice(0, 10);
          const newDay = i === 0 || rows[i - 1].ts.slice(0, 10) !== day;
          return (
            <li key={d.id} id={`d-${d.id}`} data-act={d.action} className={`border-b border-rule ${isNew ? "animate-arrive" : ""}`}>
              {newDay && (
                <div className="sticky top-0 z-10 flex items-baseline justify-between gap-4 border-t border-b border-t-ink border-b-rule bg-bg pt-[18px] pr-8 pb-2.5 pl-9 max-lg:px-4">
                  <span className="font-serif text-lg leading-[1.2] font-bold">{dateLong(d)}</span>
                  <span className="text-[13px] text-mut">{perDay.get(day)} logins</span>
                </div>
              )}
              <button
                type="button"
                aria-expanded={open}
                title={scoreTitle(d, bands)}
                onClick={() => onOpen(d.id)}
                className={`${GRID} min-h-[clamp(40px,5.4vh,50px)] w-full border-l-4 px-8 text-left transition-colors hover:bg-hover max-lg:grid-cols-[5.2em_minmax(0,1fr)_auto] max-lg:px-4 max-lg:py-2.5 ${
                  ROW_EDGE[d.action]
                } ${open ? "bg-panel" : ROW_TINT[d.action]} ${
                  isNew ? "shadow-[inset_0_0_0_9999px_color-mix(in_srgb,var(--acc)_10%,transparent)]" : ""
                }`}
              >
                <span className="font-mono text-sm text-mut tabular-nums">{timeOf(d)}</span>
                <span className="font-mono text-[15px]">{d.ip}</span>
                <span className={`flex items-center gap-[9px] font-serif text-[17px] leading-[1.1] text-acc ${d.action === "allow" ? "font-normal" : "font-bold"}`}>
                  <Mark a={d.action} />{ACTION_WORD[d.action]}
                </span>
                <span className="truncate text-[15px] text-soft max-lg:hidden">{whyShort(d, normal)}</span>
              </button>
              {open && <Detail d={d} bands={bands} normal={normal} />}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
