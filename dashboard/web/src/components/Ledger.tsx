// The table of decisions, newest first, with one row open.
import { useEffect } from "react";
import type { Action, Bands, Decision, Normal } from "../types";
import { ACTION_WORD, dateLong, timeOf, whyShort } from "../explain";
import { scoreTitle } from "./Scale";
import { Detail } from "./Detail";

export type Filter = "all" | Action;

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "allow", label: "Allowed" },
  { key: "harder_knock", label: "Extra check" },
  { key: "block", label: "Blocked" },
];

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
    <section className="main">
      <div className="toolbar" role="tablist" aria-label="Filter by verdict">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            role="tab"
            aria-selected={filter === f.key}
            className={`chip${filter === f.key ? " chip--on" : ""}`}
            data-act={f.key}
            onClick={() => onFilter(f.key)}
          >
            {f.label}
            <span className="chip__n">{f.key === "all" ? total : counts[f.key]}</span>
          </button>
        ))}
      </div>

      <div className="thead" aria-hidden="true">
        <span>Time</span><span>Address</span><span>Result</span><span>Why</span>
      </div>

      <ul className="rows">
        {rows.length === 0 && (
          <li className="empty">{loaded ? "Waiting for logins…" : "Connecting…"}</li>
        )}
        {rows.map((d, i) => {
          const open = d.id === openId;
          const newDay = i === 0 || rows[i - 1].ts.slice(0, 10) !== d.ts.slice(0, 10);
          return (
            <li key={d.id} id={`d-${d.id}`} className={`item${open ? " item--open" : ""}${fresh.has(d.id) ? " item--new" : ""}`} data-act={d.action}>
              {newDay && (
                <div className="day">
                  <span className="day__name">{dateLong(d)}</span>
                  <span className="day__n">{perDay.get(d.ts.slice(0, 10))} logins</span>
                </div>
              )}
              <button type="button" className="row" aria-expanded={open} title={scoreTitle(d, bands)} onClick={() => onOpen(d.id)}>
                <span className="row__t mono">{timeOf(d)}</span>
                <span className="row__ip mono">{d.ip}</span>
                <span className="row__v"><i className="mk" data-act={d.action} />{ACTION_WORD[d.action]}</span>
                <span className="row__y">{whyShort(d, normal)}</span>
              </button>
              {open && <Detail d={d} bands={bands} normal={normal} />}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
