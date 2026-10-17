"""Central configuration for the monitoring tool."""

DB_PATH = "monitor.db"
COLLECT_INTERVAL = 5          # seconds between metric samples
RETENTION_DAYS = 7            # old metrics are deleted automatically

# metric -> (threshold %, consecutive breaches needed to open an incident, severity)
THRESHOLDS = {
    "cpu":  (85, 3, "critical"),
    "mem":  (90, 3, "critical"),
    "disk": (90, 1, "warning"),
}

# Endpoints to health-check on every cycle.
HEALTH_CHECKS = [
    {"name": "Google", "url": "https://www.google.com", "timeout": 5},
    {"name": "Local app", "url": "http://127.0.0.1:5000/api/summary", "timeout": 3},
]
# Open a service-down incident after this many consecutive failures.
HEALTH_FAIL_LIMIT = 2
