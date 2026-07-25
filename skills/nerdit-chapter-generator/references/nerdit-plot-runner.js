/* ===================================================================
   nerdit-plot-runner.js
   Runs learner-edited Matplotlib code in the browser and renders the
   resulting figure.

   Built on Pyodide (CPython -> WebAssembly) plus the matplotlib package.
   Unlike the plain Python runner, a chart's "output" is an image, not
   text, so after the learner's code runs this captures the current
   figure with the AGG backend and shows it as a base64 PNG. Printed
   text is captured too, since a lesson often prints data before
   plotting it.

   Public API:
     window.nerditRunPlot(btn)   - run the editor inside one .nerdit-tryit
   =================================================================== */
(function () {
  'use strict';

  var PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/';

  // Runs before the learner's code: force a non-interactive backend and
  // clear any figure left behind by a previous run.
  //
  // The warning filter matters pedagogically. Lessons teach plt.show() as the
  // correct final line, but under the AGG backend show() emits
  // "Matplotlib is currently using agg ... cannot show the figure". That
  // warning is an artefact of running in a browser, not a learner mistake, and
  // printing it on every run would contradict the lesson it sits next to.
  var PRELUDE = [
    'import warnings',
    'warnings.filterwarnings("ignore", message=".*non-GUI backend.*")',
    'import matplotlib',
    'matplotlib.use("AGG")',
    'import matplotlib.pyplot as plt',
    'plt.close("all")'
  ].join('\n');

  // Runs after: hand back a base64 PNG, or "" when no figure was created.
  var CAPTURE = [
    'import io, base64',
    'import matplotlib.pyplot as plt',
    '_nerdit_png = ""',
    'if plt.get_fignums():',
    '    _nerdit_buf = io.BytesIO()',
    '    plt.savefig(_nerdit_buf, format="png", dpi=110, bbox_inches="tight")',
    '    _nerdit_buf.seek(0)',
    '    _nerdit_png = base64.b64encode(_nerdit_buf.read()).decode()',
    '    plt.close("all")',
    '_nerdit_png'
  ].join('\n');

  // Pyodide tracebacks open with several frames of loader and matplotlib
  // internals. A beginner cannot tell which line is theirs, so reduce it
  // to their line number plus the error itself.
  function friendlyError(msg) {
    var lines = String(msg).replace(/\s+$/, '').split('\n');
    var errLine = '', lineNo = '';
    for (var i = lines.length - 1; i >= 0; i--) {
      if (/^[A-Za-z_][A-Za-z_.]*(Error|Exception|Interrupt)\b/.test(lines[i].trim())) {
        errLine = lines[i].trim();
        break;
      }
    }
    for (var j = lines.length - 1; j >= 0; j--) {
      var m = lines[j].match(/File "<exec>", line (\d+)/);
      if (m) { lineNo = m[1]; break; }
    }
    if (!errLine) return String(msg);
    return (lineNo ? 'Line ' + lineNo + ' — ' : '') + errLine;
  }

  function show(box, text, pngB64, isError) {
    var out = box.querySelector('.nerdit-tryit-result');
    box.querySelector('.nerdit-tryit-status').textContent = '';
    out.innerHTML = '';

    if (text) {
      var pre = document.createElement('div');
      pre.className = 'nerdit-tryit-output' + (isError ? ' error' : '');
      pre.textContent = text;
      out.appendChild(pre);
    }
    if (pngB64) {
      var fig = document.createElement('div');
      fig.className = 'nerdit-plot-figure';
      var cap = document.createElement('div');
      cap.className = 'nerdit-plot-caption';
      cap.textContent = 'Chart';
      var img = document.createElement('img');
      img.className = 'nerdit-plot-img';
      img.alt = 'Chart produced by your code';
      img.src = 'data:image/png;base64,' + pngB64;
      fig.appendChild(cap);
      fig.appendChild(img);
      out.appendChild(fig);
    }
    if (!text && !pngB64) {
      var empty = document.createElement('div');
      empty.className = 'nerdit-tryit-empty';
      empty.textContent = 'Your code ran, but made no chart and printed nothing. Did you forget plt.plot() or print()?';
      out.appendChild(empty);
    }
  }

  function execute(box, py) {
    var buf = [];
    var collect = { batched: function (s) { buf.push(s); } };
    py.setStdout(collect);
    py.setStderr(collect);
    // Fresh namespace per run, so deleting a variable in the editor really
    // removes it instead of surviving from the previous run.
    var ns = py.toPy({});
    try {
      py.runPython(PRELUDE, { globals: ns });
      py.runPython(box.querySelector('.nerdit-tryit-editor').value, { globals: ns });
      var png = py.runPython(CAPTURE, { globals: ns });
      show(box, buf.join('\n'), png, false);
    } catch (err) {
      show(box, (buf.length ? buf.join('\n') + '\n' : '') + friendlyError(err.message || err), '', true);
    } finally {
      py.setStdout({});
      py.setStderr({});
      try { py.runPython('import matplotlib.pyplot as plt\nplt.close("all")'); } catch (e) { /* nothing to close */ }
      if (ns && ns.destroy) ns.destroy();
    }
  }

  window.nerditRunPlot = function (btn) {
    var box = btn.closest('.nerdit-tryit');
    if (!box) return;
    var status = box.querySelector('.nerdit-tryit-status');

    if (window.__nerditPlotPy) return execute(box, window.__nerditPlotPy);

    status.textContent = 'Loading Python and Matplotlib… the first run takes a little while.';

    var start = function () {
      window.loadPyodide({ indexURL: PYODIDE_URL })
        .then(function (py) {
          status.textContent = 'Loading Matplotlib…';
          return py.loadPackage(['matplotlib']).then(function () {
            window.__nerditPlotPy = py;
            execute(box, py);
          });
        })
        .catch(function () {
          status.textContent = 'Could not start Python. Check your internet connection and try again.';
        });
    };

    if (window.loadPyodide) return start();

    var s = document.createElement('script');
    s.src = PYODIDE_URL + 'pyodide.js';
    s.onload = start;
    s.onerror = function () {
      status.textContent = 'Could not load Python. Check your internet connection and try again.';
    };
    document.head.appendChild(s);
  };
})();
