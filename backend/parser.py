"""
parser.py — Parses server log files with graceful handling of format deviations.

Supported line formats:
  Primary:  TIMESTAMP IP METHOD PATH STATUS RESPONSE_TIME [extras...]
  JSON:     {"timestamp":..., "remote_ip":..., "method":..., ...}
  Malformed: counted and surfaced, never crash

Timestamp formats handled:
  - ISO 8601:     2024-03-15T14:23:01Z
  - Slash date:   2024/03/15 14:23:01
  - Named month:  15-Mar-2024 14:23:01
  - Unix epoch:   1710512581

Response time formats handled:
  - 142ms, 0.142s, 142 (bare integer)
"""

import re
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "CONNECT", "TRACE"}


@dataclass
class LogEntry:
    raw: str
    timestamp: Optional[datetime] = None
    ip: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    status: Optional[int] = None
    response_ms: Optional[float] = None
    source_format: str = "primary"  # "primary" | "json"
    extras: list = field(default_factory=list)


@dataclass
class ParseResult:
    entries: list[LogEntry]
    malformed_lines: list[str]
    malformed_count: int
    total_lines: int
    json_line_count: int
    format_anomalies: dict  # counts of each deviation type encountered


# ---------------------------------------------------------------------------
# Timestamp parsers — tried in order, first match wins
# ---------------------------------------------------------------------------

_TS_FORMATS = [
    # ISO 8601 with Z or offset
    (re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"), "%Y-%m-%dT%H:%M:%S"),
    # Slash date: 2024/03/15 14:23:01
    (re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}"), "%Y/%m/%d %H:%M:%S"),
    # Named month: 15-Mar-2024 14:23:01
    (re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}:\d{2}"), "%d-%b-%Y %H:%M:%S"),
]

_ISO_CLEANUP = re.compile(r"Z$|\+\d{2}:\d{2}$")
_EPOCH_RE = re.compile(r"^\d{10}$")


def _parse_timestamp(token: str) -> Optional[datetime]:
    """Parse a timestamp token into a UTC datetime. Returns None if unparseable."""
    # Unix epoch (exactly 10 digits)
    if _EPOCH_RE.match(token):
        try:
            return datetime.fromtimestamp(int(token), tz=timezone.utc)
        except (ValueError, OSError):
            return None

    cleaned = _ISO_CLEANUP.sub("", token)
    for pattern, fmt in _TS_FORMATS:
        if pattern.match(cleaned):
            try:
                return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Response time parser
# ---------------------------------------------------------------------------

_RT_MS = re.compile(r"^(\d+(?:\.\d+)?)ms$", re.IGNORECASE)
_RT_S = re.compile(r"^(\d+(?:\.\d+)?)s$", re.IGNORECASE)
_RT_BARE = re.compile(r"^(\d+(?:\.\d+)?)$")


def _parse_response_time(token: str) -> Optional[float]:
    """Return response time in milliseconds. Returns None if unparseable."""
    m = _RT_MS.match(token)
    if m:
        return float(m.group(1))
    m = _RT_S.match(token)
    if m:
        return float(m.group(1)) * 1000.0
    m = _RT_BARE.match(token)
    if m:
        return float(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Status code parser
# ---------------------------------------------------------------------------

def _parse_status(token: str) -> Optional[int]:
    """Return HTTP status int, or None if missing/invalid."""
    if token == "-":
        return None
    try:
        val = int(token)
        return val if 100 <= val <= 599 else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# IP validator (loose — just needs to look like an IP)
# ---------------------------------------------------------------------------

_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def _is_ip(token: str) -> bool:
    return bool(_IP_RE.match(token))


# ---------------------------------------------------------------------------
# JSON line parser
# ---------------------------------------------------------------------------

_JSON_FIELD_MAP = {
    "timestamp": ["timestamp", "time", "@timestamp"],
    "ip": ["remote_ip", "ip", "client_ip", "host"],
    "method": ["method", "http_method", "verb"],
    "path": ["path", "url", "uri", "request_path"],
    "status": ["status", "status_code", "http_status", "response_code"],
    "response_ms": ["duration_ms", "response_time_ms", "latency_ms", "duration", "response_time"],
}


def _parse_json_line(raw: str) -> Optional[LogEntry]:
    """Try to parse a JSON log line. Returns LogEntry or None."""
    try:
        obj = json.loads(raw.strip())
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(obj, dict):
        return None

    entry = LogEntry(raw=raw, source_format="json")

    def pick(fields):
        for f in fields:
            if f in obj:
                return obj[f]
        return None

    ts_raw = pick(_JSON_FIELD_MAP["timestamp"])
    if ts_raw:
        entry.timestamp = _parse_timestamp(str(ts_raw).replace("Z", "").split("+")[0].replace("T", "T"))
        if entry.timestamp is None:
            # fallback: try as-is
            try:
                entry.timestamp = datetime.fromisoformat(str(ts_raw).rstrip("Z")).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    entry.ip = pick(_JSON_FIELD_MAP["ip"])
    entry.method = pick(_JSON_FIELD_MAP["method"])
    entry.path = pick(_JSON_FIELD_MAP["path"])

    status_raw = pick(_JSON_FIELD_MAP["status"])
    if status_raw is not None:
        entry.status = _parse_status(str(status_raw))

    rt_raw = pick(_JSON_FIELD_MAP["response_ms"])
    if rt_raw is not None:
        rt = _parse_response_time(str(rt_raw))
        entry.response_ms = rt if rt is not None else (float(rt_raw) if isinstance(rt_raw, (int, float)) else None)

    # Only accept if we got at least timestamp + method + path
    if entry.method and entry.path:
        return entry
    return None


# ---------------------------------------------------------------------------
# Primary format parser
# ---------------------------------------------------------------------------

def _parse_primary_line(raw: str) -> Optional[LogEntry]:
    """
    Parse a primary-format log line.
    Expected: TIMESTAMP IP METHOD PATH STATUS RESPONSE_TIME [extras...]

    Handles:
      - Leading/trailing whitespace
      - Missing or '-' status codes
      - Response time in ms, s, or bare int
      - Extra fields appended (user agent, referrer)
    """
    line = raw.strip()
    if not line:
        return None

    tokens = line.split()
    if len(tokens) < 4:
        return None

    entry = LogEntry(raw=raw, source_format="primary")
    idx = 0

    # --- Timestamp ---
    # Some formats (slash, named month) have a space between date and time,
    # so the timestamp might be tokens[0] + tokens[1].
    ts = _parse_timestamp(tokens[idx])
    if ts is None and idx + 1 < len(tokens):
        # Try combining first two tokens (e.g. "2024/03/15" + "14:23:01")
        combined = tokens[idx] + " " + tokens[idx + 1]
        ts = _parse_timestamp(combined)
        if ts is not None:
            idx += 1  # consumed two tokens for timestamp
    if ts is None:
        return None
    entry.timestamp = ts
    idx += 1

    if idx >= len(tokens):
        return None

    # --- IP ---
    if not _is_ip(tokens[idx]):
        return None
    entry.ip = tokens[idx]
    idx += 1

    if idx >= len(tokens):
        return None

    # --- Method ---
    if tokens[idx].upper() not in VALID_METHODS:
        return None
    entry.method = tokens[idx].upper()
    idx += 1

    if idx >= len(tokens):
        return None

    # --- Path ---
    entry.path = tokens[idx]
    idx += 1

    # --- Status (optional: may be '-' or missing entirely) ---
    if idx < len(tokens):
        status = _parse_status(tokens[idx])
        # status is None either because it's '-' OR because this token isn't a status at all
        # Check if it even looks like it's supposed to be a status
        if tokens[idx] == "-" or (tokens[idx].isdigit() and 100 <= int(tokens[idx]) <= 599):
            entry.status = status
            idx += 1

    # --- Response time (optional) ---
    if idx < len(tokens):
        rt = _parse_response_time(tokens[idx])
        if rt is not None:
            entry.response_ms = rt
            idx += 1

    # --- Extras (user agent, referrer, etc.) ---
    if idx < len(tokens):
        entry.extras = tokens[idx:]

    return entry


def _classify_primary_line(tokens: list[str]) -> tuple[str | None, str | None]:
    """Return the timestamp token and response-time token for a primary-format line."""
    if not tokens:
        return None, None

    idx = 0

    ts_token = tokens[idx]
    if _parse_timestamp(ts_token) is None and idx + 1 < len(tokens):
        combined = tokens[idx] + " " + tokens[idx + 1]
        if _parse_timestamp(combined) is not None:
            ts_token = combined
            idx += 1

    idx += 1  # IP
    if idx < len(tokens):
        idx += 1  # method
    if idx < len(tokens):
        idx += 1  # path
    if idx < len(tokens):
        idx += 1  # status
    if idx < len(tokens):
        if tokens[idx] == "-" or (tokens[idx].isdigit() and 100 <= int(tokens[idx]) <= 599):
            idx += 1

    rt_token = tokens[idx] if idx < len(tokens) else None
    return ts_token, rt_token


# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------

_MAX_MALFORMED_SAMPLES = 20


def parse_log_file(filepath: str) -> ParseResult:
    """
    Parse a log file and return a ParseResult.
    Never raises — all errors are captured in malformed_lines.
    """
    entries: list[LogEntry] = []
    malformed_lines: list[str] = []
    total_lines = 0
    json_line_count = 0
    anomalies = {
        "alt_timestamp_format": 0,
        "alt_response_time_format": 0,
        "missing_status": 0,
        "json_lines": 0,
        "extra_fields": 0,
        "malformed": 0,
    }

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                total_lines += 1
                line = raw_line.strip()

                # Skip blank lines — count as malformed
                if not line:
                    anomalies["malformed"] += 1
                    if len(malformed_lines) < _MAX_MALFORMED_SAMPLES:
                        malformed_lines.append(raw_line.rstrip("\n"))
                    continue

                # Try JSON first (lines starting with '{')
                if line.startswith("{"):
                    entry = _parse_json_line(line)
                    if entry:
                        entries.append(entry)
                        json_line_count += 1
                        anomalies["json_lines"] += 1
                        continue
                    # JSON-looking but unparseable → malformed
                    anomalies["malformed"] += 1
                    if len(malformed_lines) < _MAX_MALFORMED_SAMPLES:
                        malformed_lines.append(line)
                    continue

                # Try primary format
                entry = _parse_primary_line(line)
                if entry:
                    # Track anomaly subtypes
                    if entry.source_format == "primary":
                        tokens = line.split()
                        ts_token, rt_token = _classify_primary_line(tokens)

                        if "/" in ts_token or re.match(r"^\d{2}-[A-Za-z]", ts_token) or _EPOCH_RE.match(ts_token):
                            anomalies["alt_timestamp_format"] += 1

                        if rt_token and (_RT_S.match(rt_token) or _RT_BARE.match(rt_token)) and not _RT_MS.match(rt_token):
                                anomalies["alt_response_time_format"] += 1
                    if entry.status is None:
                        anomalies["missing_status"] += 1
                    if entry.extras:
                        anomalies["extra_fields"] += 1
                    entries.append(entry)
                else:
                    anomalies["malformed"] += 1
                    if len(malformed_lines) < _MAX_MALFORMED_SAMPLES:
                        malformed_lines.append(line)

    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error parsing {filepath}: {e}")

    return ParseResult(
        entries=entries,
        malformed_lines=malformed_lines,
        malformed_count=anomalies["malformed"],
        total_lines=total_lines,
        json_line_count=json_line_count,
        format_anomalies=anomalies,
    )