/* NERDIT experiment ("nerdit-sim", owner 2026-11-05): the learner changes an input and sees the
 * rule decide, in words, in a picture and in the code. Contract: references/sim.md.
 *
 * <div class="nerdit-sim"> holds <script type="application/json" class="nerdit-sim-spec"> (controls,
 * examples, predict, challenge, tests) and <script type="text/plain" class="nerdit-sim-model">
 * (Python: def simulate(<control ids>) -> {"ok", "result", "why", "details"?, "picture"?, "code"?}).
 * The model runs on the same in-browser Python (Pyodide) as the lesson runners. Pictures are drawn
 * here from a few lines of data, so a lesson never carries drawing code:
 *   pieces  {"type":"pieces","items":[..],"take":[from,to],"takeLabel","left":[from,to],"leftLabel"}
 *   flow    {"type":"flow","steps":[..],"reached":n,"stopLabel"}
 *   compare {"type":"compare","columns":[{"title","lines":[..],"verdict","ok"}, ..]}
 *   bars    {"type":"bars","items":[{"label","value"}],"unit","mark"}
 *   table   {"type":"table","head":[..],"rows":[[..]],"mark":[row indexes]}
 */
(function () {
  var PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/';

  function boot() {
    if (window.__nerditPy) return Promise.resolve(window.__nerditPy);
    if (!window.__nerditPyBoot) {
      window.__nerditPyBoot = new Promise(function (resolve, reject) {
        var go = function () {
          window.loadPyodide({ indexURL: PYODIDE }).then(function (py) { window.__nerditPy = py; resolve(py); }, reject);
        };
        if (window.loadPyodide) return go();
        var s = document.createElement('script');
        s.src = PYODIDE + 'pyodide.js'; s.onload = go; s.onerror = reject;
        document.head.appendChild(s);
      });
      window.__nerditPyBoot.catch(function () { window.__nerditPyBoot = null; });
    }
    return window.__nerditPyBoot;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function textW(s, size) { return String(s).length * size * 0.6; }
  function box(x, y, w, h, label, o) {
    o = o || {};
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="8" fill="' + (o.fill || 'var(--bg-soft)') +
      '" stroke="' + (o.stroke || 'var(--nb)') + '" stroke-width="2"' + (o.dash ? ' stroke-dasharray="6 4"' : '') +
      (o.faded ? ' opacity=".35"' : '') + '/>' + '<text x="' + (x + w / 2) + '" y="' + (y + h / 2 + 5.5) +
      '" text-anchor="middle" font-size="16" font-weight="700" fill="' + (o.ink || 'var(--nb)') + '"' +
      (o.faded ? ' opacity=".45"' : '') + '>' + esc(label) + '</text>';
  }
  function label(x, y, s, colour, anchor) {
    return '<text x="' + x + '" y="' + y + '" text-anchor="' + (anchor || 'middle') + '" font-size="15" font-weight="700" fill="' +
      colour + '">' + esc(s) + '</text>';
  }
  function wrap(w, h, body, aria) {
    return '<svg viewBox="0 0 ' + Math.ceil(w) + ' ' + h + '" role="img" aria-label="' + esc(aria) + '">' + body + '</svg>';
  }
  function range(r, n) { return r && r.length === 2 && r[0] >= 0 && r[1] < n && r[0] <= r[1] ? r : null; }

  var DRAW = {
    pieces: function (p, ok) {
      var items = p.items || [], parts = [], at = [], x = 10, colour = ok ? 'var(--green)' : 'var(--orange)';
      items.forEach(function (item, k) {
        var w = Math.max(64, textW(item, 16) + 26);
        if (k && p.cuts !== false) {
          parts.push('<line x1="' + (x - 9) + '" y1="18" x2="' + (x - 9) + '" y2="68" stroke="var(--orange)" stroke-width="2" stroke-dasharray="4 4"/>' +
            label(x - 9, 16, p.cut || '/', 'var(--orange)'));
        }
        parts.push(box(x, 24, w, 40, item));
        at.push([x, w]); x += w + 18;
      });
      var take = range(p.take, items.length), left = range(p.left, items.length);
      if (take) {
        var a = at[take[0]][0], b = at[take[1]][0] + at[take[1]][1];
        parts.push('<path d="M' + a + ' 70 L' + a + ' 78 L' + b + ' 78 L' + b + ' 70" fill="none" stroke="' + colour + '" stroke-width="3"/>' +
          label((a + b) / 2, 98, p.takeLabel || '', colour));
      }
      if (left) {
        var c = at[left[0]][0] - 4, d = at[left[1]][0] + at[left[1]][1] + 4;
        parts.push('<rect x="' + c + '" y="19" width="' + (d - c) + '" height="50" rx="10" fill="none" stroke="var(--orange)" stroke-width="2" stroke-dasharray="6 4"/>' +
          label((c + d) / 2, 98, p.leftLabel || 'left over', 'var(--orange)'));
      }
      return wrap(Math.max(x, 300), 108, parts.join(''), 'The input in pieces');
    },
    flow: function (p, ok) {
      var steps = p.steps || [], reached = typeof p.reached === 'number' ? p.reached : steps.length - 1;
      var parts = [], x = 10;
      steps.forEach(function (s, k) {
        var w = Math.max(80, textW(s, 16) + 26), faded = k > reached;
        if (k) parts.push('<line x1="' + (x - 26) + '" y1="44" x2="' + (x - 6) + '" y2="44" stroke="var(--nb-mid)" stroke-width="3"' + (faded ? ' opacity=".35"' : '') + '/>' +
          '<path d="M' + (x - 13) + ' 37 L' + (x - 5) + ' 44 L' + (x - 13) + ' 51" fill="none" stroke="var(--nb-mid)" stroke-width="3"' + (faded ? ' opacity=".35"' : '') + '/>');
        parts.push(box(x, 24, w, 40, s, { faded: faded, stroke: k === reached ? (ok ? 'var(--green)' : 'var(--orange)') : 'var(--nb)' }));
        if (k === reached) parts.push(label(x + w / 2, 92, ok ? (p.doneLabel || 'reached') : (p.stopLabel || 'stops here'), ok ? 'var(--green)' : 'var(--orange)'));
        x += w + 32;
      });
      return wrap(Math.max(x - 22, 300), 104, parts.join(''), 'The steps, and where it gets to');
    },
    compare: function (p) {
      var cols = (p.columns || []).slice(0, 3), w = 230, parts = [];
      var h = 70 + 24 * Math.max.apply(null, cols.map(function (c) { return (c.lines || []).length; }).concat([1]));
      cols.forEach(function (c, k) {
        var x = 10 + k * (w + 16), colour = c.ok ? 'var(--green)' : 'var(--orange)';
        parts.push('<rect x="' + x + '" y="8" width="' + w + '" height="' + (h + 24) + '" rx="10" fill="var(--white)" stroke="' + colour + '" stroke-width="2"/>' +
          '<text x="' + (x + 12) + '" y="34" font-size="16" font-weight="800" fill="var(--nb)">' + esc(c.title) + '</text>');
        (c.lines || []).forEach(function (line, j) {
          parts.push('<text x="' + (x + 12) + '" y="' + (62 + j * 24) + '" font-size="15" fill="var(--tx)">' + esc(line) + '</text>');
        });
        parts.push(label(x + 12, h + 22, (c.ok ? '✓ ' : '✗ ') + (c.verdict || ''), colour, 'start'));
      });
      return wrap(10 + cols.length * (w + 16), h + 40, parts.join(''), 'Side by side');
    },
    bars: function (p) {
      var items = (p.items || []).slice(0, 8), max = Math.max.apply(null, items.map(function (i) { return Math.abs(i.value); }).concat([1]));
      var lw = Math.max.apply(null, items.map(function (i) { return textW(i.label, 15); }).concat([40])) + 16, parts = [];
      items.forEach(function (it, k) {
        var y = 10 + k * 34, len = 260 * Math.abs(it.value) / max, marked = it.label === p.mark;
        parts.push('<text x="' + (lw - 8) + '" y="' + (y + 19) + '" text-anchor="end" font-size="15" font-weight="' + (marked ? 800 : 600) + '" fill="var(--tx)">' + esc(it.label) + '</text>' +
          '<rect x="' + lw + '" y="' + (y + 4) + '" width="' + Math.max(len, 2) + '" height="22" rx="4" fill="' + (marked ? 'var(--teal)' : 'var(--nb-mid)') + '" opacity="' + (marked ? 1 : .55) + '"/>' +
          '<text x="' + (lw + len + 8) + '" y="' + (y + 20) + '" font-size="15" font-weight="700" fill="var(--tx)">' + esc(it.value + (p.unit ? ' ' + p.unit : '')) + '</text>');
      });
      return wrap(lw + 380, 20 + items.length * 34, parts.join(''), 'Values compared');
    },
    table: function (p) {
      var head = p.head || [], rows = (p.rows || []).slice(0, 8), mark = p.mark || [], cw = [], parts = [];
      head.forEach(function (h, k) {
        cw.push(Math.max.apply(null, [textW(h, 15)].concat(rows.map(function (r) { return textW(r[k], 15); }))) + 24);
      });
      var total = cw.reduce(function (a, b) { return a + b; }, 0) + 30, y = 30;
      var x = 30;
      head.forEach(function (h, k) { parts.push('<text x="' + (x + 10) + '" y="22" font-size="15" font-weight="800" fill="var(--nb)">' + esc(h) + '</text>'); x += cw[k]; });
      rows.forEach(function (r, j) {
        var on = mark.indexOf(j) >= 0;
        if (on) parts.push('<rect x="26" y="' + (y + 2) + '" width="' + (total - 26) + '" height="26" rx="4" fill="var(--teal-bg)" stroke="var(--teal)"/>' +
          '<text x="8" y="' + (y + 20) + '" font-size="15" font-weight="800" fill="var(--teal)">✓</text>');
        x = 30;
        r.forEach(function (cell, k) {
          parts.push('<text x="' + (x + 10) + '" y="' + (y + 20) + '" font-size="15" font-weight="' + (on ? 700 : 400) + '" fill="var(--tx)">' + esc(cell) + '</text>');
          x += cw[k];
        });
        y += 30;
      });
      return wrap(total + 4, y + 6, parts.join(''), 'Rows, with the matching ones ticked');
    }
  };

  window.nerditSimPicture = function (picture, ok) {
    var draw = picture && DRAW[picture.type];
    return draw ? draw(picture, ok) : '';
  };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function setup(box, index) {
    var specNode = box.querySelector('script.nerdit-sim-spec');
    var modelNode = box.querySelector('script.nerdit-sim-model');
    if (!specNode || !modelNode || box.getAttribute('data-ready')) return;
    box.setAttribute('data-ready', '1');
    var spec = JSON.parse(specNode.textContent);
    var model = modelNode.textContent;
    var id = 'nerdit-sim-' + index + '-' + Math.random().toString(36).slice(2, 6);
    var inputs = {};
    var waiting = spec.predict ? 'Make your prediction above, then press Run.' : 'Press Run to see what happens.';

    var ui = el('div', 'nerdit-sim-ui');
    var controls = el('div', 'nerdit-sim-controls');
    (spec.controls || []).forEach(function (c) {
      if (c.type === 'choice') {
        var fs = el('fieldset', 'nerdit-sim-choice');
        fs.appendChild(el('legend', null, c.label));
        c.options.forEach(function (opt) {
          var lab = el('label'), r = document.createElement('input');
          r.type = 'radio'; r.name = id + '-' + c.id; r.value = opt; r.checked = opt === c.value;
          lab.appendChild(r); lab.appendChild(el('code', null, opt));
          fs.appendChild(lab);
        });
        controls.appendChild(fs);
        inputs[c.id] = {
          get: function () { var on = fs.querySelector('input:checked'); return on ? on.value : c.value; },
          set: function (v) { fs.querySelectorAll('input').forEach(function (r) { r.checked = r.value === v; }); }
        };
        return;
      }
      var field = el('div', 'nerdit-sim-field'), lab2 = el('label', null, c.label), inp = document.createElement('input');
      inp.id = id + '-' + c.id; lab2.htmlFor = inp.id;
      if (c.type === 'slider') { inp.type = 'range'; inp.min = c.min; inp.max = c.max; inp.step = c.step || 1; }
      else if (c.type === 'number') { inp.type = 'number'; if (c.min != null) inp.min = c.min; if (c.max != null) inp.max = c.max; }
      else { inp.type = 'text'; inp.spellcheck = false; inp.autocomplete = 'off'; }
      inp.value = c.value;
      field.appendChild(lab2);
      if (c.prefix) field.appendChild(el('span', 'nerdit-sim-prefix', c.prefix));
      field.appendChild(inp);
      if (c.type === 'slider') {
        var shown = el('output', 'nerdit-sim-value', String(c.value));
        inp.addEventListener('input', function () { shown.textContent = inp.value; });
        field.appendChild(shown);
      }
      controls.appendChild(field);
      inputs[c.id] = {
        get: function () { return c.type === 'text' ? inp.value : Number(inp.value); },
        set: function (v) { inp.value = v; inp.dispatchEvent(new Event('input')); }
      };
      inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); run(); } });
    });
    ui.appendChild(controls);

    if (spec.examples && inputs[spec.examples.control]) {
      var ex = el('div', 'nerdit-sim-examples');
      ex.appendChild(el('span', null, 'Try: '));
      spec.examples.values.forEach(function (v) {
        var b = el('button', 'nerdit-sim-example', String(v));
        b.type = 'button';
        b.addEventListener('click', function () { inputs[spec.examples.control].set(v); run(); });
        ex.appendChild(b);
      });
      ui.appendChild(ex);
    }

    var actions = el('div', 'nerdit-sim-actions');
    var runBtn = el('button', 'nerdit-check-btn', 'Run'), resetBtn = el('button', 'nerdit-sim-reset', 'Reset');
    runBtn.type = resetBtn.type = 'button';
    actions.appendChild(runBtn); actions.appendChild(resetBtn);
    ui.appendChild(actions);

    var result = el('div', 'nerdit-sim-result');
    result.setAttribute('role', 'status');
    result.setAttribute('aria-live', 'polite');
    result.appendChild(el('p', 'nerdit-sim-hint', waiting));
    ui.appendChild(result);

    var predictBox = null, verdict = null;
    if (spec.predict) {
      predictBox = el('div', 'nerdit-sim-predict');
      predictBox.appendChild(el('p', 'nerdit-sim-q', spec.predict.question));
      var opts = el('div', 'nerdit-sim-options');
      spec.predict.options.forEach(function (opt, k) {
        var b = el('button', 'nerdit-sim-option', opt);
        b.type = 'button';
        b.addEventListener('click', function () {
          opts.querySelectorAll('button').forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
          Object.keys(spec.predict.inputs || {}).forEach(function (key) { if (inputs[key]) inputs[key].set(spec.predict.inputs[key]); });
          var right = k === spec.predict.answer;
          verdict.textContent = (right ? 'Your prediction is right. ' : 'Not quite. ') + 'Here is what the rule does:';
          verdict.className = 'nerdit-sim-verdict ' + (right ? 'ok' : 'no');
          run();
        });
        opts.appendChild(b);
      });
      predictBox.appendChild(opts);
      verdict = el('p', 'nerdit-sim-verdict');
      predictBox.appendChild(verdict);
      box.appendChild(predictBox);
    }
    box.appendChild(ui);
    if (spec.challenge) {
      var ch = el('p', 'nerdit-sim-challenge');
      ch.appendChild(el('strong', null, 'Now you: '));
      ch.appendChild(document.createTextNode(spec.challenge));
      box.appendChild(ch);
    }

    function show(r) {
      result.textContent = '';
      var line = el('p', 'nerdit-sim-outcome ' + (r.ok ? 'ok' : 'no'));
      line.appendChild(el('span', 'nerdit-sim-mark', r.ok ? '✓' : '✗'));
      line.appendChild(document.createTextNode(' ' + r.result));
      result.appendChild(line);
      var svg = window.nerditSimPicture(r.picture, r.ok);
      if (svg || r.code) {
        var stage = el('div', 'nerdit-sim-stage');
        if (svg) { var pic = el('div', 'nerdit-sim-visual'); pic.innerHTML = svg; stage.appendChild(pic); }
        if (r.code && r.code.lines) {
          var pre = el('pre', 'nerdit-sim-code'), code = el('code');
          r.code.lines.forEach(function (text, k) {
            code.appendChild(el('span', (r.code.highlight || []).indexOf(k) >= 0 ? 'hl' : null, text));
            code.appendChild(document.createTextNode('\n'));
          });
          pre.appendChild(code);
          stage.appendChild(pre);
        }
        result.appendChild(stage);
      }
      if (r.details && r.details.length) {
        var dl = el('dl', 'nerdit-sim-details');
        r.details.forEach(function (d) { dl.appendChild(el('dt', null, d[0])); dl.appendChild(el('dd', null, d[1])); });
        result.appendChild(dl);
      }
      if (r.why) {
        var why = el('p', 'nerdit-sim-why');
        why.appendChild(el('strong', null, 'Why: '));
        why.appendChild(document.createTextNode(r.why));
        result.appendChild(why);
      }
    }

    function run() {
      var values = {};
      Object.keys(inputs).forEach(function (key) { values[key] = inputs[key].get(); });
      runBtn.disabled = true;
      if (!window.__nerditPy) { result.textContent = ''; result.appendChild(el('p', 'nerdit-sim-hint', 'Starting Python… the first run takes a few seconds.')); }
      boot().then(function (py) {
        var ns = py.globals.get('dict')();
        ns.set('NERDIT_SIM_INPUT', JSON.stringify(values));
        try {
          show(JSON.parse(py.runPython(model + '\nimport json as _json\n_json.dumps(simulate(**_json.loads(NERDIT_SIM_INPUT)))', { globals: ns })));
        } finally { ns.destroy(); }
      }).catch(function (err) {
        result.textContent = '';
        result.appendChild(el('p', 'nerdit-sim-outcome no', 'Could not run the experiment: ' + (err && err.message ? err.message.split('\n').slice(-2).join(' ') : err)));
      }).then(function () { runBtn.disabled = false; });
    }

    runBtn.addEventListener('click', run);
    resetBtn.addEventListener('click', function () {
      (spec.controls || []).forEach(function (c) { inputs[c.id].set(c.value); });
      result.textContent = '';
      result.appendChild(el('p', 'nerdit-sim-hint', waiting));
      if (predictBox) {
        predictBox.querySelectorAll('.nerdit-sim-option').forEach(function (o) { o.removeAttribute('aria-pressed'); });
        verdict.textContent = ''; verdict.className = 'nerdit-sim-verdict';
      }
    });
  }

  window.nerditSetupSims = function (root) {
    Array.prototype.forEach.call((root || document).querySelectorAll('.nerdit-sim'), setup);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { window.nerditSetupSims(); });
  else window.nerditSetupSims();
})();
