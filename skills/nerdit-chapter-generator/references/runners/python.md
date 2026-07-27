# Runner: Python (Pyodide)

Load the engine once per lesson, after the wrapper:

<script src="/nerdit-python-runner.js"></script>


**Python variant** — no seed block; the learner's code is the whole program. Keep the
starter program short and directly tied to the concept just taught.
```html
<div class="nerdit-tryit" data-lang="python">
  <div class="nerdit-tryit-head">▶ Try It Yourself — edit the code and run it</div>
  <textarea class="nerdit-tryit-editor" rows="6" spellcheck="false">marks = 72
if marks >= 40:
    print("Pass")
else:
    print("Fail")</textarea>
  <div class="nerdit-tryit-bar">
    <button class="nerdit-run-btn" onclick="nerditRunPython(this)">Run Python ▶</button>
    <span class="nerdit-tryit-status" aria-live="polite"></span>
  </div>
  <div class="nerdit-tryit-result"></div>
</div>
```
Python output (including tracebacks) renders into `.nerdit-tryit-result` as plain text
inside `.nerdit-tryit-output`. Warn the learner in one sentence that the first run takes a
few seconds while Python loads.