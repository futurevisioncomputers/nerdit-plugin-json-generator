import json
import os
import subprocess
import sys

import pytest

from check_sequence import (
    build_ownership, code_text, concepts_in_title, constructs_declared, find_violations,
    identifier_families_in_title, identifiers, load_manifests,
)

SCRIPT = os.path.join(os.path.dirname(__file__), "check_sequence.py")


def _pre(code, lang="python"):
    return f'<pre data-lang="{lang}"><code>{code}</code></pre>'


PY_COURSE = [
    {"id": "l1", "title": "Variables and Values",
     "description": "Store data in a name you choose."},
    {"id": "l2", "title": "Conditions with if",
     "description": "Run code only when a test is true."},
    {"id": "l3", "title": "Loops and Iteration",
     "description": "Repeat work over every item in a list."},
]


def test_loop_before_the_loops_lesson_is_flagged():
    # The reported bug: a loop example lands in the conditions lesson.
    content = {"l2": _pre("for name in names:\n    print(name)")}
    v = find_violations(PY_COURSE, content)
    assert [(x[1], x[2], x[3]) for x in v] == [("l2", "for", 2)]


def test_taught_construct_in_its_own_lesson_passes():
    content = {"l3": _pre("for name in names:\n    print(name)")}
    assert find_violations(PY_COURSE, content) == []


def test_earlier_construct_in_later_lesson_passes():
    # `if` belongs to lesson 2, so lesson 3 may use it freely.
    content = {"l3": _pre("for n in nums:\n    if n > 2:\n        print(n)")}
    assert find_violations(PY_COURSE, content) == []


def test_named_api_owned_by_later_lesson_is_flagged():
    course = [
        {"id": "p", "title": "Prompt Templates",
         "description": "Design prompts with PromptTemplate."},
        {"id": "c", "title": "Chains and Sequential Workflows",
         "description": "Compose steps with LLMChain and LCEL."},
    ]
    content = {"p": _pre('chain = LLMChain(llm=model, prompt=prompt)')}
    v = find_violations(course, content)
    assert [(x[1], x[2], x[3]) for x in v] == [("p", "LLMChain", 1)]


def test_identifier_named_in_own_description_is_not_flagged():
    course = [
        {"id": "p", "title": "Prompt Templates",
         "description": "Use PromptTemplate to build prompts."},
        {"id": "c", "title": "Chains", "description": "PromptTemplate feeds an LLMChain."},
    ]
    # PromptTemplate is also named by the later lesson, but lesson 1 owns it by first
    # mention and names it itself.
    assert find_violations(course, {"p": _pre("t = PromptTemplate(x)")}) == []


def test_prose_forward_reference_outside_pre_is_allowed():
    content = {"l2": "<p>You will learn <em>for</em> loops in a later lesson.</p>"
                     + _pre("if age > 18:\n    print('adult')")}
    assert find_violations(PY_COURSE, content) == []


def test_english_prose_inside_pre_is_not_a_for_loop():
    # A bare-word search would read "code for beginners" as a loop.
    assert find_violations(PY_COURSE, {"l1": _pre("example code for beginners")}) == []


def test_string_literals_are_not_api_usage():
    course = [
        {"id": "a", "title": "NLP Fundamentals", "description": "Tokens and embeddings."},
        {"id": "b", "title": "Vector Databases", "description": "Store vectors in FAISS."},
    ]
    # A prompt list mentioning FAISS is prose the code carries, not a use of FAISS.
    prose = _pre('prompts = ["What is FAISS?", "Define embeddings."]')
    assert find_violations(course, {"a": prose}) == []
    # An import of it is.
    real = _pre("from langchain_community.vectorstores import FAISS")
    assert [x[2] for x in find_violations(course, {"a": real})] == ["FAISS"]


def test_docstrings_are_not_api_usage():
    course = [
        {"id": "a", "title": "Python Foundations", "description": "Async and typing."},
        {"id": "b", "title": "Chains and Workflows", "description": "Compose LLMChain."},
    ]
    doc = _pre('def go():\n    """Async invocation of an LLMChain chain."""\n    return 1')
    assert find_violations(course, {"a": doc}) == []


def test_sql_string_values_do_not_hide_real_keywords():
    # Stripping 'Surat' must not disturb the surrounding SQL.
    course = [
        {"id": "s1", "title": "Filtering Rows", "description": "Keep only some rows."},
        {"id": "s2", "title": "Grouping with GROUP BY", "description": "Group rows."},
    ]
    html = _pre("SELECT city FROM customers WHERE city = 'Surat' GROUP BY city;", "sql")
    assert [x[2] for x in find_violations(course, {"s1": html})] == ["GROUP BY"]


def test_comments_are_stripped_before_matching():
    content = {"l1": _pre("x = 1  # a for loop would go here\n-- and here")}
    assert find_violations(PY_COURSE, content) == []


def test_output_block_text_is_not_scanned():
    html = (_pre("print(total)")
            + '<div class="nerdit-output"><div class="nerdit-output-label">Output</div>'
              "<pre><code>for each city we printed one row</code></pre></div></div>")
    assert find_violations(PY_COURSE, {"l1": html}) == []


def test_code_text_decodes_entities_and_drops_tags():
    out = code_text(_pre("if x &lt; 3:\n    print(x)"))
    assert "if x < 3:" in out
    assert "<code>" not in out


def test_identifiers_skips_generic_acronyms_and_plain_words():
    found = identifiers("Call the API and parse JSON with LLMChain and FAISS")
    assert found == {"LLMChain", "FAISS"}


def test_concepts_from_title_only_not_description():
    assert "for" in concepts_in_title("Loops and Iteration")
    assert concepts_in_title("Reading Files Safely").get("open()")
    # A description mentioning conditions must not hand `if` to this lesson.
    _, constructs = build_ownership(
        [{"id": "a", "title": "Exceptions", "description": "handle error conditions"}])
    assert "if" not in constructs


HTTP_COURSE = [
    {"id": "h1", "title": "HTTP Methods in FastAPI", "description": "HTTP Methods in FastAPI"},
    {"id": "h2", "title": "POST Request Body", "description": "POST Request Body"},
    {"id": "h3", "title": "PUT & DELETE", "description": "PUT & DELETE"},
]


def test_title_family_claims_names_it_never_spells_out():
    # "HTTP Methods" owns POST even though only lesson 2's title says POST.
    assert identifier_families_in_title("HTTP Methods in FastAPI") >= {"GET", "POST", "DELETE"}
    content = {"h1": _pre("POST   /bookmarks\nDELETE /bookmarks/{id}", "http")}
    assert find_violations(HTTP_COURSE, content) == []


def test_family_ownership_still_flags_lessons_before_the_owner():
    course = [{"id": "h0", "title": "What is an API?", "description": "What is an API?"}] \
        + HTTP_COURSE
    v = find_violations(course, {"h0": _pre("POST /v1/predict HTTP/1.1", "http")})
    assert [(x[1], x[2], x[3]) for x in v] == [("h0", "POST", 1)]


PANDAS_COURSE = [
    {"id": "p1", "title": "Introduction to Pandas", "description": "Why Pandas exists."},
    {"id": "p2", "title": "Understanding Series and DataFrames",
     "description": "The two core Pandas objects."},
    {"id": "p3", "title": "Data Inspection and Exploration",
     "description": "Look inside a DataFrame with head and info."},
    {"id": "p4", "title": "GroupBy and Aggregation Techniques",
     "description": "Summarise groups of rows."},
]


def test_plural_title_owns_the_singular_identifier():
    # "DataFrames" in lesson 2's title must claim "DataFrame" in lesson 3's description,
    # or lesson 2 gets flagged for teaching its own subject.
    v = find_violations(PANDAS_COURSE, {"p2": _pre('df = pd.DataFrame({"a": [1]})')})
    assert v == []


def test_identifier_before_its_plural_owner_is_still_flagged():
    v = find_violations(PANDAS_COURSE, {"p1": _pre('df = pd.DataFrame({"a": [1]})')})
    assert [(x[1], x[2], x[3]) for x in v] == [("p1", "DataFrame", 1)]


def test_sql_aggregate_does_not_match_a_pandas_method_call():
    # `.sum()` is a method, not the SQL aggregate the GroupBy lesson owns.
    content = {"p3": _pre('print(df.isna().sum())\ntotal = df["amt"].sum()')}
    assert find_violations(PANDAS_COURSE, content) == []


def test_sql_aggregate_still_flagged_inside_a_sql_block():
    course = [
        {"id": "s1", "title": "Selecting Rows", "description": "Read rows."},
        {"id": "s2", "title": "Aggregation Basics", "description": "Summarise rows."},
    ]
    content = {"s1": _pre("SELECT SUM(amount) FROM orders;", "sql")}
    v = find_violations(course, content)
    assert [(x[1], x[2], x[3]) for x in v] == [("s1", "SUM()", 1)]


def test_sql_block_detected_without_a_data_lang_attribute():
    course = [
        {"id": "s1", "title": "Selecting Rows", "description": "Read rows."},
        {"id": "s2", "title": "Grouping with GROUP BY", "description": "Group rows."},
    ]
    html = "<pre><code>SELECT city, COUNT(*) FROM customers GROUP BY city;</code></pre>"
    v = find_violations(course, {"s1": html})
    assert ("GROUP BY", 1) in [(x[2], x[3]) for x in v]


def test_python_open_builtin_flagged_but_method_call_is_not():
    course = [
        {"id": "a", "title": "Strings", "description": "Text values."},
        {"id": "b", "title": "File Handling", "description": "Read and write files."},
    ]
    assert find_violations(course, {"a": _pre('f = open("data.txt")')})
    assert find_violations(course, {"a": _pre("conn.open()")}) == []


def test_classification_lesson_does_not_own_the_class_keyword():
    course = [
        {"id": "a", "title": "Text Processing Systems", "description": "Clean text."},
        {"id": "b", "title": "Text Classification and Document Categorization",
         "description": "Sort documents into labelled buckets."},
    ]
    assert "class" not in concepts_in_title(course[1]["title"])
    assert find_violations(course, {"a": _pre("class TextCleaner:\n    pass")}) == []


def test_plural_and_inflected_titles_still_own_their_construct():
    assert "class" in concepts_in_title("Classes and Objects")
    assert "for" in concepts_in_title("Loops and Iteration")
    assert "for" in concepts_in_title("Looping Over Data")
    assert "async" in concepts_in_title("Asynchronous Programming")
    assert "open()" in concepts_in_title("Reading Files Safely")


def test_project_lessons_do_not_own_terms():
    course = [
        {"id": "a", "title": "Docker for AI Systems", "description": "Containerise models."},
        {"id": "b", "title": "Project — AI-Powered Container Platform",
         "description": "Build a platform using OpenAI end to end."},
    ]
    # The project is late because it uses what came before, not because it introduces it.
    assert find_violations(course, {"a": _pre("llm = OpenAI(temperature=0)")}) == []


def test_a_project_lesson_that_declares_teaches_still_owns_those_terms():
    course = [
        {"id": "a", "title": "Setup", "description": "Install the tools you need."},
        {"id": "b", "title": "Project — Build a Tracer",
         "description": "Assemble the pieces into one tool."},
    ]
    manifests = {"b": {"teaches": ["LangSmith"], "uses": []}}
    v = find_violations(course, {"a": _pre("t = LangSmith()")}, manifests=manifests)
    assert [(x[1], x[2], x[3]) for x in v] == [("a", "LangSmith", 1)]


def test_platform_names_are_never_owned():
    course = [
        {"id": "a", "title": "Virtualization Basics", "description": "How containers run."},
        {"id": "b", "title": "Setting Up Docker on macOS",
         "description": "Install Docker Desktop on macOS and Windows."},
    ]
    assert find_violations(course, {"a": _pre("Host OS (macOS/Windows)")}) == []


def test_two_capital_words_are_not_identifiers():
    assert identifiers("GROUP BY and ORDER BY clauses") == set()
    assert "BY" not in identifiers("Grouping with GROUP BY")


def test_first_mention_wins_for_construct_ownership():
    course = [
        {"id": "a", "title": "Loops", "description": ""},
        {"id": "b", "title": "Loops Again", "description": ""},
    ]
    _, constructs = build_ownership(course)
    assert constructs["for"][0] == 0


def test_lesson_with_no_code_is_skipped():
    assert find_violations(PY_COURSE, {"l1": "<p>All prose, no code.</p>"}) == []


def test_missing_lesson_content_is_skipped():
    assert find_violations(PY_COURSE, {}) == []


def _run(tmp_path, lessons, contents, *extra):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps(lessons), encoding="utf-8")
    out.write_text(json.dumps(
        {"lessons": [{"id": k, "content": v} for k, v in contents.items()]}),
        encoding="utf-8")
    return subprocess.run(
        [sys.executable, SCRIPT, "--input", str(inp), "--course", str(out), *extra],
        capture_output=True, text=True)


def test_cli_clean_run_exits_zero(tmp_path):
    r = _run(tmp_path, PY_COURSE, {"l3": _pre("for n in nums:\n    print(n)")})
    assert r.returncode == 0
    assert "SEQUENCING: clean" in r.stdout


def test_cli_reports_violation_but_exits_zero_without_strict(tmp_path):
    r = _run(tmp_path, PY_COURSE, {"l2": _pre("for n in nums:\n    print(n)")})
    assert r.returncode == 0
    assert "1 violation" in r.stdout
    assert "lesson 03" in r.stdout


def test_cli_strict_exits_two_on_violation(tmp_path):
    r = _run(tmp_path, PY_COURSE, {"l2": _pre("for n in nums:\n    print(n)")}, "--strict")
    assert r.returncode == 2


def test_declared_teaches_overrides_heuristic_ownership():
    # The heuristic gives DataFrame to lesson 2 by title; lesson 1 declares it teaches it.
    course = [
        {"id": "a", "title": "Introduction to Pandas", "description": "Why Pandas."},
        {"id": "b", "title": "Understanding DataFrames", "description": "The core object."},
    ]
    manifests = {"a": {"teaches": ["DataFrame"], "uses": []}}
    content = {"a": _pre('df = pd.DataFrame({"x": [1]})')}
    assert find_violations(course, content) != []
    assert find_violations(course, content, manifests=manifests) == []


ADVANCED_LATE = [
    {"id": "L1", "title": "Variables and Values", "description": "Store a value."},
    {"id": "L2", "title": "Repeating Work Over a List",
     "description": "Do the same thing to every item in a list."},
    {"id": "L3", "title": "Strings and Text", "description": "Join and slice text."},
    {"id": "L4", "title": "Advanced Loop Patterns",
     "description": "Nested loops and early exit."},
]


def test_declared_teaches_claims_a_construct_not_only_an_identifier():
    # "Advanced Loop Patterns" at lesson 4 must not own `for` when lesson 2 taught loops
    # under a title that never says "loop".
    content = {"L3": _pre("for w in words:\n    print(w)")}
    assert find_violations(ADVANCED_LATE, content) != []
    manifests = {"L2": {"teaches": ["for", "loop", "iteration"], "uses": []}}
    assert find_violations(ADVANCED_LATE, content, manifests=manifests) == []


def test_declaring_a_concept_phrase_claims_its_whole_construct_family():
    # Declaring "loop" claims both `for` and `while`.
    assert set(constructs_declared(["loop"])) == {"for", "while"}
    content = {"L3": _pre("while going:\n    step()")}
    manifests = {"L2": {"teaches": ["loop"], "uses": []}}
    assert find_violations(ADVANCED_LATE, content) != []
    assert find_violations(ADVANCED_LATE, content, manifests=manifests) == []


def test_declared_construct_ownership_still_respects_first_mention():
    # L2 declares loops, so L4 cannot reclaim them by declaring the same thing.
    manifests = {"L2": {"teaches": ["for"], "uses": []},
                 "L4": {"teaches": ["for"], "uses": []}}
    _, construct_owner = build_ownership(ADVANCED_LATE, manifests)
    assert construct_owner["for"][0] == 1


def test_declaring_a_construct_does_not_excuse_a_genuinely_early_lesson():
    # L1 comes before the lesson that declared loops, so its `for` is still a violation.
    manifests = {"L2": {"teaches": ["for", "loop"], "uses": []}}
    content = {"L1": _pre("for x in xs:\n    print(x)")}
    v = find_violations(ADVANCED_LATE, content, manifests=manifests)
    assert [(x[1], x[2], x[3]) for x in v] == [("L1", "for", 1)]


def test_declared_use_of_a_later_term_is_flagged_without_any_code():
    # Prose-level leak: nothing in a <pre>, but the writer admits it leaned on LLMChain.
    course = [
        {"id": "a", "title": "Prompt Templates", "description": "Design prompts."},
        {"id": "b", "title": "Chains", "description": "Compose steps with LLMChain."},
    ]
    manifests = {"a": {"teaches": ["prompt"], "uses": ["LLMChain"]}}
    v = find_violations(course, {"a": "<p>prose only</p>"}, manifests=manifests)
    assert [(x[1], x[2], x[3]) for x in v] == [("a", "LLMChain", 1)]


def test_term_in_both_code_and_declared_uses_is_reported_once():
    course = [
        {"id": "a", "title": "Prompt Templates", "description": "Design prompts."},
        {"id": "b", "title": "Chains", "description": "Compose steps with LLMChain."},
    ]
    manifests = {"a": {"teaches": [], "uses": ["LLMChain"]}}
    v = find_violations(course, {"a": _pre("c = LLMChain(x)")}, manifests=manifests)
    assert len(v) == 1


def test_allowlisted_term_is_never_flagged():
    course = [
        {"id": "a", "title": "Setup", "description": "Install the tools you need."},
        {"id": "b", "title": "Functions and Reuse", "description": "Write a def."},
    ]
    content = {"a": _pre("def main():\n    return 1")}
    assert find_violations(course, content) != []
    assert find_violations(course, content, allow={"def", "return"}) == []


def test_allowlist_folds_plurals_like_ownership_does():
    course = [
        {"id": "a", "title": "Setup", "description": "Install the tools you need."},
        {"id": "b", "title": "Understanding DataFrames", "description": "The core object."},
    ]
    content = {"a": _pre('df = pd.DataFrame({"x": [1]})')}
    assert find_violations(course, content, allow={"DataFrames"}) == []


def test_load_manifests_reads_only_requested_ids(tmp_path):
    (tmp_path / "a.concepts.json").write_text(
        json.dumps({"teaches": ["x"], "uses": []}), encoding="utf-8")
    (tmp_path / "z.concepts.json").write_text(
        json.dumps({"teaches": ["q"], "uses": []}), encoding="utf-8")
    got = load_manifests(str(tmp_path), ["a", "b"])
    assert set(got) == {"a"}
    assert got["a"]["teaches"] == ["x"]


def test_load_manifests_raises_on_malformed_json(tmp_path):
    (tmp_path / "a.concepts.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifests(str(tmp_path), ["a"])


def test_load_manifests_raises_when_a_field_is_not_a_list(tmp_path):
    (tmp_path / "a.concepts.json").write_text(
        json.dumps({"teaches": "DataFrame"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifests(str(tmp_path), ["a"])


def test_cli_reports_manifest_coverage(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps(PY_COURSE), encoding="utf-8")
    out.write_text(json.dumps({"lessons": [
        {"id": "l3", "content": _pre("for n in nums:\n    print(n)")}]}), encoding="utf-8")
    (tmp_path / "l3.concepts.json").write_text(
        json.dumps({"teaches": ["for", "while"], "uses": []}), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, SCRIPT, "--input", str(inp), "--course", str(out),
         "--concepts-dir", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0
    assert "1/3 lessons declared a concept manifest" in r.stdout


def test_cli_exits_two_on_a_broken_manifest(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps(PY_COURSE), encoding="utf-8")
    out.write_text(json.dumps({"lessons": []}), encoding="utf-8")
    (tmp_path / "l1.concepts.json").write_text("{broken", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, SCRIPT, "--input", str(inp), "--course", str(out),
         "--concepts-dir", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 2
    assert "unreadable concept manifest" in r.stdout


def test_cli_allow_flag_suppresses_a_violation(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps(PY_COURSE), encoding="utf-8")
    out.write_text(json.dumps({"lessons": [
        {"id": "l2", "content": _pre("for n in nums:\n    print(n)")}]}), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, SCRIPT, "--input", str(inp), "--course", str(out),
         "--allow", "for,while", "--strict"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "clean" in r.stdout


def test_bundled_langchain_reference_reproduces_the_reported_bug():
    """The plugin's own reference output ships the exact defect this check exists for:
    lesson 1 demonstrates LLMChain, which lesson 8 teaches."""
    ref = os.path.join(os.path.dirname(__file__), "..", "references")
    with open(os.path.join(
            ref, "course-introduction-to-langchain-and-llm-applications_input.json"),
            encoding="utf-8") as f:
        lessons = json.load(f)
    with open(os.path.join(
            ref, "course-introduction-to-langchain-and-llm-applications_output.json"),
            encoding="utf-8") as f:
        course = json.load(f)
    v = find_violations(lessons, {l["id"]: l["content"] for l in course["lessons"]})
    assert any(term == "LLMChain" and i == 0 for i, _, term, _, _ in v)


def test_bundled_mixed_reference_is_clean():
    ref = os.path.join(os.path.dirname(__file__), "..", "references")
    with open(os.path.join(ref, "course-sample-mixed_input.json"), encoding="utf-8") as f:
        lessons = json.load(f)
    with open(os.path.join(ref, "course-sample-mixed_output.json"), encoding="utf-8") as f:
        course = json.load(f)
    assert find_violations(lessons, {l["id"]: l["content"] for l in course["lessons"]}) == []
