// Shape of GET /api/events (see dashboard/app.py).

export type Action = "allow" | "harder_knock" | "block";

export interface Features {
  hour: number;
  dow: number; // 0 = Monday
  is_known_ip: number; // 0 or 1
  time_since_last: number; // seconds, capped at 7 days
  attempts_last_5min: number;
}

export interface Decision {
  id: number;
  ts: string; // local ISO time, e.g. 2026-11-09T14:03:22+01:00
  ip: string;
  action: Action;
  reason: string; // rule name, or "model"
  score: number | null; // null when a rule decided
  features: Features | null;
}

export interface Bands {
  allow_above: number;
  block_below: number;
}

export interface Normal {
  hour: [number, number];
  time_since_last: [number, number];
  attempts_last_5min: [number, number];
  is_known_ip: boolean;
}

export interface Payload {
  demo: boolean;
  bands: Bands | null;
  normal: Normal | null;
  counts: Record<Action, number>;
  max_id: number; // newest id in the database
  events: Decision[];
}
