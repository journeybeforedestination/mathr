import json
import random

from mathr.domain.facts import LEVELS_BY_ID
from mathr.domain.round import PARTS_TO_LAUNCH, Tally, apply, new_round, tick
from mathr.storage import LevelRecord, Progress, Settings, load, merge, save


def played(level_id="fives", timed=True, corrects=0, wrongs=0, seconds=0.0):
    current = new_round(LEVELS_BY_ID[level_id], random.Random(0), timed=timed)
    if seconds:
        current, _ = tick(current, seconds)
    for _ in range(wrongs):
        current, _ = apply(current, current.current.answer + 1)
    for _ in range(corrects):
        current, _ = apply(current, current.current.answer)
    return current


def test_round_trip(tmp_path):
    path = tmp_path / "progress.json"
    progress = Progress(
        levels={"fives": LevelRecord(launches=3, practice=1, failures=2, best_seconds=41.5)},
        facts={"3+2=5@b": Tally(4, 1, 5, 18.25)},
        settings=Settings(sound=False, timer=True),
    )
    save(path, progress)
    assert load(path) == progress


def test_missing_file_is_empty_progress(tmp_path):
    assert load(tmp_path / "nope.json") == Progress()


def test_corrupt_file_is_empty_progress(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text('{"version": 1, "levels": {"fi')
    assert load(path) == Progress()


def test_unexpected_shape_is_empty_progress(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text('{"version": 1}')
    assert load(path) == Progress()


def test_a_file_from_before_the_clock_still_loads(tmp_path):
    """The v1 shape, written before response times or settings existed."""
    path = tmp_path / "progress.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "levels": {"fives": {"launches": 3}},
                "facts": {"3+2=5@b": {"right": 4, "wrong": 1}},
            }
        )
    )
    progress = load(path)
    assert progress.level("fives") == LevelRecord(launches=3)
    assert progress.facts["3+2=5@b"] == Tally(right=4, wrong=1, answered=0, seconds=0.0)
    assert progress.settings == Settings(sound=True, timer=True)


def test_save_leaves_no_temp_files(tmp_path):
    path = tmp_path / "progress.json"
    save(path, Progress(levels={"tens": LevelRecord(launches=1)}))
    save(path, Progress(levels={"tens": LevelRecord(launches=2)}))
    assert [p.name for p in tmp_path.iterdir()] == ["progress.json"]


def test_save_creates_the_directory(tmp_path):
    path = tmp_path / "mathr" / "progress.json"
    save(path, Progress())
    assert load(path) == Progress()


def test_merge_accumulates_fact_tallies():
    finished = played(corrects=1)
    key = next(iter(finished.attempts))
    after = merge(Progress(facts={key: Tally(4, 1, 5, 12.0)}), finished)
    tally = after.facts[key]
    assert (tally.right, tally.wrong, tally.answered) == (5, 1, 6)


def test_a_launch_records_launch_and_best_time():
    finished = played(corrects=PARTS_TO_LAUNCH, seconds=2.5)
    after = merge(Progress(), finished)
    record = after.level("fives")
    assert record.launches == 1 and record.failures == 0
    assert record.best_seconds == finished.elapsed


def test_best_time_only_improves():
    before = Progress(levels={"fives": LevelRecord(launches=1, best_seconds=20.0)})
    after = merge(before, played(corrects=PARTS_TO_LAUNCH, seconds=25.0))
    assert after.level("fives").best_seconds == 20.0


def test_abduction_records_a_failure_and_no_best_time():
    current = played(corrects=2)
    current, _ = tick(current, 999)
    after = merge(Progress(), current)
    assert after.level("fives") == LevelRecord(failures=1)


def test_untimed_launches_are_counted_apart():
    after = merge(Progress(), played(timed=False, corrects=PARTS_TO_LAUNCH))
    assert after.level("fives") == LevelRecord(launches=0, practice=1, best_seconds=None)


def test_walking_away_records_facts_but_no_launch():
    after = merge(Progress(), played(corrects=3))
    assert after.level("fives") == LevelRecord()
    assert sum(t.answered for t in after.facts.values()) == 3


def test_settings_survive_a_merge():
    before = Progress(settings=Settings(sound=False, timer=False))
    assert merge(before, played(corrects=1)).settings == before.settings
