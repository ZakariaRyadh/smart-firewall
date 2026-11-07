"""Read-only dashboard. Run from the repo root:

    python -m dashboard.app                         # data/demo.db, port 8000
    SFW_DB=/var/lib/sfw/state.db python -m dashboard.app

Listens on 127.0.0.1 only. On the Pi, view it through an SSH tunnel:
    ssh -L 8000:localhost:8000 zakaria@<pi>

The page is built from dashboard/web (npm run build) into dashboard/web/dist.
"""
import os
from datetime import datetime
from pathlib import Path

import joblib
from flask import Flask, jsonify, request, send_from_directory

from sfw.state import connect_readonly, decision_counts, get_meta, recent_decisions

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = os.environ.get("SFW_DB", str(ROOT / "data" / "demo.db"))
MODEL_PATH = os.environ.get("SFW_MODEL", str(ROOT / "models" / "model.joblib"))
DIST = Path(__file__).resolve().parent / "web" / "dist"
MAX_LIMIT = 500

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
       "frame-ancestors 'none'; form-action 'none'")


def load_bands():
    """Bands and usual ranges from the model bundle, so the page matches the model."""
    try:
        b = joblib.load(MODEL_PATH)
    except (OSError, EOFError):
        return None, None
    return {"allow_above": float(b["p5"]), "block_below": float(b["lowest"])}, b.get("normal")


BANDS, NORMAL = load_bands()
app = Flask(__name__, static_folder=None)


@app.after_request
def security_headers(resp):
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def iso(ts):
    """Epoch seconds to local ISO time, e.g. 2026-11-09T14:03:22+01:00."""
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


@app.get("/api/events")
def events():
    after = request.args.get("after", default=0, type=int)
    limit = min(max(request.args.get("limit", default=200, type=int), 1), MAX_LIMIT)
    try:
        db = connect_readonly(DB_PATH)
    except Exception:
        return jsonify({"error": "no database yet"}), 503
    try:
        rows = recent_decisions(db, after_id=max(after, 0), limit=limit)
        counts = decision_counts(db)
        max_id = db.execute("SELECT COALESCE(MAX(id), 0) FROM decisions").fetchone()[0]
        demo = get_meta(db, "demo") == "1"
    except Exception:
        return jsonify({"error": "database not ready"}), 503
    finally:
        db.close()
    for r in rows:
        r["ts"] = iso(r["ts"])
    return jsonify({
        "demo": demo,
        "bands": BANDS,
        "normal": NORMAL,
        "counts": {k: counts.get(k, 0) for k in ("allow", "harder_knock", "block")},
        "max_id": max_id,
        "events": rows,
    })


@app.get("/")
def index():
    return send_from_directory(DIST, "index.html")


@app.get("/assets/<path:name>")
def assets(name):
    return send_from_directory(DIST / "assets", name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8000)), debug=False)
