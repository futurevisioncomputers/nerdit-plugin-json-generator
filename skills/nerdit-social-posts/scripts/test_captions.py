from captions import caption_errors, fill_links, utm_link

LESSON = "Each project gets its own venv. pip installs 2 packages here. Activate the venv before pip install."
ITEM = {"id": "d01-reel", "date": "2026-11-19"}
URL = "https://nerdit.in/course/course-demo-1/preview"
OK_IG = ("Most beginners install packages globally. A venv keeps each project's packages apart.\n\n"
         "Save this for your next project and share it with a friend. Full lesson free, link in bio.\n#python #fastapi")
OK_LI = ("Installing packages globally is a common beginner mistake. A virtual environment keeps each project's "
         "packages apart, so a project is faster to set up again.\n\nFree lesson: " + utm_link(URL, "linkedin", ITEM)
         + "\n#Python #FastAPI")


def test_utm_link_carries_platform_date_and_item():
    assert utm_link(URL, "facebook", ITEM) == (URL + "?utm_source=facebook&utm_medium=social"
                                               "&utm_campaign=pack-2026-11-19&utm_content=d01-reel")


def test_fill_links_replaces_the_placeholder():
    assert fill_links("Learn: {link}", URL, "linkedin", ITEM) == "Learn: " + utm_link(URL, "linkedin", ITEM)


def test_good_captions_pass():
    assert caption_errors("instagram", "reel", OK_IG, LESSON, ITEM, URL) == []
    assert caption_errors("linkedin", "carousel", OK_LI, LESSON, ITEM, URL) == []


def test_instagram_question_opener_is_refused():
    assert "instagram: open with a claim or a named mistake, not a question" in caption_errors(
        "instagram", "reel", "Why use venv? " + OK_IG, LESSON, ITEM, URL)


def test_instagram_url_is_refused():
    assert "instagram: no links (say 'link in bio')" in caption_errors(
        "instagram", "reel", OK_IG + " https://nerdit.in", LESSON, ITEM, URL)


def test_instagram_too_long_is_refused():
    assert "instagram: 2301 characters; at most 2200" in caption_errors(
        "instagram", "reel", OK_IG + "a" * (2301 - len(OK_IG)), LESSON, ITEM, URL)


def test_instagram_more_than_8_hashtags_is_refused():
    tags = " ".join(f"#tag{c}" for c in "abcdefghi")
    assert "instagram: 11 hashtags; at most 8" in caption_errors("instagram", "reel", OK_IG + " " + tags, LESSON, ITEM, URL)


def test_instagram_needs_a_call_to_action():
    text = "Most beginners install packages globally. A venv keeps them apart. Full lesson free, link in bio."
    assert "instagram: add a call to action (comment, save or share)" in caption_errors(
        "instagram", "reel", text, LESSON, ITEM, URL)


def test_instagram_needs_link_in_bio():
    assert "instagram: say 'link in bio'" in caption_errors(
        "instagram", "reel", OK_IG.replace("link in bio", "see the site"), LESSON, ITEM, URL)


def test_number_not_in_lesson_is_refused():
    assert "linkedin: 40% is not in the lesson" in caption_errors(
        "linkedin", "carousel", OK_LI.replace("faster", "40% faster"), LESSON, ITEM, URL)


def test_numbers_from_the_lesson_years_and_link_digits_are_allowed():
    assert caption_errors("linkedin", "carousel", OK_LI.replace("mistake.", "mistake in 2026: pip installs 2 packages."),
                          LESSON, ITEM, URL) == []


def test_facebook_needs_its_utm_link():
    assert caption_errors("facebook", "reel", "Learn venv " + utm_link(URL, "facebook", ITEM), LESSON, ITEM, URL) == []
    assert caption_errors("facebook", "reel", "Learn venv", LESSON, ITEM, URL) == [
        "facebook: needs the course link " + utm_link(URL, "facebook", ITEM)]


def test_facebook_more_than_5_hashtags_is_refused():
    text = "Learn venv " + utm_link(URL, "facebook", ITEM) + " #a #b #c #d #e #f"
    assert caption_errors("facebook", "reel", text, LESSON, ITEM, URL) == ["facebook: 6 hashtags; at most 5"]


def test_linkedin_too_long_is_refused():
    assert "linkedin: 3001 characters; at most 3000" in caption_errors(
        "linkedin", "feed", OK_LI + "a" * (3001 - len(OK_LI)), LESSON, ITEM, URL)


def test_linkedin_more_than_5_hashtags_is_refused():
    assert "linkedin: 7 hashtags; at most 5" in caption_errors(
        "linkedin", "feed", OK_LI + " #a #b #c #d #e", LESSON, ITEM, URL)


def test_linkedin_devanagari_is_refused():
    assert "linkedin: English only (no Devanagari)" in caption_errors(
        "linkedin", "feed", OK_LI + " सीखो", LESSON, ITEM, URL)


def test_linkedin_link_with_the_wrong_source_is_refused():
    wrong = OK_LI.replace("utm_source=linkedin", "utm_source=instagram")
    assert "linkedin: needs the course link " + utm_link(URL, "linkedin", ITEM) in caption_errors(
        "linkedin", "feed", wrong, LESSON, ITEM, URL)


def test_empty_caption_on_a_post_is_refused():
    assert caption_errors("instagram", "reel", "  ", LESSON, ITEM, URL) == ["instagram: caption is empty"]


def test_story_caption_must_be_empty():
    assert caption_errors("instagram", "story", "hi", LESSON, ITEM, URL) == ["instagram: Stories take no caption"]
    assert caption_errors("facebook", "story", "", LESSON, ITEM, URL) == []


def test_a_number_must_match_a_whole_lesson_number():
    lesson = "Run 15 requests and 40 tests."
    text = OK_LI.replace("mistake.", "mistake: 5 requests fail.")
    assert caption_errors("linkedin", "feed", text, lesson, ITEM, URL) == ["linkedin: 5 is not in the lesson"]
    assert caption_errors("linkedin", "feed", OK_LI.replace("faster", "40% faster"), lesson, ITEM, URL) == []


# ---- Pinterest (design: nerdit docs/superpowers/specs/2026-11-22-pinterest-posting-design.md) ----
PIN = ("Python virtual environments for beginners\n\n"
       "Each project gets its own venv, so packages never clash. Activate the venv before pip install.")


def test_a_story_takes_a_pinterest_caption_but_instagram_still_takes_none():
    assert caption_errors("pinterest", "story", PIN, LESSON, ITEM, URL) == []
    assert caption_errors("instagram", "story", PIN, LESSON, ITEM, URL) == ["instagram: Stories take no caption"]
    assert caption_errors("pinterest", "carousel", PIN, LESSON, ITEM, URL) == []
    assert caption_errors("pinterest", "story", "", LESSON, ITEM, URL) == ["pinterest: caption is empty"]


def test_pinterest_caption_rules():
    e = lambda t: caption_errors("pinterest", "feed", t, LESSON, ITEM, URL)  # noqa: E731
    assert "pinterest: first line is the title; it is empty" in e("\n\nEach project gets its own venv.")
    assert "pinterest: title is 101 characters; at most 100" in e("x" * 101 + "\n\nwords")
    assert "pinterest: description is 801 characters; at most 800" in e("Title\n\n" + "y" * 801)
    assert "pinterest: no link (the pin carries it)" in e("Title\n\nSee https://nerdit.in/x")
    assert "pinterest: English only (no Devanagari)" in e("Title\n\nयह venv है")
    assert "pinterest: 6 hashtags; at most 5" in e("Title\n\nwords #a #b #c #d #e #f")
    assert "pinterest: 7 is not in the lesson" in e("Title\n\n7 packages")
