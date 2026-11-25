from numwords import normalise, words_to_digits


def test_normalise_forms():
    assert normalise("85,000 / 85000 / 85K / 72% in 2026") == {"85000", "72"}


def test_normalise_millions_and_decimals():
    assert normalise("1.5M jobs, 2.5 times") == {"1500000", "2.5"}


def test_words_to_digits():
    assert words_to_digits(["eighty-five", "thousand", "people"]) == ["85000", "people"]
    assert words_to_digits(["seventy-two", "percent"]) == ["72", "percent"]
    assert words_to_digits(["one", "million", "jobs"]) == ["1000000", "jobs"]
    assert words_to_digits(["two", "hundred", "fifty"]) == ["250"]


def test_words_to_digits_leaves_other_words():
    assert words_to_digits(["learn", "how", "ai", "works"]) == ["learn", "how", "ai", "works"]


def test_normalise_billion_suffixes_and_scale_words():
    assert normalise("$40bn, 9B, $1.5B, 85 thousand, 1.5 million, 20mn") == {
        "40000000000", "9000000000", "1500000000", "85000", "1500000", "20000000"}


def test_words_to_digits_point_and_digit_scale():
    assert words_to_digits(["one", "point", "five", "million"]) == ["1500000"]
    assert words_to_digits(["85", "thousand", "jobs"]) == ["85000", "jobs"]
    assert words_to_digits(["1.5", "million"]) == ["1500000"]
