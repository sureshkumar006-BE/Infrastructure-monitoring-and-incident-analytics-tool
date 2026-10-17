import sqlite3
import time
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                ts REAL, cpu REAL, mem REAL, disk REAL,
                load1 REAL, net_sent_kbps REAL, net_recv_kbps REAL
            );
            CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);

            CREATE TABLE IF NOT EXISTS health_checks (
                ts REAL, name TEXT, url TEXT, ok INTEGER, latency_ms REAL, error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_health_ts ON health_checks(ts);

            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT, severity TEXT, message TEXT,
                started_at REAL, resolved_at REAL, peak_value REAL
            );
            """
        )


def purge_old(days):
    cutoff = time.time() - days * 86400
    with get_conn() as c:
        c.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
        c.execute("DELETE FROM health_checks WHERE ts < ?", (cutoff,))
