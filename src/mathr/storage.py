"""Progress on disk. The only I/O in the core.

New fields are read through `.get` with defaults, so a file written by an
earlier version still loads. `Fact.key` is unchanged, which is why this needs
no `version` bump: the warning in plan.md is about the key format, not about
adding fields beside it.
"""

import json
import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

from .domain.round import Round, Tally

VERSION = 1


@dataclass(frozen=True)
class Settings:
    sound: bool = True
    timer: bool = True


@dataclass(frozen=True)
class LevelRecord:
    launches: int = 0  # timed
    practice: int = 0  # untimed
    failures: int = 0
    best_seconds: float | None = None


@dataclass(frozen=True)
class Progress:
    levels: Mapping[str, LevelRecord] = field(default_factory=dict)
    facts: Mapping[str, Tally] = field(default_factory=dict)
    settings: Settings = Settings()

    def level(self, level_id: str) -> LevelRecord:
        return self.levels.get(level_id, LevelRecord())


def default_path() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(data_home) / "mathr" / "progress.json"


def load(path: Path) -> Progress:
    """A missing or damaged file reads as no progress, never as an exception."""
    try:
        raw = json.loads(path.read_text())
        settings = raw.get("settings", {})
        return Progress(
            levels={
                str(key): LevelRecord(
                    launches=int(value.get("launches", 0)),
                    practice=int(value.get("practice", 0)),
                    failures=int(value.get("failures", 0)),
                    best_seconds=(
                        None if value.get("best_seconds") is None else float(value["best_seconds"])
                    ),
                )
                for key, value in raw["levels"].items()
            },
            facts={
                str(key): Tally(
                    right=int(value["right"]),
                    wrong=int(value["wrong"]),
                    answered=int(value.get("answered", 0)),
                    seconds=float(value.get("seconds", 0.0)),
                )
                for key, value in raw["facts"].items()
            },
            settings=Settings(
                sound=bool(settings.get("sound", True)),
                timer=bool(settings.get("timer", True)),
            ),
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return Progress()


def save(path: Path, progress: Progress) -> None:
    """Write through a temp file in the same directory, then replace.

    He will close the window mid-write, and a truncated progress.json is the
    one bug guaranteed to end use of the program.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": VERSION,
        "settings": {"sound": progress.settings.sound, "timer": progress.settings.timer},
        "levels": {
            level: {
                "launches": record.launches,
                "practice": record.practice,
                "failures": record.failures,
                "best_seconds": record.best_seconds,
            }
            for level, record in sorted(progress.levels.items())
        },
        "facts": {
            key: {
                "right": tally.right,
                "wrong": tally.wrong,
                "answered": tally.answered,
                "seconds": round(tally.seconds, 2),
            }
            for key, tally in sorted(progress.facts.items())
        },
    }
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(handle, "w") as out:
            json.dump(payload, out, indent=1)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def _fold(record: LevelRecord, round: Round) -> LevelRecord:
    if not round.timed:
        return replace(record, practice=record.practice + round.launched)
    if round.failed:
        return replace(record, failures=record.failures + 1)
    if not round.launched:
        return record
    best = record.best_seconds
    return replace(
        record,
        launches=record.launches + 1,
        best_seconds=round.elapsed if best is None else min(best, round.elapsed),
    )


def merge(progress: Progress, round: Round) -> Progress:
    """Fold a finished round into progress, launched or not.

    Whatever he practised is worth recording even when he walks away
    mid-round; the per-fact tallies are the part that cannot be reconstructed.
    """
    facts = dict(progress.facts)
    for key, tally in round.attempts.items():
        was = facts.get(key, Tally())
        facts[key] = Tally(
            right=was.right + tally.right,
            wrong=was.wrong + tally.wrong,
            answered=was.answered + tally.answered,
            seconds=was.seconds + tally.seconds,
        )
    levels = {**progress.levels, round.level_id: _fold(progress.level(round.level_id), round)}
    return Progress(levels=levels, facts=facts, settings=progress.settings)
