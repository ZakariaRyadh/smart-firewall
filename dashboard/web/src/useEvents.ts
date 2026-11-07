// Polls /api/events and keeps the newest decisions in memory.
import { useEffect, useRef, useState } from "react";
import type { Action, Bands, Decision, Normal, Payload } from "./types";

const POLL_MS = 1500;
const RETRY_MS = 4000;
const KEEP = 300; // decisions kept in the page
const FRESH_MS = 1600; // how long a new row stays highlighted

export interface EventsState {
  log: Decision[]; // newest first
  counts: Record<Action, number>;
  bands: Bands | null;
  normal: Normal | null;
  demo: boolean;
  connected: boolean;
  loaded: boolean;
  updated: Date | null;
  fresh: Set<number>;
}

const EMPTY: EventsState = {
  log: [], counts: { allow: 0, harder_knock: 0, block: 0 }, bands: null, normal: null,
  demo: false, connected: true, loaded: false, updated: null, fresh: new Set(),
};

async function fetchEvents(after: number, signal: AbortSignal): Promise<Payload> {
  const limit = after === 0 ? 200 : 500;
  const r = await fetch(`/api/events?after=${after}&limit=${limit}`, { cache: "no-store", signal });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export function useEvents(): EventsState {
  const [state, setState] = useState<EventsState>(EMPTY);
  const lastId = useRef(0);

  useEffect(() => {
    let timer: number | undefined;
    let alive = true;
    const ctrl = new AbortController();

    async function tick() {
      let wait = POLL_MS;
      try {
        let data = await fetchEvents(lastId.current, ctrl.signal);
        let reset = lastId.current === 0;
        if (data.max_id < lastId.current) {
          // the database was rebuilt (ids restarted): load it again from scratch
          lastId.current = 0;
          reset = true;
          data = await fetchEvents(0, ctrl.signal);
        }
        if (!alive) return;
        const ids = data.events.map((e) => e.id);
        if (ids.length) lastId.current = ids[ids.length - 1];
        const incoming = [...data.events].reverse(); // API sends oldest first
        setState((s) => ({
          log: [...incoming, ...(reset ? [] : s.log)].slice(0, KEEP),
          counts: data.counts,
          bands: data.bands,
          normal: data.normal,
          demo: data.demo,
          connected: true,
          loaded: true,
          updated: new Date(),
          fresh: reset ? new Set() : new Set(ids),
        }));
        if (!reset && ids.length)
          window.setTimeout(() => alive && setState((s) => ({ ...s, fresh: new Set() })), FRESH_MS);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        wait = RETRY_MS;
        if (alive) setState((s) => ({ ...s, connected: false, loaded: true }));
      }
      if (alive) timer = window.setTimeout(tick, wait);
    }

    tick();
    return () => {
      alive = false;
      ctrl.abort();
      window.clearTimeout(timer);
    };
  }, []);

  return state;
}
