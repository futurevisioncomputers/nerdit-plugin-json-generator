/* NERDIT Python runner — Pyodide (CPython compiled to WebAssembly).
 *
 * Lazy-loads on the learner's first Run click; the first load takes a few
 * seconds and roughly 6 MB, so lessons warn the learner in one sentence.
 * NumPy, pandas, matplotlib and scikit-learn ship inside Pyodide; each run
 * loads whatever the learner's code imports before executing it.
 *
 * Served by the website at /nerdit-python-runner.js. Source of truth lives in
 * the nerdit plugin's references/ directory.
 *
 * Lesson datasets (plugin runners/python.md, Lesson data): a lesson may carry a recipe in
 * <script type="application/json" class="nerdit-dataset">. Before the first run on the
 * page the runner builds its CSV files inside Pyodide with the plugin's own generator
 * (/nerdit_world_gen.py), so pd.read_csv("orders.csv") works as on a real computer, and
 * adds a Download link per file under the first Try It. nerdit-plot-runner.js does the same.
 */
(function () {
  if (typeof window.nerditDatasetRecipe !== "function") {
    // The parsed recipe, or null when the page has none or its JSON is broken.
    window.nerditDatasetRecipe = function (root) {
      var el = (root || document).querySelector('script.nerdit-dataset');
      if (!el) return null;
      try {
        var recipe = JSON.parse(el.textContent);
        return recipe && typeof recipe === 'object' && !Array.isArray(recipe) ? recipe : null;
      } catch (e) {
        return null;
      }
    };
  }
  var DATA_ERROR = "Could not prepare this lesson's data. Check your internet connection and try again.";
  var BUILD = 'import json\njson.dumps(build_files(json.loads(_nerdit_recipe)))';
  var dataset = null; // { py, key, promise }: built once per page and Pyodide instance
  var addDownloads = function (files) {
    var anchor = document.querySelector('.nerdit-tryit');
    if (!anchor) return;
    Object.keys(files).forEach(function (name) {
      var have = document.querySelectorAll('a.nerdit-dataset-download');
      for (var i = 0; i < have.length; i++) {
        if (have[i].getAttribute('download') === name) { anchor = have[i]; return; }
      }
      var a = document.createElement('a');
      a.className = 'nerdit-dataset-download';
      a.setAttribute('download', name);
      a.href = URL.createObjectURL(new Blob([files[name]], { type: 'text/csv' }));
      a.textContent = 'Download ' + name;
      anchor.parentNode.insertBefore(a, anchor.nextSibling);
      anchor = a;
    });
  };
  var prepareDataset = function (py) {
    var recipe = window.nerditDatasetRecipe(document);
    if (!recipe) return Promise.resolve(null);
    // The block's exact text goes to Python: a JS round trip would turn 100.0 into 100 and
    // round big seeds, giving other CSVs than the ones check_python_outputs.py verified.
    var key = document.querySelector('script.nerdit-dataset').textContent;
    if (dataset && dataset.py === py && dataset.key === key) {
      // The classroom replaces the lesson DOM on every visit; the files persist, the links do not.
      return dataset.promise.then(function (files) { addDownloads(files); return files; });
    }
    var promise = fetch('/nerdit_world_gen.py')
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      })
      .then(function (src) {
        // A private namespace: the generator never appears in the learner's variables.
        var ns = py.toPy({});
        try {
          py.runPython(src, { globals: ns });
          ns.set('_nerdit_recipe', key);
          var files = JSON.parse(py.runPython(BUILD, { globals: ns }));
          Object.keys(files).forEach(function (name) { py.FS.writeFile(name, files[name]); });
          addDownloads(files);
          return files;
        } finally {
          if (ns && ns.destroy) ns.destroy();
        }
      });
    // A failed build is forgotten, so the next Run tries again.
    promise.catch(function () { if (dataset && dataset.promise === promise) dataset = null; });
    dataset = { py: py, key: key, promise: promise };
    return promise;
  };

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
      // NumPy, pandas, sqlite3 and the rest ship with Pyodide but are not
      // installed until asked for: without this step `import pandas` fails with
      // ModuleNotFoundError. Packages already loaded resolve at once.
      var run = function(py){
        var code = box.querySelector('.nerdit-tryit-editor').value;
        status.textContent = 'Preparing…';
        prepareDataset(py).then(
          function(){
            status.textContent = 'Loading packages…';
            py.loadPackagesFromImports(code).then(
              function(){ execute(py, code); },
              function(){ show('Could not load the Python packages this code needs. Check your internet connection and try again.', true); }
            );
          },
          function(){ show(DATA_ERROR, true); }
        );
      };
      var execute = function(py, code){
        var buf = [];
        var collect = { batched: function(s){ buf.push(s); } };
        py.setStdout(collect);
        py.setStderr(collect);
        // Fresh namespace each run, so deleting a variable in the editor really
        // removes it instead of silently surviving from the previous run.
        var ns = py.toPy({});
        try {
          py.runPython(code, { globals: ns });
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
