import json
import random

from mathr.domain.facts import LEVELS_BY_ID
from mathr.domain.round import (
    CODE,
    CURLING,
    FOOTBALL,
    LINES_TO_CRACK,
    PARTS_TO_LAUNCH,
    STONES,
    TENNIS,
    Aim,
    Tally,
    apply,
    new_round,
    place,
    tick,
)
from mathr.storage import LevelRecord, Progress, Settings, load, merge, save


def played(level_id="fives", timed=True, corrects=0, wrongs=0, seconds=0.0, **kwargs):
    current = new_round(LEVELS_BY_ID[level_id], random.Random(0), timed=timed, **kwargs)
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
        levels={"rocket/fives": LevelRecord(launches=3, practice=1, failures=2, best_seconds=41.5)},
        facts={"3+2=5@b": Tally(4, 1, 5, 18.25)},
        placements={"30": Aim(attempts=4, error=21.5)},
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
    assert progress.level("rocket", "fives") == LevelRecord(launches=3)
    assert progress.facts["3+2=5@b"] == Tally(right=4, wrong=1, answered=0, seconds=0.0)
    assert progress.settings == Settings(sound=True, timer=True)


def test_save_leaves_no_temp_files(tmp_path):
    path = tmp_path / "progress.json"
    save(path, Progress(levels={"rocket/tens": LevelRecord(launches=1)}))
    save(path, Progress(levels={"rocket/tens": LevelRecord(launches=2)}))
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
    record = after.level("rocket", "fives")
    assert record.launches == 1 and record.failures == 0
    assert record.best_seconds == finished.elapsed


def test_best_time_only_improves():
    before = Progress(levels={"rocket/fives": LevelRecord(launches=1, best_seconds=20.0)})
    after = merge(before, played(corrects=PARTS_TO_LAUNCH, seconds=25.0))
    assert after.level("rocket", "fives").best_seconds == 20.0


def test_abduction_records_a_failure_and_no_best_time():
    current = played(corrects=2)
    current, _ = tick(current, 999)
    after = merge(Progress(), current)
    assert after.level("rocket", "fives") == LevelRecord(failures=1)


def test_untimed_launches_are_counted_apart():
    """The Timer toggle must not make the number that means "I beat it"
    farmable: with no clock the rocket has no way to lose either."""
    after = merge(Progress(), played(timed=False, corrects=PARTS_TO_LAUNCH))
    assert after.level("rocket", "fives") == LevelRecord(launches=0, practice=1, best_seconds=None)


def test_a_code_win_is_a_launch_though_it_has_no_clock():
    """`_fold` asks whether the round was losable, not whether it was timed. The
    code cabinet has three alarms a wrong answer trips, so its win is not
    farmable the way an untimed rocket launch would be."""
    current = new_round(
        LEVELS_BY_ID["tens"], random.Random(0), timed=False, rules=CODE, mode_id="code"
    )
    while not current.over:
        current, _ = apply(current, current.current.answer)
    assert current.parts == LINES_TO_CRACK
    after = merge(Progress(), current)
    assert after.level("code", "tens").launches == 1
    assert after.level("code", "tens").practice == 0


def test_walking_away_records_facts_but_no_launch():
    after = merge(Progress(), played(corrects=3))
    assert after.level("rocket", "fives") == LevelRecord()
    assert sum(t.answered for t in after.facts.values()) == 3


def test_settings_survive_a_merge():
    before = Progress(settings=Settings(sound=False, timer=False))
    assert merge(before, played(corrects=1)).settings == before.settings


# --- modes keep their own records -------------------------------------------


def test_a_v1_record_migrates_under_the_rocket(tmp_path):
    """Rocket is the guess: it is the mode the arcade opens on, and the only
    one whose badge a v1 level card ever showed."""
    path = tmp_path / "progress.json"
    path.write_text(
        json.dumps({"version": 1, "levels": {"fives": {"launches": 3}}, "facts": {}})
    )
    assert set(load(path).levels) == {"rocket/fives"}


def test_a_rocket_win_and_a_tennis_win_are_separate_records():
    after = merge(Progress(), played(corrects=PARTS_TO_LAUNCH))
    tennis = new_round(LEVELS_BY_ID["fives"], random.Random(0), rules=TENNIS, mode_id="tennis")
    for _ in range(TENNIS.target):
        tennis, _ = apply(tennis, tennis.current.answer)
    after = merge(after, tennis)
    assert after.level("rocket", "fives").launches == 1
    assert after.level("tennis", "fives").launches == 1


def test_placements_accumulate_by_bucket():
    drive = new_round(
        LEVELS_BY_ID["fives"], random.Random(0), rules=FOOTBALL, mode_id="football"
    )
    target = drive.placing
    drive, _ = place(drive, target + 2)
    bucket = str(target // 10 * 10)
    after = merge(Progress(placements={bucket: Aim(attempts=1, error=5.0)}), drive)
    assert after.placements[bucket] == Aim(attempts=2, error=7.0)


def test_a_v2_file_without_placements_loads_empty(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text(json.dumps({"version": 2, "levels": {}, "facts": {}}))
    assert load(path).placements == {}


# --- fractions keep their own section ----------------------------------------


def curled(level_id="thirds", stones=1, wide=False):
    current = new_round(
        LEVELS_BY_ID[level_id],
        random.Random(0),
        timed=False,
        rules=CURLING,
        mode_id="curling",
    )
    for _ in range(stones):
        off = current.current.tolerance + 1 if wide else 0
        current, _ = place(current, current.current.value + off)
    return current


def test_a_stone_is_recorded_under_targets_and_never_under_facts():
    round = curled()
    after = merge(Progress(), round)
    assert set(after.facts) == set()
    assert set(after.targets) == set(round.attempts)
    assert next(iter(after.targets)).count("/") == 1


def test_target_rows_accumulate_across_ends():
    after = merge(Progress(), curled())
    key = next(iter(after.targets))
    again = merge(after, curled())
    assert again.targets[key].answered == 2


def test_a_football_round_still_writes_its_aims_by_bucket():
    drive = new_round(
        LEVELS_BY_ID["fives"], random.Random(0), rules=FOOTBALL, mode_id="football"
    )
    drive, _ = place(drive, drive.placing)
    after = merge(Progress(), drive)
    assert after.targets == {}
    assert [int(bucket) for bucket in after.placements]


def test_targets_round_trip(tmp_path):
    path = tmp_path / "progress.json"
    progress = Progress(targets={"2/3|6": Tally(3, 1, 4, 12.5)})
    save(path, progress)
    assert load(path) == progress


def test_a_file_from_before_the_stones_still_loads(tmp_path):
    """The section is additive, which is why `Fact.key` and the level key are
    both untouched and `VERSION` does not move."""
    path = tmp_path / "progress.json"
    path.write_text(json.dumps({"version": 2, "levels": {}, "facts": {}}))
    assert load(path).targets == {}


def test_a_won_end_is_a_launch_though_it_has_no_clock():
    round = curled(stones=STONES)
    after = merge(Progress(), round)
    assert after.level("curling", "thirds").launches == 1
    assert after.level("curling", "thirds").practice == 0
