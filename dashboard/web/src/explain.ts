// Turns a decision into plain words anyone can read.
import type { Action, Decision, Normal } from "./types";

export const CAP_SECONDS = 604800; // same 7-day cap as sfw/features.py

// "harder_knock" in the code. Shown as "Extra check" so non-technical viewers get it.
export const ACTION_WORD: Record<Action, string> = {
  allow: "Allowed",
  harder_knock: "Extra check",
  block: "Blocked",
};

export const ACTION_HELP: Record<Action, string> = {
  allow: "Looked like normal use, let in",
  harder_knock: "A bit odd, asked for a longer knock",
  block: "Looked like an attack, kept out",
};

// Kept in sync with sfw/rules.py thresholds.
export const RULE_TEXT: Record<string, string> = {
  rate_1min: "more than 5 tries in 1 minute",
  rate_5min: "more than 15 tries in 5 minutes",
  bad_knock_x3: "3 wrong knocks in a row",
  too_fast: "tries less than 1 second apart",
  hard_knock: "passed the longer knock after an extra check",
};

export const isRule = (d: Decision) => d.score === null;

export const pad = (n: number) => String(n).padStart(2, "0");

export function fmtScore(s: number | null): string {
  return s === null ? "—" : s.toFixed(2).replace("-", "−");
}

export function fmtGap(s: number): string {
  if (s >= CAP_SECONDS) return "first time";
  if (s < 60) return `${s < 10 ? s.toFixed(1) : Math.round(s)} s`;
  if (s < 3600) return `${Math.round(s / 60)} min`;
  if (s < 86400) return `${(s / 3600).toFixed(1).replace(".0", "")} h`;
  return `${Math.round(s / 86400)} days`;
}

export const timeOf = (d: Decision) => d.ts.slice(11, 19);

const dayOf = (d: Decision) => {
  const [y, m, day] = d.ts.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, day);
};

/** "Friday 20 November 2026", with "Today" / "Yesterday" in front when it fits. */
export function dateLong(d: Decision, year = true): string {
  const day = dayOf(d);
  const text = day.toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", ...(year ? { year: "numeric" } : {}),
  });
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const diff = Math.round((today - day.getTime()) / 86400000);
  return diff === 0 ? `Today · ${text}` : diff === 1 ? `Yesterday · ${text}` : text;
}

/** What made this attempt different from normal use, in a few words each. */
export function oddities(d: Decision, n: Normal | null): string[] {
  const f = d.features;
  if (!f || !n) return [];
  const out: string[] = [];
  if (f.hour < n.hour[0] || f.hour > n.hour[1]) out.push("Unusual hour");
  if (!f.is_known_ip && n.is_known_ip) out.push("New address");
  if (f.attempts_last_5min > n.attempts_last_5min[1]) out.push(`${f.attempts_last_5min + 1} tries in 5 min`);
  if (f.time_since_last < n.time_since_last[0]) out.push("Too fast");
  else if (f.time_since_last > n.time_since_last[1] && f.time_since_last < CAP_SECONDS) out.push("Long silence");
  return out;
}

const joinList = (a: string[]) =>
  a.length < 2 ? a.join("") : `${a.slice(0, -1).join(", ")} and ${a[a.length - 1]}`;

/** One short sentence for the detail panel. */
export function why(d: Decision, n: Normal | null): string {
  if (isRule(d)) return `${ACTION_WORD[d.action]}: ${RULE_TEXT[d.reason] ?? d.reason}.`;
  const o = oddities(d, n).map((x) => x.toLowerCase());
  if (d.action === "allow")
    return o.length ? `Allowed, but ${joinList(o)}.` : "Normal login. Nothing unusual.";
  return o.length
    ? `${ACTION_WORD[d.action]}: ${joinList(o)}.`
    : `${ACTION_WORD[d.action]}: this does not look like the usual logins.`;
}

/** A few words for the table. */
export function whyShort(d: Decision, n: Normal | null): string {
  if (isRule(d)) return `Rule: ${RULE_TEXT[d.reason] ?? d.reason}`;
  const o = oddities(d, n);
  return o.length ? o.join(" · ") : "Normal login";
}
