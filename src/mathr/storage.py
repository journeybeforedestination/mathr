"""Progress on disk. The only I/O in the core.

New fields are read through `.get` with defaults, so a file written by an
earlier version still loads. `Fact.key` is unchanged and needs no bump for
that reason; `version` is 2 because the *level* key changed shape, from
`<level>` to `<mode>/<level>`, which is a different format.

Four sections: `levels`, `facts`, `placements` and `targets`. The last two are
both about placing a number on a line and are still kept apart, because
`placements` is bucketed by decade of the line and sorted with `int()` — a
fraction key in there raises inside `save`, which means `os.replace` never runs
and the whole file quietly stops being written.
"""

import json
import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

from .domain.round import Aim, Round, Tally

VERSION = 2


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
    #: Keyed `<mode>/<level>`. One record per level shared by every mode made
    #: the badge on a level card a mixture of three different games, and
    #: `best_seconds` a minimum across clocks that are not comparable.
    levels: Mapping[str, LevelRecord] = field(default_factory=dict)
    facts: Mapping[str, Tally] = field(default_factory=dict)
    placements: Mapping[str, Aim] = field(default_factory=dict)
    #: Keyed by `Target.key` — `2/3|6`. Its own section rather than a corner of
    #: `facts`: two key shapes in one map makes every later reader of the file
    #: disambiguate them, and it costs one dict and no version bump to keep them
    #: apart.
    targets: Mapping[str, Tally] = field(default_factory=dict)
    settings: Settings = Settings()

    def level(self, mode_id: str, level_id: str) -> LevelRecord:
        return self.levels.get(f"{mode_id}/{level_id}", LevelRecord())


def default_path(testing: bool = False) -> Path:
    """Where progress lives, and where it lives when you are only checking.

    A sibling file rather than no file at all: the save path is the one place a
    bug stops the record being written with nothing on screen to say so, so a
    test session has to exercise it — just not against his.
    """
    data_home = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    name = "test-progress.json" if testing else "progress.json"
    return Path(data_home) / "mathr" / name


def load(path: Path) -> Progress:
    """A missing or damaged file reads as no progress, never as an exception."""
    try:
        raw = json.loads(path.read_text())
        settings = raw.get("settings", {})
        # Every level record written before modes were recorded is the rocket's:
        # it is the mode the arcade opens on, and the only one whose badge the
        # level screen ever showed.
        prefix = "rocket/" if int(raw.get("version", 1)) < 2 else ""
        return Progress(
            levels={
                prefix + str(key): LevelRecord(
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
            placements={
                str(key): Aim(attempts=int(value["attempts"]), error=float(value["error"]))
                for key, value in raw.get("placements", {}).items()
            },
            targets={
                str(key): Tally(
                    right=int(value["right"]),
                    wrong=int(value["wrong"]),
                    answered=int(value.get("answered", 0)),
                    seconds=float(value.get("seconds", 0.0)),
                )
                for key, value in raw.get("targets", {}).items()
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
        "placements": {
            bucket: {"attempts": aim.attempts, "error": round(aim.error, 2)}
            for bucket, aim in sorted(progress.placements.items(), key=lambda item: int(item[0]))
        },
        "targets": {
            key: {
                "right": tally.right,
                "wrong": tally.wrong,
                "answered": tally.answered,
                "seconds": round(tally.seconds, 2),
            }
            for key, tally in sorted(progress.targets.items())
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
    # `losable`, not `timed`: what makes a win farmable is having no way to
    # lose, not having no clock. The rocket with the Timer toggle off still has
    # neither, so it still folds to `practice`; the booth has no clock and three
    # lives a blown call spends, so a perfect game there is a launch.
    if not round.losable:
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
    # Routed by what the mode asks, never by sniffing the shape of the key: a
    # fraction row in `placements` raises inside `save` and stops the file being
    # written at all, with nothing on screen to say so.
    facts = dict(progress.facts)
    targets = dict(progress.targets)
    into = targets if round.rules.targets_from_deck else facts
    for key, tally in round.attempts.items():
        was = into.get(key, Tally())
        into[key] = Tally(
            right=was.right + tally.right,
            wrong=was.wrong + tally.wrong,
            answered=was.answered + tally.answered,
            seconds=was.seconds + tally.seconds,
        )
    placements = dict(progress.placements)
    for bucket, aim in round.aims.items():
        was = placements.get(bucket, Aim())
        placements[bucket] = Aim(
            attempts=was.attempts + aim.attempts, error=was.error + aim.error
        )
    key = f"{round.mode_id}/{round.level_id}"
    levels = {**progress.levels, key: _fold(progress.level(round.mode_id, round.level_id), round)}
    return Progress(
        levels=levels,
        facts=facts,
        placements=placements,
        targets=targets,
        settings=progress.settings,
    )
