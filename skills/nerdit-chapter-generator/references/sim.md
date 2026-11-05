# Experiment: `nerdit-sim` (owner, 2026-11-05)

The lesson explains, the video builds the picture, the experiment lets the learner **change an
input and see the rule decide**: in words, in a picture and in the code. Read this file only for a
lesson that gets one. `check_sims.py` (run by the gate) runs the model offline on every case.

## When

At most **one per lesson**, only where you can finish this sentence from the lesson itself:
*"Learners understand ___ better because they can change ___ and see ___."* Good: a result that
changes with an input, two ways on the same input, a rule that passes or fails, a process that
stops at a step, values to compare. Never for a definition, a list of facts, or a task the lesson's
Try It already covers. Place it after the section's explanation and code walk, before its Try It.

## Markup

```html
<div class="nerdit-sim">
  <div class="nerdit-sim-head">🧪 Experiment — Which URLs reach the view?</div>
  <p class="nerdit-sim-goal">Change the path and the converter, and watch which URLs match the rule.</p>
  <p class="nerdit-sim-note">A teaching model of this lesson's rule; not a live Flask server.</p>
  <script type="application/json" class="nerdit-sim-spec">{ …spec… }</script>
  <script type="text/plain" class="nerdit-sim-model">def simulate(path, converter): …</script>
</div>
```
Load the renderer once, after the wrapper: `<script src="/nerdit-sim.js"></script>`. The note says
honestly what the experiment is (a model of the rule, an exact calculation, …), never "live" when
nothing real runs. Write both scripts raw (a browser does not decode `&lt;` inside `<script>`),
except `<` before a letter, `/` or `!`: write it `\u003c` in the spec and `\x3c` in the model
(`"\x3cfilename>"`). The admin's sanitizer deletes a script whose text looks like a tag, so the
experiment would vanish on publish; `check_sims.py` fails it. Both still read `<` when they run.

## Spec (JSON)

- `controls`: 1–3 of `{"id", "type", "label", "value"}`; `type` is `text`, `choice` (+ `options`,
  2–4), `number` (optional `min`/`max`) or `slider` (+ `min`, `max`, `step`). `id` is a Python name;
  `prefix` (optional) shows fixed text before a text box (`/files/`).
- `examples` (optional): `{"control", "values": [1–4]}`: one-click inputs.
- `predict`: `{"question"` (ends with ?)`, "inputs", "options": [2–4], "answer": index}`. Clicking an
  option sets `inputs`, runs, and says whether the guess was right.
- `challenge`: a new case to try that is not the page's Try It.
- `tests`: at least 3 `{"inputs", "ok", "result"?}` (result = the expected start of the result
  text), with both outcomes among them.

## Model (Python)

`def simulate(<every control id>)` returns:
`{"ok": bool, "result": "matched" (≤ 80 chars, words, not only a colour), "why": the rule that
decided it, "details": [["label", "value"], …] (optional), "picture": {…} (optional), "code":
{"lines": [...], "highlight": [index, …]} (optional)}`. Only `math re json html statistics datetime
itertools collections decimal fractions string textwrap functools operator` may be imported. Every
fact and rule comes from the lesson; check the model against the real thing when you can.

## Pictures (drawn by the renderer: give data, never SVG)

| `type` | Data | Use for |
|---|---|---|
| `pieces` | `items`, `take` [from, to], `takeLabel`, `left` [from, to], `leftLabel`, `cuts` (default true), `cut` (default `/`) | input split into parts: URL paths, words, fields |
| `flow` | `steps` (2–6), `reached` (index), `stopLabel`, `doneLabel` | a process that stops or completes |
| `compare` | `columns` (2–3) of `{"title", "lines", "verdict", "ok"}` | two ways on the same input |
| `bars` | `items` of `{"label", "value"}`, `unit`, `mark` | values to compare |
| `table` | `head`, `rows` (≤ 8), `mark` (row indexes) | rows a filter or query keeps |

## Example model

```python
def simulate(path, converter):
    code = {"lines": [f'@app.route("/files/{converter}")', "def show_file(filename):"], "highlight": [0]}
    if path == "":
        return {"ok": False, "result": "not matched: 404 Not Found", "code": code,
                "why": "Nothing comes after /files/, so there is no value for filename."}
    pieces = path.split("/")
    if converter == "\x3cfilename>" and len(pieces) > 1:
        return {"ok": False, "result": "not matched: 404 Not Found", "code": code,
                "why": f"A plain variable part stops at the next slash, so '/{'/'.join(pieces[1:])}' is left over.",
                "picture": {"type": "pieces", "items": ["files"] + pieces, "take": [1, 1],
                            "takeLabel": "takes " + pieces[0], "left": [2, len(pieces)]}}
    return {"ok": True, "result": "matched", "code": code,
            "why": "The path converter also accepts slashes." if len(pieces) > 1 else "No slash, so one piece fits.",
            "picture": {"type": "pieces", "items": ["files"] + pieces, "take": [1, len(pieces)],
                        "takeLabel": "filename = " + path}}
```
