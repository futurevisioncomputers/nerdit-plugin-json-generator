# Runner: Matplotlib

### 6e. Matplotlib widget (data-visualization courses)

A chart lesson's output is a picture, not text, so the plain Python runner is not
enough. Load `references/nerdit-plot-runner.js` (`<script src="/nerdit-plot-runner.js">`,
absolute path — same reason as the Excel engine in runners/excel.md)
and use `nerditRunPlot(this)` instead of `nerditRunPython(this)`. Everything else about
the `nerdit-tryit` block is identical:

```html
<div class="nerdit-tryit" data-lang="python">
  <div class="nerdit-tryit-head">▶ Try It Yourself — edit the code and draw a real chart</div>
  <p>This runs real Python and Matplotlib inside your browser. The first run takes a
  little while as Python and Matplotlib load.</p>
  <textarea class="nerdit-tryit-editor" rows="12" spellcheck="false">import matplotlib.pyplot as plt

plt.plot(["Jan","Feb","Mar"], [120, 150, 130], marker="o")
plt.title("Monthly Sales")
plt.show()</textarea>
  <div class="nerdit-tryit-bar">
    <button class="nerdit-run-btn" onclick="nerditRunPlot(this)">Run &amp; Draw ▶</button>
    <span class="nerdit-tryit-status" aria-live="polite"></span>
  </div>
  <div class="nerdit-tryit-result"></div>
</div>
```

The runner captures the current figure after the learner's code and shows it as a PNG in
`nerdit-plot-figure`; anything printed appears above it. Each run gets a fresh namespace
and closes old figures, so charts never bleed between runs.

Two things it handles for you, both of which would otherwise confuse a beginner:
- **`plt.show()` warning suppressed.** Lessons teach `plt.show()` as the correct last
  line, but the browser's AGG backend warns "cannot show the figure" on every call. That
  warning is an artefact of the environment, not a learner mistake, so it is filtered out.
- **Tracebacks reduced** to the learner's line plus the error, hiding Pyodide and
  matplotlib internal frames.

**Writing the documented output.** A chart has no text output to paste, so describe what
appears, in one or two short sentences — "Four bars. Mouse is tallest at 120, Laptop is
shortest at 45." When the code also prints, show the printed text exactly and describe the
chart separately. Never invent a number: run the code and check.
