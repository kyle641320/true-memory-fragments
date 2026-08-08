from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENTS_PATH = "metrics/events.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def metrics_file(repo_root: str | Path) -> Path:
    root = Path(repo_root).resolve() / ".tmf"
    root.mkdir(parents=True, exist_ok=True)
    path = root / EVENTS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def log_event(repo_root: str | Path, event: str, *, node_id: str | None = None, **fields: Any) -> None:
    """Append one local metrics event without source contents."""
    payload: dict[str, Any] = {"ts": _now(), "event": event}
    if node_id is not None:
        payload["node_id"] = node_id
    for key, value in fields.items():
        if key in {"source", "source_text", "content", "code"}:
            continue
        payload[key] = value
    with metrics_file(repo_root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def load_events(repo_root: str | Path, *, since: str | None = None) -> list[dict[str, Any]]:
    path = metrics_file(repo_root)
    threshold = _parse_ts(since) if since else None
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if threshold is not None:
            ts = _parse_ts(str(item.get("ts", "")))
            if ts is None or ts < threshold:
                continue
        out.append(item)
    return out


def stats(repo_root: str | Path, *, since: str | None = None) -> dict[str, Any]:
    events = load_events(repo_root, since=since)
    counts: dict[str, int] = {}
    rederive_ms = 0.0
    cache_bytes = 0
    read_bytes = 0
    for item in events:
        event = str(item.get("event"))
        counts[event] = counts.get(event, 0) + 1
        if event == "rederive":
            try:
                rederive_ms += float(item.get("duration_ms") or 0)
            except Exception:
                pass
        try:
            cache_bytes += int(item.get("cache_bytes_estimate") or 0)
        except Exception:
            pass
        try:
            read_bytes += int(item.get("read_bytes") or 0)
        except Exception:
            pass
    hits = counts.get("cache_hit", 0)
    misses = counts.get("miss", 0)
    stale = counts.get("stale_detected", 0)
    denom = hits + misses + stale
    return {
        "events": len(events),
        "counts": counts,
        "hit_rate": (hits / denom) if denom else None,
        "stale_detected": stale,
        "rederive_count": counts.get("rederive", 0),
        "rederive_duration_ms_total": round(rederive_ms, 3),
        "cache_service_bytes_estimate": cache_bytes,
        "read_bytes": read_bytes,
        "rename_migrations": counts.get("rename_migration", 0),
        "rename_mass_invalidations": counts.get("rename_mass_invalidation", 0),
    }
