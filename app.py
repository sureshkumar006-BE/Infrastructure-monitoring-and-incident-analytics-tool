"""Web dashboard + JSON API. Run: python app.py  ->  http://127.0.0.1:5000"""
import threading
import time
from flask import Flask, jsonify, render_template, request

from db import get_conn, init_db
from monitor import run_forever

app = Flask(__name__)


def rows(sql, args=()):
    with get_conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/metrics")
def metrics():
    minutes = int(request.args.get("minutes", 30))
    since = time.time() - minutes * 60
    return jsonify(rows("SELECT * FROM metrics WHERE ts >= ? ORDER BY ts", (since,)))


@app.route("/api/incidents")
def incidents():
    return jsonify(rows("SELECT * FROM incidents ORDER BY started_at DESC LIMIT 50"))


@app.route("/api/health")
def health():
    return jsonify(rows(
        "SELECT h.* FROM health_checks h JOIN "
        "(SELECT name, MAX(ts) AS mts FROM health_checks GROUP BY name) l "
        "ON h.name = l.name AND h.ts = l.mts"
    ))


@app.route("/api/summary")
def summary():
    day_ago = time.time() - 86400
    total = rows("SELECT COUNT(*) AS n FROM incidents WHERE started_at >= ?", (day_ago,))[0]["n"]
    open_n = rows("SELECT COUNT(*) AS n FROM incidents WHERE resolved_at IS NULL")[0]["n"]
    mttr = rows(
        "SELECT AVG(resolved_at - started_at) AS a FROM incidents "
        "WHERE resolved_at IS NOT NULL AND started_at >= ?", (day_ago,)
    )[0]["a"]
    avg = rows(
        "SELECT AVG(cpu) AS cpu, AVG(mem) AS mem, AVG(disk) AS disk "
        "FROM metrics WHERE ts >= ?", (day_ago,)
    )[0]
    checks = rows("SELECT AVG(ok) AS a FROM health_checks WHERE ts >= ?", (day_ago,))[0]["a"]
    return jsonify({
        "incidents_24h": total,
        "open_incidents": open_n,
        "mttr_seconds": round(mttr, 1) if mttr else None,
        "availability_pct": round(checks * 100, 2) if checks is not None else None,
        "avg": {k: round(v, 1) if v is not None else None for k, v in avg.items()},
    })


if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_forever, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
