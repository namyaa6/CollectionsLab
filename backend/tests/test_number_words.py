import pytest

from backend.eval.number_words import words_to_int


@pytest.mark.parametrize("words,expected", [
    ("sixty five thousand two hundred", 65200),
    ("one lakh four thousand nine hundred two", 104902),
    ("two lakh", 200000),
    ("a hundred", 100),
    ("a thousand", 1000),
    ("three hundred and fifty", 350),
    ("twelve thousand", 12000),
    ("one crore", 10_000_000),
    ("seventy eight", 78),
    ("zero", 0),
])
def test_valid(words, expected):
    assert words_to_int(words.split()) == expected


@pytest.mark.parametrize("words", ["five six", "twenty thirty", "hundred hundred", "banana", "and", ""])
def test_nonsense_is_none(words):
    assert words_to_int(words.split()) is None
