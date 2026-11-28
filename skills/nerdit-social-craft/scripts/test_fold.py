from fold import FOLD, feed_window, fold_errors

LONG = ("Every Python beginner who installs packages globally ends up with a broken project on the day two of their "
        "projects need different versions.")   # 140 characters, one sentence


def test_folds_are_instagram_125_and_linkedin_140():
    assert FOLD == {"instagram": 125, "linkedin": 140}


def test_long_first_sentence_is_cut():
    assert len(LONG) == 140
    assert fold_errors(LONG, "instagram", "instagram") == [
        "instagram: first sentence is 140 characters; the feed cuts at 125"]


def test_nothing_concrete_before_the_cut():
    assert fold_errors("Most beginners install packages globally. Save this.", "instagram", "instagram") == [
        "instagram: nothing concrete before the cut (a number or a name like Python or Excel)"]


def test_name_counts_as_concrete():
    assert fold_errors("Most beginners install Python packages globally.", "instagram", "instagram") == []


def test_other_platforms_have_no_fold():
    assert fold_errors(LONG, "facebook", "facebook") == []


def test_link_is_not_the_first_sentence():
    assert fold_errors("https://nerdit.in/x\nSave 2 hours with Excel.", "linkedin", "linkedin") == []


def test_feed_window_is_the_first_fold_characters():
    assert feed_window(LONG, "instagram") == LONG[:125]
