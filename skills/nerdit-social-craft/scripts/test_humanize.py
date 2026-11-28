from humanize import clean, main, slop_errors


def test_em_dash_is_an_error():
    assert slop_errors("A venv keeps packages apart — always.", "instagram") == [
        "instagram: em dash; use a comma or a full stop"]


def test_en_dash_is_an_error():
    assert slop_errors("Lessons 1–4 are free.", "facebook") == ["facebook: en dash; use a hyphen"]


def test_invisible_character_is_an_error():
    assert slop_errors("Save​this", "facebook") == ["facebook: invisible character ZERO WIDTH SPACE (delete it)"]


def test_stock_word_names_the_plain_word():
    assert slop_errors("Unlock your Excel skills.", "linkedin") == ["linkedin: stock word 'unlock' (say 'get')"]


def test_cut_word_says_cut_it():
    assert slop_errors("Notably, Python is free.", "linkedin") == ["linkedin: stock word 'notably' (cut it)"]


def test_phrase_matches_before_its_word():
    assert slop_errors("Let us delve into pandas.", "linkedin") == ["linkedin: stock word 'delve into' (say 'look at')"]


def test_structure_is_flagged_with_its_fix():
    errs = slop_errors("It's not just a tool, it's a habit.", "linkedin")
    assert len(errs) == 1 and errs[0].startswith("linkedin: \"It's not just X, it's Y\"")


def test_nerdit_keeps_tech_words():
    assert slop_errors("The Python ecosystem is robust.", "linkedin") == []


def test_links_and_hashtags_are_ignored():
    assert slop_errors("Free lesson: https://nerdit.in/journey?utm_source=x #journey", "facebook") == []


def test_roman_hinglish_caption_passes():
    assert slop_errors("Aaj venv seekho, har project ka folder alag rakho. Save karo, link in bio.", "instagram") == []


def test_clean_fixes_dash_and_word():
    assert clean("We leverage venv — always.")[0] == "We use venv, always."


def test_cli_fix_prints_clean_text(tmp_path, capsys):
    f = tmp_path / "c.txt"
    f.write_text("We leverage venv — always.", encoding="utf-8")
    assert main([str(f), "--fix"]) == 0
    assert capsys.readouterr().out.strip() == "We use venv, always."
