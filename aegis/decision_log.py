"""Decision logging — every Aegis verdict is appended as one JSONL record.

Reproducibility is a project requirement: the eventual ablation numbers are
derived from these logs. Keep the schema append-only and stable.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG_PATH = "runs/aegis/decisions.jsonl"


class DecisionLogger:
    """Thread-safe JSONL appender. ``max_workers > 1`` in the benchmark uses a
    process pool, so each process opens the file in append mode independently;
    JSONL tolerates that as long as each ``log`` writes one whole line."""

    def __init__(self, path: str = DEFAULT_LOG_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(self, **record: object) -> None:
        record["ts"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(record, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


_default: DecisionLogger | None = None


def get_logger() -> DecisionLogger:
    """Process-wide default logger (lazily created)."""
    global _default
    if _default is None:
        _default = DecisionLogger()
    return _default
