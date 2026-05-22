"""
analyzer.py — Statistical aggregations over parsed LogEntry lists.

All functions accept a list[LogEntry] and return plain dicts/lists
suitable for JSON serialization.
"""

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional
import statistics

from parser import LogEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESPONSE_TIME_CAP_MS = 60_000

def _status_class(status: Optional[int]) -> str:
    if status is None:
        return "unknown"
    if status < 200:
        return "1xx"
    if status < 300:
        return "2xx"
    if status < 400:
        return "3xx"
    if status < 500:
        return "4xx"
    return "5xx"


def _normalize_path(path: str) -> str:
    """Collapse numeric path segments for grouping: /api/users/123 → /api/users/{id}"""
    import re
    return re.sub(r"/\d+", "/{id}", path)


def _response_times(entries: list[LogEntry]) -> list[float]:
    return [e.response_ms for e in entries if e.response_ms is not None and e.response_ms >= 0]


def _capped_response_times(times: list[float]) -> list[float]:
    return [t for t in times if t <= RESPONSE_TIME_CAP_MS]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def compute_summary(entries: list[LogEntry], parse_result) -> dict:
    if not entries:
        return {
            "total_requests": 0,
            "total_lines": parse_result.total_lines,
            "malformed_count": parse_result.malformed_count,
            "parse_success_rate": 0.0,
            "error_rate": 0.0,
            "time_range_start": None,
            "time_range_end": None,
            "duration_seconds": None,
            "avg_response_ms": None,
            "avg_response_ms_cap_ms": RESPONSE_TIME_CAP_MS,
            "avg_response_ms_excluded": 0,
            "median_response_ms": None,
            "p95_response_ms": None,
            "p99_response_ms": None,
            "json_line_count": parse_result.json_line_count,
            "format_anomalies": parse_result.format_anomalies,
        }

    total = len(entries)
    error_entries = [e for e in entries if e.status and e.status >= 400]
    rt_entries = _response_times(entries)
    capped_rt_entries = _capped_response_times(rt_entries)

    timestamps = [e.timestamp for e in entries if e.timestamp]
    ts_start = min(timestamps) if timestamps else None
    ts_end = max(timestamps) if timestamps else None
    duration = (ts_end - ts_start).total_seconds() if ts_start and ts_end else None

    avg_rt = statistics.mean(capped_rt_entries) if capped_rt_entries else None
    median_rt = statistics.median(rt_entries) if rt_entries else None
    sorted_rt = sorted(capped_rt_entries)
    p95 = sorted_rt[int(len(sorted_rt) * 0.95)] if sorted_rt else None
    p99 = sorted_rt[int(len(sorted_rt) * 0.99)] if sorted_rt else None

    return {
        "total_requests": total,
        "total_lines": parse_result.total_lines,
        "malformed_count": parse_result.malformed_count,
        "parse_success_rate": round(total / parse_result.total_lines * 100, 1) if parse_result.total_lines else 0,
        "error_rate": round(len(error_entries) / total * 100, 1),
        "time_range_start": ts_start.isoformat() if ts_start else None,
        "time_range_end": ts_end.isoformat() if ts_end else None,
        "duration_seconds": round(duration, 1) if duration else None,
        "avg_response_ms": round(avg_rt, 1) if avg_rt is not None else None,
        "avg_response_ms_cap_ms": RESPONSE_TIME_CAP_MS,
        "avg_response_ms_excluded": max(len(rt_entries) - len(capped_rt_entries), 0),
        "median_response_ms": round(median_rt, 1) if median_rt is not None else None,
        "p95_response_ms": round(p95, 1) if p95 is not None else None,
        "p99_response_ms": round(p99, 1) if p99 is not None else None,
        "json_line_count": parse_result.json_line_count,
        "format_anomalies": parse_result.format_anomalies,
    }


# ---------------------------------------------------------------------------
# Status code distribution
# ---------------------------------------------------------------------------

def status_distribution(entries: list[LogEntry]) -> list[dict]:
    counter = Counter(_status_class(e.status) for e in entries)
    order = ["2xx", "3xx", "4xx", "5xx", "1xx", "unknown"]
    return [
        {"class": cls, "count": counter.get(cls, 0)}
        for cls in order
        if counter.get(cls, 0) > 0
    ]


def status_code_breakdown(entries: list[LogEntry]) -> list[dict]:
    counter = Counter(str(e.status) if e.status else "unknown" for e in entries)
    return [
        {"status": code, "count": cnt}
        for code, cnt in counter.most_common(20)
    ]


# ---------------------------------------------------------------------------
# Slowest endpoints
# ---------------------------------------------------------------------------

def slowest_endpoints(entries: list[LogEntry], top_n: int = 10) -> list[dict]:
    """Return top N endpoint+method combos by average response time."""
    groups: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        if e.response_ms is not None and e.response_ms >= 0 and e.method and e.path:
            key = f"{e.method} {_normalize_path(e.path)}"
            groups[key].append(e.response_ms)

    results = []
    for endpoint, times in groups.items():
        capped_times = _capped_response_times(times)
        avg_source = capped_times if capped_times else times
        results.append({
            "endpoint": endpoint,
            "avg_ms": round(statistics.mean(avg_source), 1),
            "max_ms": round(max(times), 1),
            "p95_ms": round(sorted(times)[int(len(times) * 0.95)], 1),
            "request_count": len(times),
        })

    return sorted(results, key=lambda x: x["avg_ms"], reverse=True)[:top_n]


# ---------------------------------------------------------------------------
# Top error IPs
# ---------------------------------------------------------------------------

def top_error_ips(entries: list[LogEntry], top_n: int = 10) -> list[dict]:
    ip_errors: Counter = Counter()
    ip_total: Counter = Counter()

    for e in entries:
        if e.ip:
            ip_total[e.ip] += 1
            if e.status and e.status >= 400:
                ip_errors[e.ip] += 1

    results = [
        {
            "ip": ip,
            "error_count": cnt,
            "total_requests": ip_total[ip],
            "error_rate": round(cnt / ip_total[ip] * 100, 1) if ip_total[ip] else 0,
        }
        for ip, cnt in ip_errors.most_common(top_n)
    ]
    return results


# ---------------------------------------------------------------------------
# Requests over time (bucketed by minute or hour)
# ---------------------------------------------------------------------------

def requests_over_time(entries: list[LogEntry], buckets: int = 60) -> list[dict]:
    """Return request counts bucketed across the time range, for a line chart."""
    timed = [e for e in entries if e.timestamp]
    if not timed:
        return []

    ts_min = min(e.timestamp for e in timed)
    ts_max = max(e.timestamp for e in timed)
    total_seconds = (ts_max - ts_min).total_seconds()

    if total_seconds <= 0:
        return [{"time": ts_min.strftime("%H:%M"), "requests": len(timed), "errors": 0}]

    bucket_size = max(total_seconds / buckets, 1)
    bucket_counts: list[int] = [0] * buckets
    error_counts: list[int] = [0] * buckets

    for e in timed:
        offset = (e.timestamp - ts_min).total_seconds()
        idx = min(int(offset / bucket_size), buckets - 1)
        bucket_counts[idx] += 1
        if e.status and e.status >= 400:
            error_counts[idx] += 1

    result = []
    for i in range(buckets):
        if bucket_counts[i] > 0:
            bucket_ts = ts_min.timestamp() + i * bucket_size
            dt = datetime.fromtimestamp(bucket_ts, tz=timezone.utc)
            result.append({
                "time": dt.strftime("%H:%M"),
                "requests": bucket_counts[i],
                "errors": error_counts[i],
            })

    return result


# ---------------------------------------------------------------------------
# Top endpoints by request count
# ---------------------------------------------------------------------------

def top_endpoints_by_volume(entries: list[LogEntry], top_n: int = 10) -> list[dict]:
    counter: Counter = Counter()
    for e in entries:
        if e.path and e.method:
            counter[f"{e.method} {_normalize_path(e.path)}"] += 1
    return [{"endpoint": ep, "count": cnt} for ep, cnt in counter.most_common(top_n)]


# ---------------------------------------------------------------------------
# Method distribution
# ---------------------------------------------------------------------------

def method_distribution(entries: list[LogEntry]) -> list[dict]:
    counter = Counter(e.method for e in entries if e.method)
    return [{"method": m, "count": c} for m, c in counter.most_common()]


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def analyze(parse_result) -> dict:
    entries = parse_result.entries
    return {
        "summary": compute_summary(entries, parse_result),
        "status_distribution": status_distribution(entries),
        "status_code_breakdown": status_code_breakdown(entries),
        "slowest_endpoints": slowest_endpoints(entries),
        "top_error_ips": top_error_ips(entries),
        "requests_over_time": requests_over_time(entries),
        "top_endpoints_by_volume": top_endpoints_by_volume(entries),
        "method_distribution": method_distribution(entries),
        "malformed_samples": parse_result.malformed_lines[:20],
    }