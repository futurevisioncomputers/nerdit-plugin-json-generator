/* NERDIT Python runner — Pyodide (CPython compiled to WebAssembly).
 *
 * Lazy-loads on the learner's first Run click; the first load takes a few
 * seconds and roughly 6 MB, so lessons warn the learner in one sentence.
 * NumPy, pandas, matplotlib and scikit-learn ship inside Pyodide and are
 * importable without extra setup.
 *
 * Served by the website at /nerdit-python-runner.js. Source of truth lives in
 * the nerdit plugin's references/ directory.
 */
(function () {
  if (typeof window.nerditRunPython !== "function") {
    window.nerditRunPython = function (btn) {
      var box = btn.closest('.nerdit-tryit');
      var status = box.querySelector('.nerdit-tryit-status');
      var out = box.querySelector('.nerdit-tryit-result');
      var show = function(text, isError){
        status.textContent = '';
        out.innerHTML = '<div class="nerdit-tryit-output' + (isError ? ' error' : '') + '"></div>';
        out.firstChild.textContent = text === '' ? '(no output — did you forget print()?)' : text;
      };
      // Pyodide tracebacks start with 5-6 frames of its own loader internals
      // (/lib/python312.zip/_pyodide/_base.py). A beginner reading that has no idea
      // which line is theirs, so reduce it to the learner's line + the error itself.
      var friendlyError = function(msg){
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
      };
      var run = function(py){
        var buf = [];
        var collect = { batched: function(s){ buf.push(s); } };
        py.setStdout(collect);
        py.setStderr(collect);
        // Fresh namespace each run, so deleting a variable in the editor really
        // removes it instead of silently surviving from the previous run.
        var ns = py.toPy({});
        try {
          py.runPython(box.querySelector('.nerdit-tryit-editor').value, { globals: ns });
          show(buf.join('\n'), false);
        } catch (err) {
          show((buf.length ? buf.join('\n') + '\n' : '') + friendlyError(err.message || err), true);
        } finally {
          py.setStdout({});
          py.setStderr({});
          if (ns && ns.destroy) ns.destroy();
        }
      };
      if (window.__nerditPy) return run(window.__nerditPy);
      status.textContent = 'Loading Python… (first run takes a few seconds)';
      var boot = function(){
        window.loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/' })
          .then(function(py){ window.__nerditPy = py; run(py); })
          .catch(function(){ status.textContent = 'Could not start Python. Check your internet connection.'; });
      };
      if (window.loadPyodide) return boot();
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js';
      s.onload = boot;
      s.onerror = function(){ status.textContent = 'Could not load Python. Check your internet connection.'; };
      document.head.appendChild(s);
    };
  }
})();
