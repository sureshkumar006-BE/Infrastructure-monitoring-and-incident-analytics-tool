# Infrastructure Monitoring & Incident Analytics

A lightweight monitoring tool built in Python. It collects system metrics, health-checks web services, automatically opens and resolves incidents when thresholds are crossed, and shows everything on a live web dashboard.

![Dashboard screenshot](screenshot.png)

## Features

- **Metric collection** every 5 seconds: CPU, memory, disk, load average, network in/out (`psutil`)
- **Service health checks**: HTTP up/down status and response time
- **Automatic incident detection**: an incident opens when a metric stays over its limit for several samples in a row, and resolves itself on recovery
- **Root-cause hint**: incident messages name the process using the most CPU or memory
- **Incident analytics**: open incidents, incidents in 24h, MTTR (mean time to resolve), availability %
- **Live dashboard** with charts, service status and incident history
- **Data retention**: metrics older than 7 days are deleted automatically

## Tech stack

Python, Flask, SQLite, psutil, Chart.js

## Project structure

```
infra-monitor/
├── app.py                  # Flask web server + JSON API
├── monitor.py              # collector + incident detection logic
├── db.py                   # SQLite schema and helpers
├── config.py               # thresholds, health-check URLs, retention
├── templates/
│   └── dashboard.html      # live dashboard
└── requirements.txt
```

## Run it

```bash
git clone https://github.com/<your-username>/infra-monitor.git
cd infra-monitor
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Configuration

Edit `config.py`:

```python
THRESHOLDS = {
    "cpu":  (85, 3, "critical"),   # (limit %, consecutive breaches, severity)
    "mem":  (90, 3, "critical"),
    "disk": (90, 1, "warning"),
}
```

Add or change URLs in `HEALTH_CHECKS` to monitor your own services.

## API endpoints

| Endpoint | Returns |
| --- | --- |
| `/api/metrics?minutes=30` | Recent metric samples |
| `/api/incidents` | Last 50 incidents |
| `/api/health` | Latest status of each health check |
| `/api/summary` | Open incidents, 24h count, MTTR, availability |

## How incident detection works

A single spike is normal, so an incident only opens after several consecutive samples over the limit. When the metric drops back under the limit, the incident closes and its duration is recorded. This reduces false alarms (alert fatigue).

## Possible improvements

- Telegram / email alerts
- Docker packaging
- Run as a `systemd` service on Linux
- Multi-server agents with a central collector
<img width="1513" height="862" alt="Screenshot 2026-10-17 181702" src="https://github.com/user-attachments/assets/b7def2cc-ca53-4aa8-849e-d10417f6bad2" />
