// Result colours and the small square marker (outline, half, solid).
import type { Action } from "../types";

export const TONE_TEXT: Record<Action, string> = { allow: "text-ok", harder_knock: "text-warn", block: "text-bad" };
export const TONE_BG: Record<Action, string> = { allow: "bg-ok", harder_knock: "bg-warn", block: "bg-bad" };

const MARK: Record<Action, string> = {
  allow: "border-ok bg-ok/30",
  harder_knock: "border-warn bg-[linear-gradient(90deg,var(--amber)_50%,transparent_50%)]",
  block: "border-bad bg-bad",
};

export function Mark({ a }: { a: Action }) {
  return <i aria-hidden="true" className={`inline-block size-2.5 flex-none border-[1.5px] ${MARK[a]}`} />;
}
