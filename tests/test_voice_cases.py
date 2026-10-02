"""M25: consistency checks for the fake voice sentences (tests/voice_cases.py).

These don't measure anything. They make sure the scoring tags match their sentences, so a typo in
a tag can't quietly turn a correct transcript into a "wrong name" or a "wrong number" in M25's results.
"""

import re

from voice_cases import ANSWERS, V1, V2, V3, V4

SPOKEN = V1 + V2 + V3


def test_group_sizes_match_the_plan() -> None:
    assert (len(V1), len(V2), len(V3), len(V4), len(ANSWERS)) == (8, 10, 8, 4, 6)


def test_every_tag_appears_as_a_whole_word_in_its_sentence() -> None:
    for case in SPOKEN:
        for tag in case["names"] + case["numbers"]:
            assert re.search(rf"(?<!\w){re.escape(tag)}(?!\w)", case["text"]), (tag, case["text"])


def test_names_live_only_in_v2_and_numbers_only_in_v3() -> None:
    assert all(case["names"] for case in V2)
    assert not any(case["names"] for case in V1 + V3)
    assert not any(case["numbers"] for case in V1 + V2)
    assert sum(len(case["numbers"]) for case in V3) == 8


def test_scored_names_are_capitalized_words_not_initials() -> None:
    for case in V2:
        for name in case["names"]:
            assert len(name) >= 2 and name[0].isupper() and name.isalpha(), name


def test_no_sentence_is_used_twice() -> None:
    texts = [case["text"] for case in SPOKEN]
    assert len(set(texts)) == len(texts)


def test_answers_are_100_to_600_characters_and_two_are_about_300() -> None:
    assert all(100 <= len(answer) <= 600 for answer in ANSWERS)
    assert sum(250 <= len(answer) <= 350 for answer in ANSWERS) >= 2


def test_non_speech_clips_are_fully_described() -> None:
    for clip in V4:
        assert clip["seconds"] > 0
        assert clip["level_dbfs"] is None or clip["level_dbfs"] < 0
    assert [clip["name"] for clip in V4] == ["silence", "noise", "hum", "clicks"]
