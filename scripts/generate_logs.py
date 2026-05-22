#!/usr/bin/env python3
"""
generate_logs.py — generates a representative test log file.
Usage: python scripts/generate_logs.py [--lines 5000] [--hours 24] [--output logs/test.log]
"""

import argparse
import json
import os
import random
from datetime import datetime, timedelta, timezone

ENDPOINTS = [
    "/api/users", "/api/users/12", "/api/users/99", "/api/login", "/api/logout",
    "/api/products", "/api/products/45", "/api/orders", "/api/orders/7",
    "/api/dashboard", "/api/search", "/api/settings", "/health", "/metrics",
    "/api/payments", "/api/payments/confirm", "/api/upload", "/static/app.js",
    "/static/style.css", "/favicon.ico",
]

METHODS = ["GET", "GET", "GET", "GET", "POST", "POST", "PUT", "DELETE", "PATCH"]

STATUS_CODES = [
    200, 200, 200, 200, 200, 200, 200, 200, 200, 200,
    200, 200, 200, 200, 200, 200, 200, 200, 200, 200,
    200, 200, 200, 200, 200, 200, 200, 200, 200, 200,
    200, 200, 200, 200, 200, 200, 200, 200, 200, 200,
    201, 201, 201, 201, 204, 204, 204, 204, 301, 304,
    400, 400, 401, 403, 404, 404, 500, 502, 503,
]

IPS = [
    "192.168.1.42", "192.168.1.55", "10.0.0.7", "10.0.0.23",
    "172.16.0.5", "203.0.113.14", "198.51.100.77", "203.0.113.99",
    "10.10.10.1", "192.168.2.100",
]

USER_AGENTS = [
    '"Mozilla/5.0 (Windows NT 10.0)"',
    '"curl/7.68.0"',
    '"python-requests/2.28.0"',
    '"Mozilla/5.0 (Macintosh; Intel Mac OS X)"',
]

REFERRERS = ['"https://example.com/dashboard"', '"https://google.com"', '"-"']

STACK_TRACE_LINES = [
    "  at processRequest (server.js:142)",
    "  at async handleRoute (router.js:88)",
    "  at async Server.<anonymous> (server.js:201)",
    "NullPointerException: Cannot read property 'id' of undefined",
    "Error: Connection timeout after 30000ms",
]


def iso_timestamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def slash_timestamp(dt):
    return dt.strftime("%Y/%m/%d %H:%M:%S")


def named_month_timestamp(dt):
    return dt.strftime("%d-%b-%Y %H:%M:%S")


def unix_timestamp(dt):
    return str(int(dt.timestamp()))


def response_time_ms(ms):
    return f"{ms}ms"


def response_time_s(ms):
    return f"{ms/1000:.3f}s"


def response_time_bare(ms):
    return str(ms)


TIMESTAMP_FORMATTERS = [
    iso_timestamp,
    slash_timestamp,
    named_month_timestamp,
    unix_timestamp,
]


def generate_line(dt):
    ip = random.choice(IPS)
    method = random.choice(METHODS)
    path = random.choice(ENDPOINTS)
    status = random.choice(STATUS_CODES)

    ms = int(random.triangular(20, 800, 160))
    if random.random() < 0.03:
        ms = random.randint(900, 3200)

    status_str = str(status) if random.random() > 0.05 else "-"
    ts = random.choices(TIMESTAMP_FORMATTERS, weights=[90, 4, 3, 3])[0](dt)
    rt = random.choices(
        [response_time_ms, response_time_s, response_time_bare],
        weights=[97, 2, 1],
    )[0](ms)
    indent = "  " if random.random() < 0.03 else ""

    line = f"{indent}{ts} {ip} {method} {path} {status_str} {rt}"

    if random.random() < 0.04:
        line += f" {random.choice(USER_AGENTS)}"
    if random.random() < 0.03:
        line += f" {random.choice(REFERRERS)}"

    return line


def generate_json_line(dt):
    ip = random.choice(IPS)
    method = random.choice(METHODS)
    path = random.choice(ENDPOINTS)
    status = random.choice(STATUS_CODES)
    ms = int(random.triangular(20, 800, 180))
    if random.random() < 0.03:
        ms = random.randint(900, 3200)
    record = {
        "timestamp": dt.isoformat() + "Z",
        "remote_ip": ip,
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": ms,
        "service": "api-v2",
    }
    return json.dumps(record)


def generate_malformed():
    options = [
        "",
        "   ",
        "STARTUP: service initialized on port 8080",
        "2024-03-15T14:23:01Z incomplete",
        "192.168.1.42 GET /api/users",
        "[WARN] Database pool exhausted, waiting...",
        "----boundary----",
        f"2024-03-15 {random.choice(STACK_TRACE_LINES)}",
        "null null null null null null",
        "2024-03-15T14:23:01Z 10.0.0.7 UNKNOWN_METHOD /api/test abc 99xz",
    ]
    return random.choice(options)


def main():
    parser = argparse.ArgumentParser(description="Generate test log file")
    parser.add_argument("--lines", type=int, default=5000, help="Number of log entries")
    parser.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Time window to spread log entries across (default: 24h)",
    )
    parser.add_argument("--output", type=str, default="logs/test.log", help="Output file path")
    args = parser.parse_args()

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    else:
        os.makedirs(".", exist_ok=True)

    start_dt = datetime.now(tz=timezone.utc) - timedelta(hours=args.hours)
    total_seconds = args.hours * 3600
    lines_written = 0
    malformed_count = 0
    json_count = 0

    with open(args.output, "w", encoding="utf-8") as f:
        for _ in range(args.lines):
            offset = random.uniform(0, total_seconds)
            entry_dt = start_dt + timedelta(seconds=offset)

            roll = random.random()
            if roll < 0.07:
                f.write(generate_malformed() + "\n")
                malformed_count += 1
                if random.random() < 0.2:
                    f.write(random.choice(STACK_TRACE_LINES) + "\n")
                    malformed_count += 1
            elif roll < 0.12:
                f.write(generate_json_line(entry_dt) + "\n")
                json_count += 1
            else:
                f.write(generate_line(entry_dt) + "\n")

            lines_written += 1

    print(f"✓ Generated {lines_written} lines → {args.output}")
    print(f"  ~{malformed_count} malformed lines, ~{json_count} JSON lines")


if __name__ == "__main__":
    main()
