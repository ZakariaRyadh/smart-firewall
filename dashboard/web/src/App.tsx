import { useEffect, useMemo, useState } from "react";
import { useEvents } from "./useEvents";
import { Rail } from "./components/Rail";
import { Ledger, type Filter } from "./components/Ledger";

export function App() {
  const ev = useEvents();
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<number | null>(null); // null = all rows closed

  const rows = useMemo(
    () => (filter === "all" ? ev.log : ev.log.filter((d) => d.action === filter)),
    [ev.log, filter],
  );
  const open = openId !== null && rows.some((d) => d.id === openId) ? openId : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpenId(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="app">
      <Rail
        counts={ev.counts}
        log={ev.log}
        normal={ev.normal}
        demo={ev.demo}
        connected={ev.connected}
        updated={ev.updated}
        anyOpen={open !== null}
        onClose={() => setOpenId(null)}
        onShow={(id) => { setFilter("all"); setOpenId(id); }}
      />
      <Ledger
        rows={rows}
        openId={open}
        fresh={ev.fresh}
        bands={ev.bands}
        normal={ev.normal}
        filter={filter}
        counts={ev.counts}
        loaded={ev.loaded}
        onFilter={(f) => { setFilter(f); setOpenId(null); }}
        onOpen={(id) => setOpenId(id === open ? null : id)}
      />
    </div>
  );
}
