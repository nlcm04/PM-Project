from app.utils import ordinal


def test_ordinal_basic_cases():
    assert ordinal(1) == "1st"
    assert ordinal(2) == "2nd"
    assert ordinal(3) == "3rd"
    assert ordinal(4) == "4th"


def test_ordinal_teens_are_all_th():
    assert ordinal(11) == "11th"
    assert ordinal(12) == "12th"
    assert ordinal(13) == "13th"


def test_ordinal_larger_numbers():
    assert ordinal(21) == "21st"
    assert ordinal(53) == "53rd"
    assert ordinal(73) == "73rd"
    assert ordinal(93) == "93rd"
    assert ordinal(100) == "100th"
    assert ordinal(111) == "111th"
