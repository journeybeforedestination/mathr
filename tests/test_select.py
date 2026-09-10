"""Which questions come first: the deck ordered by where his time goes."""

import random

from mathr.domain.facts import LEVELS_BY_ID, shuffled
from mathr.domain.round import WEIGHT_CEILING, Tally, _weights, new_round

LEVEL = LEVELS_BY_ID["big"]  # 5.0 seconds a part


def keys(level=LEVEL):
    return [fact.key for fact in level.facts]


def history(**by_key):
    """A record of one answer per fact, at the given number of seconds."""
    return {key: Tally(right=1, answered=1, seconds=seconds) for key, seconds in by_key.items()}


def rank(key, seed, weights):
    deck = shuffled(LEVEL.facts, random.Random(seed), weights)
    return next(index for index, question in enumerate(deck) if question.key == key)


def test_a_slow_fact_is_asked_earlier_than_a_fast_one():
    slow, fast = keys()[0], keys()[1]
    weights = _weights(LEVEL, history(**{slow: 20.0, fast: 1.0}))
    ahead = sum(rank(slow, seed, weights) < rank(fast, seed, weights) for seed in range(40))
    assert ahead > 30


def test_an_unseen_fact_is_not_starved():
    """45 of 76 facts have been answered exactly once: there is no verdict to
    pass on them yet, so they weigh the same as an on-pace fact."""
    slow = keys()[0]
    weights = _weights(LEVEL, history(**{slow: 20.0}))
    unseen = keys()[1]
    assert unseen not in weights
    assert min(rank(unseen, seed, weights) for seed in range(40)) < 10


def test_one_bad_morning_cannot_take_over_the_deck():
    stall = _weights(LEVEL, history(**{keys()[0]: 23.6}))
    assert stall[keys()[0]] == WEIGHT_CEILING


def test_an_unweighted_deck_is_exactly_what_it_always_was():
    """Every seeded test in the suite depends on this: the flat shuffle
    interleaves the orientation flip with the sample, so restructuring it moves
    which questions are flipped as well as their order."""
    assert shuffled(LEVEL.facts, random.Random(7)) == shuffled(LEVEL.facts, random.Random(7), None)
    assert new_round(LEVEL, random.Random(7)).deck == shuffled(LEVEL.facts, random.Random(7))


def test_no_history_means_no_weighting():
    assert new_round(LEVEL, random.Random(7), history={}).deck == shuffled(
        LEVEL.facts, random.Random(7)
    )


def test_the_whole_pool_is_still_in_the_deck():
    weights = _weights(LEVEL, history(**{keys()[0]: 20.0}))
    deck = shuffled(LEVEL.facts, random.Random(1), weights)
    assert sorted(question.key for question in deck) == sorted(keys())
