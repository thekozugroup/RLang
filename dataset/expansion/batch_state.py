"""batch_state.py

Tracks conversion progress to disk so interrupted runs can resume
without re-converting rows that already succeeded.

State file location: batches/state.json (relative to this file's directory,
or overridden by the path passed to BatchState).

Usage:
    from batch_state import BatchState
    from pathlib import Path

    state = BatchState(Path(__file__).parent / "batches" / "state.json")
    state.load()

    for row in rows:
        if state.is_done(row["id"]):
            continue
        result = convert(row)
        if result:
            state.mark_done(row["id"])
        else:
            state.mark_failed(row["id"])
    state.save()
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_DEFAULT_STATE_FILE = Path(__file__).resolve().parent / "batches" / "state.json"


class BatchState:
    """Persist conversion progress to disk; supports resume and failure tracking."""

    def __init__(self, state_file: Optional[Path] = None) -> None:
        self._state_file: Path = Path(state_file) if state_file else _DEFAULT_STATE_FILE
        self._done: set[str] = set()
        self._failed: set[str] = set()
        self._last_updated: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mark_done(self, row_id: str) -> None:
        """Mark a row as successfully converted."""
        row_id = str(row_id)
        self._done.add(row_id)
        self._failed.discard(row_id)
        self._touch()

    def mark_failed(self, row_id: str) -> None:
        """Mark a row as failed (will be skipped on resume unless cleared)."""
        row_id = str(row_id)
        if row_id not in self._done:
            self._failed.add(row_id)
        self._touch()

    def is_done(self, row_id: str) -> bool:
        """Return True if the row was already successfully converted."""
        return str(row_id) in self._done

    def is_failed(self, row_id: str) -> bool:
        """Return True if the row was previously marked as failed."""
        return str(row_id) in self._failed

    def clear_failed(self) -> None:
        """Remove all failed entries so they will be retried on next run."""
        self._failed.clear()
        self._touch()

    def save(self) -> None:
        """Persist state to disk atomically."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "done": sorted(self._done),
            "failed": sorted(self._failed),
            "last_updated": self._last_updated or self._now(),
        }
        # Write to a temp file then rename for atomicity
        tmp = self._state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._state_file)

    def load(self) -> None:
        """Load state from disk. Silent no-op if the file does not exist yet."""
        if not self._state_file.exists():
            return
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            self._done = set(raw.get("done", []))
            self._failed = set(raw.get("failed", []))
            self._last_updated = raw.get("last_updated")
        except (json.JSONDecodeError, OSError) as exc:
            # Corrupt state file — start fresh, but warn
            print(f"[BatchState] Warning: could not load state from {self._state_file}: {exc}")
            self._done = set()
            self._failed = set()
            self._last_updated = None

    def stats(self) -> dict:
        """Return a summary dict.

        Keys:
            total_done      — number of successfully converted rows
            total_failed    — number of rows marked as failed
            last_updated    — ISO-8601 timestamp of last mutation, or None
        """
        return {
            "total_done": len(self._done),
            "total_failed": len(self._failed),
            "last_updated": self._last_updated,
        }

    # ------------------------------------------------------------------
    # Convenience / context-manager support
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"BatchState(done={s['total_done']}, failed={s['total_failed']}, "
            f"file={self._state_file})"
        )

    def __enter__(self) -> "BatchState":
        self.load()
        return self

    def __exit__(self, *_) -> None:
        self.save()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _touch(self) -> None:
        self._last_updated = self._now()


# ---------------------------------------------------------------------------
# CLI — quick smoke-test / inspection
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect or reset BatchState")
    parser.add_argument("--state-file", type=Path, default=_DEFAULT_STATE_FILE)
    parser.add_argument("--stats", action="store_true", help="Print stats and exit")
    parser.add_argument("--clear-failed", action="store_true", help="Clear failed set")
    args = parser.parse_args()

    state = BatchState(args.state_file)
    state.load()

    if args.clear_failed:
        state.clear_failed()
        state.save()
        print("Cleared failed entries.")

    print(state)
    print(json.dumps(state.stats(), indent=2))
