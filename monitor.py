"""Collector + incident detector. Run standalone: python monitor.py"""
import os
import time
import urllib.request
import psutil

import config
from db import get_conn, init_db, purge_old

_breaches = {}        # metric -> consecutive breach count
_health_fails = {}    # check name -> consecutive failures
_last_net = None      # (timestamp, bytes_sent, bytes_recv)


# ---------------------------------------------------------------- collection
def collect_metrics():
    global _last_net
    now = time.time()
    net = psutil.net_io_counters()
    sent_kbps = recv_kbps = 0.0
    if _last_net:
        dt = max(now - _last_net[0], 0.001)
        sent_kbps = (net.bytes_sent - _last_net[1]) / 1024 / dt
        recv_kbps = (net.bytes_recv - _last_net[2]) / 1024 / dt
    _last_net = (now, net.bytes_sent, net.bytes_recv)

    load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    root = os.path.abspath(os.sep)
    return {
        "ts": now,
        "cpu": psutil.cpu_percent(interval=1),
        "mem": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage(root).percent,
        "load1": load1,
        "net_sent_kbps": round(sent_kbps, 2),
        "net_recv_kbps": round(recv_kbps, 2),
    }


def store_metrics(m):
    with get_conn() as c:
        c.execute(
            "INSERT INTO metrics VALUES (?,?,?,?,?,?,?)",
            (m["ts"], m["cpu"], m["mem"], m["disk"], m["load1"],
             m["net_sent_kbps"], m["net_recv_kbps"]),
        )


_IGNORED = {"system idle process", "idle", "system", "registry", "memory compression"}


def top_process(sort_by="cpu_percent"):
    """Return the heaviest real process by CPU or memory (skips OS placeholders)."""
    ncpu = psutil.cpu_count() or 1
    procs = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            if (info["name"] or "").lower() in _IGNORED:
                continue
            procs.append(info)
        except psutil.Error:
            pass
    procs.sort(key=lambda x: (x[sort_by] or 0), reverse=True)
    if procs:
        t = procs[0]
        cpu = (t["cpu_percent"] or 0) / ncpu   # normalise to 0-100% of whole machine
        return f"{t['name']} (cpu {cpu:.1f}%, mem {t['memory_percent'] or 0:.1f}%)"
    return "unknown"


# ------------------------------------------------------------- incident logic
def open_incident(metric, severity, message, value):
    with get_conn() as c:
        c.execute(
            "INSERT INTO incidents (metric, severity, message, started_at, peak_value) "
            "VALUES (?,?,?,?,?)",
            (metric, severity, message, time.time(), value),
        )
    print(f"[INCIDENT OPENED] {metric}: {message}")


def get_open_incident(metric):
    with get_conn() as c:
        return c.execute(
            "SELECT * FROM incidents WHERE metric=? AND resolved_at IS NULL", (metric,)
        ).fetchone()


def resolve_incident(metric):
    with get_conn() as c:
        c.execute(
            "UPDATE incidents SET resolved_at=? WHERE metric=? AND resolved_at IS NULL",
            (time.time(), metric),
        )
    print(f"[INCIDENT RESOLVED] {metric}")


def update_peak(metric, value):
    with get_conn() as c:
        c.execute(
            "UPDATE incidents SET peak_value=MAX(peak_value, ?) "
            "WHERE metric=? AND resolved_at IS NULL",
            (value, metric),
        )


def evaluate_thresholds(m):
    for metric, (limit, needed, severity) in config.THRESHOLDS.items():
        value = m[metric]
        if value >= limit:
            _breaches[metric] = _breaches.get(metric, 0) + 1
            if get_open_incident(metric):
                update_peak(metric, value)
            elif _breaches[metric] >= needed:
                sort_key = "memory_percent" if metric == "mem" else "cpu_percent"
                culprit = f" Top process: {top_process(sort_key)}" if metric in ("cpu", "mem") else ""
                open_incident(
                    metric, severity,
                    f"{metric.upper()} at {value:.1f}% (limit {limit}%).{culprit}", value,
                )
        else:
            _breaches[metric] = 0
            if get_open_incident(metric):
                resolve_incident(metric)


# ---------------------------------------------------------------- health checks
def run_health_checks():
    for chk in config.HEALTH_CHECKS:
        name, url = chk["name"], chk["url"]
        start = time.time()
        ok, err = 1, None
        try:
            with urllib.request.urlopen(url, timeout=chk.get("timeout", 5)) as r:
                if r.status >= 400:
                    ok, err = 0, f"HTTP {r.status}"
        except Exception as e:  # noqa: BLE001
            ok, err = 0, str(e)[:200]
        latency = (time.time() - start) * 1000

        with get_conn() as c:
            c.execute(
                "INSERT INTO health_checks VALUES (?,?,?,?,?,?)",
                (time.time(), name, url, ok, round(latency, 1), err),
            )

        key = f"service:{name}"
        if ok:
            _health_fails[key] = 0
            if get_open_incident(key):
                resolve_incident(key)
        else:
            _health_fails[key] = _health_fails.get(key, 0) + 1
            if _health_fails[key] >= config.HEALTH_FAIL_LIMIT and not get_open_incident(key):
                open_incident(key, "critical", f"{name} is DOWN: {err}", 0)


# -------------------------------------------------------------------- main loop
def run_forever():
    init_db()
    cycles = 0
    while True:
        try:
            m = collect_metrics()
            store_metrics(m)
            evaluate_thresholds(m)
            run_health_checks()
            cycles += 1
            if cycles % 720 == 0:
                purge_old(config.RETENTION_DAYS)
        except Exception as e:  # noqa: BLE001  keep the collector alive
            print("collector error:", e)
        time.sleep(config.COLLECT_INTERVAL)


if __name__ == "__main__":
    run_forever()