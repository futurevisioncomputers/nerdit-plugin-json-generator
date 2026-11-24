"""A program that starts a server under its main guard must be imported, never run: running it
serves until stopped, and uvicorn's reload=True leaves a child process that holds the output pipe,
so the learner check hung for over an hour on the FastAPI course (2026-11-07)."""
from verify_course import _starts_server

GUARD = 'if __name__ == "__main__":\n'


def test_uvicorn_run_with_reload_is_a_server():
    assert _starts_server('import uvicorn\napp = 1\n' + GUARD + '    uvicorn.run("main:app", reload=True)\n')


def test_uvicorn_run_with_app_object_is_a_server():
    assert _starts_server(GUARD + '    import uvicorn\n\n    uvicorn.run(app, host="127.0.0.1", port=8000)\n')


def test_flask_app_run_is_still_a_server():
    assert _starts_server(GUARD + '    app.run(debug=True)\n')


def test_plain_script_and_unguarded_call_are_not():
    assert not _starts_server(GUARD + '    print("hello")\n')
    assert not _starts_server('uvicorn.run(app)\n')   # no main guard: nothing to import around
