/* ===================================================================
   nerdit-excel-engine.js
   Small Excel formula evaluator + sheet renderer + pivot builder.

   Exists because Excel has no embeddable engine the way SQL has sql.js
   and Python has Pyodide. Without this, an Excel lesson's "Try It
   Yourself" would have nothing to run, so practice would collapse back
   into reading. This supports only the function set the v9 Excel
   lessons actually teach — it is a teaching aid, not a spreadsheet.

   Public API:
     window.nerditExcelInit()        - render every .nerdit-xl on the page
     window.nerditRunExcel(btn)      - evaluate the formula in one widget
     window.nerditPivot(el)          - rebuild an interactive pivot table
     window.NerditExcel.evaluate(formula, grid) - for tests
   =================================================================== */
(function () {
  'use strict';

  // ---------- errors ----------
  function XlError(code) { this.code = code; }
  XlError.prototype.toString = function () { return this.code; };
  var NA = function () { return new XlError('#N/A'); };
  var VALUE = function () { return new XlError('#VALUE!'); };
  var DIV0 = function () { return new XlError('#DIV/0!'); };
  var NAME = function () { return new XlError('#NAME?'); };
  var REF = function () { return new XlError('#REF!'); };
  function isErr(v) { return v instanceof XlError; }

  // ---------- grid ----------
  // headers: ["ID","Name",...]  rows: [[...],[...]]
  // Row 1 holds the headers, so data row i sits on sheet row i + 2.
  function makeGrid(headers, rows) {
    var cells = [headers.slice()];
    for (var i = 0; i < rows.length; i++) cells.push(rows[i].slice());
    return {
      headers: headers,
      rows: rows,
      cells: cells,
      rowCount: cells.length,
      colCount: headers.length
    };
  }

  function colToIndex(letters) {
    var n = 0;
    letters = letters.toUpperCase();
    for (var i = 0; i < letters.length; i++) n = n * 26 + (letters.charCodeAt(i) - 64);
    return n - 1;
  }

  function indexToCol(idx) {
    var s = '';
    idx += 1;
    while (idx > 0) {
      var r = (idx - 1) % 26;
      s = String.fromCharCode(65 + r) + s;
      idx = Math.floor((idx - 1) / 26);
    }
    return s;
  }

  function parseRef(ref) {
    var m = /^\$?([A-Za-z]+)\$?([0-9]+)$/.exec(ref);
    if (!m) return null;
    return { col: colToIndex(m[1]), row: parseInt(m[2], 10) - 1 };
  }

  function cellValue(grid, r, c) {
    if (r < 0 || c < 0 || r >= grid.rowCount || c >= grid.colCount) return REF();
    var row = grid.cells[r];
    var v = row ? row[c] : '';
    return v === undefined || v === null ? '' : v;
  }

  // A range keeps its rectangle so VLOOKUP can index columns within it.
  function makeRange(grid, r1, c1, r2, c2) {
    return {
      isRange: true, grid: grid,
      r1: Math.min(r1, r2), c1: Math.min(c1, c2),
      r2: Math.max(r1, r2), c2: Math.max(c1, c2)
    };
  }

  function rangeValues(rg) {
    var out = [];
    for (var r = rg.r1; r <= rg.r2; r++)
      for (var c = rg.c1; c <= rg.c2; c++) out.push(cellValue(rg.grid, r, c));
    return out;
  }

  // Values down a single column of a range, used by lookups.
  function rangeColumn(rg, offset) {
    var out = [];
    for (var r = rg.r1; r <= rg.r2; r++) out.push(cellValue(rg.grid, r, rg.c1 + offset));
    return out;
  }

  // ---------- tokenizer ----------
  function tokenize(src) {
    var t = [], i = 0;
    var digit = function (c) { return c >= '0' && c <= '9'; };
    while (i < src.length) {
      var c = src[i];
      if (/\s/.test(c)) { i++; continue; }
      if (c === '"') {
        var j = i + 1, s = '';
        while (j < src.length) {
          if (src[j] === '"') {
            if (src[j + 1] === '"') { s += '"'; j += 2; continue; }
            break;
          }
          s += src[j++];
        }
        if (j >= src.length) throw new Error('A quote is not closed.');
        t.push({ type: 'str', value: s }); i = j + 1; continue;
      }
      if (digit(c) || (c === '.' && digit(src[i + 1]))) {
        var k = i;
        while (k < src.length && (digit(src[k]) || src[k] === '.')) k++;
        t.push({ type: 'num', value: parseFloat(src.slice(i, k)) }); i = k; continue;
      }
      if (/[A-Za-z$_]/.test(c)) {
        var w = i;
        while (w < src.length && /[A-Za-z0-9$_]/.test(src[w])) w++;
        var word = src.slice(i, w);
        var bare = word.replace(/\$/g, '');
        if (src[w] === ':' && parseRef(word)) {
          var e = w + 1;
          while (e < src.length && /[A-Za-z0-9$]/.test(src[e])) e++;
          t.push({ type: 'range', value: [word, src.slice(w + 1, e)] }); i = e; continue;
        }
        if (src[w] === '(') { t.push({ type: 'func', value: bare.toUpperCase() }); i = w; continue; }
        if (parseRef(word)) { t.push({ type: 'ref', value: word }); i = w; continue; }
        t.push({ type: 'name', value: bare.toUpperCase() }); i = w; continue;
      }
      var two = src.substr(i, 2);
      if (two === '<=' || two === '>=' || two === '<>') { t.push({ type: 'op', value: two }); i += 2; continue; }
      if ('+-*/^&<>=(),%'.indexOf(c) >= 0) { t.push({ type: 'op', value: c }); i++; continue; }
      throw new Error('Cannot understand the character "' + c + '".');
    }
    return t;
  }

  // ---------- parser (precedence climbing) ----------
  function parse(tokens) {
    var pos = 0;
    function peek() { return tokens[pos]; }
    function eat(v) {
      var t = tokens[pos];
      if (!t || t.value !== v) throw new Error('Expected "' + v + '" in the formula.');
      pos++; return t;
    }

    function parseComparison() {
      var left = parseConcat();
      while (peek() && peek().type === 'op' && ['=', '<>', '<', '>', '<=', '>='].indexOf(peek().value) >= 0) {
        var op = tokens[pos++].value;
        left = { kind: 'bin', op: op, left: left, right: parseConcat() };
      }
      return left;
    }
    function parseConcat() {
      var left = parseAdditive();
      while (peek() && peek().value === '&') {
        pos++;
        left = { kind: 'bin', op: '&', left: left, right: parseAdditive() };
      }
      return left;
    }
    function parseAdditive() {
      var left = parseMultiplicative();
      while (peek() && (peek().value === '+' || peek().value === '-')) {
        var op = tokens[pos++].value;
        left = { kind: 'bin', op: op, left: left, right: parseMultiplicative() };
      }
      return left;
    }
    function parseMultiplicative() {
      var left = parsePower();
      while (peek() && (peek().value === '*' || peek().value === '/')) {
        var op = tokens[pos++].value;
        left = { kind: 'bin', op: op, left: left, right: parsePower() };
      }
      return left;
    }
    function parsePower() {
      var left = parseUnary();
      if (peek() && peek().value === '^') {
        pos++;
        return { kind: 'bin', op: '^', left: left, right: parsePower() };
      }
      return left;
    }
    function parseUnary() {
      if (peek() && (peek().value === '-' || peek().value === '+')) {
        var op = tokens[pos++].value;
        return { kind: 'unary', op: op, arg: parseUnary() };
      }
      return parsePostfix();
    }
    function parsePostfix() {
      var node = parsePrimary();
      while (peek() && peek().value === '%') { pos++; node = { kind: 'percent', arg: node }; }
      return node;
    }
    function parsePrimary() {
      var t = peek();
      if (!t) throw new Error('The formula ends too early.');
      if (t.type === 'num') { pos++; return { kind: 'num', value: t.value }; }
      if (t.type === 'str') { pos++; return { kind: 'str', value: t.value }; }
      if (t.type === 'ref') { pos++; return { kind: 'ref', value: t.value }; }
      if (t.type === 'range') { pos++; return { kind: 'range', value: t.value }; }
      if (t.type === 'name') {
        pos++;
        if (t.value === 'TRUE') return { kind: 'bool', value: true };
        if (t.value === 'FALSE') return { kind: 'bool', value: false };
        return { kind: 'badname', value: t.value };
      }
      if (t.type === 'func') {
        pos++; eat('(');
        var args = [];
        if (peek() && peek().value !== ')') {
          args.push(parseComparison());
          while (peek() && peek().value === ',') { pos++; args.push(parseComparison()); }
        }
        eat(')');
        return { kind: 'call', name: t.value, args: args };
      }
      if (t.value === '(') {
        pos++;
        var inner = parseComparison();
        eat(')');
        return inner;
      }
      throw new Error('Unexpected "' + t.value + '" in the formula.');
    }

    var ast = parseComparison();
    if (pos < tokens.length) throw new Error('Unexpected "' + tokens[pos].value + '" after the formula.');
    return ast;
  }

  // ---------- value helpers ----------
  function toNumber(v) {
    if (isErr(v)) return v;
    if (typeof v === 'number') return v;
    if (typeof v === 'boolean') return v ? 1 : 0;
    if (v === '' || v === null || v === undefined) return 0;
    var n = parseFloat(v);
    if (isNaN(n) || String(v).trim() !== String(n)) return VALUE();
    return n;
  }
  function toText(v) {
    if (isErr(v)) return v;
    if (typeof v === 'boolean') return v ? 'TRUE' : 'FALSE';
    if (v === null || v === undefined) return '';
    return String(v);
  }
  function truthy(v) {
    if (isErr(v)) return v;
    if (typeof v === 'boolean') return v;
    if (typeof v === 'number') return v !== 0;
    if (typeof v === 'string') {
      if (v.toUpperCase() === 'TRUE') return true;
      if (v.toUpperCase() === 'FALSE') return false;
    }
    return !!v;
  }
  function looseEqual(a, b) {
    if (typeof a === 'string' && typeof b === 'string') return a.toUpperCase() === b.toUpperCase();
    if (typeof a === 'number' && typeof b === 'string') { var n = parseFloat(b); return !isNaN(n) && n === a; }
    if (typeof b === 'number' && typeof a === 'string') { var m = parseFloat(a); return !isNaN(m) && m === b; }
    return a === b;
  }

  // Criteria used by COUNTIF / SUMIF families: ">100", "<>West", "West", 42
  function matchCriteria(value, crit) {
    var op = '=', target = crit;
    if (typeof crit === 'string') {
      var m = /^(<=|>=|<>|<|>|=)(.*)$/.exec(crit.trim());
      if (m) { op = m[1]; target = m[2].trim(); }
    }
    var tNum = (typeof target === 'number') ? target : parseFloat(target);
    var targetIsNum = (typeof target === 'number') || (target !== '' && !isNaN(tNum) && String(target).trim() === String(tNum));
    var vNum = (typeof value === 'number') ? value : parseFloat(value);
    var bothNum = targetIsNum && typeof vNum === 'number' && !isNaN(vNum) &&
                  (typeof value === 'number' || String(value).trim() === String(vNum));

    switch (op) {
      case '=':  return bothNum ? vNum === tNum : looseEqual(value, target);
      case '<>': return bothNum ? vNum !== tNum : !looseEqual(value, target);
      case '>':  return bothNum ? vNum > tNum : String(value).toUpperCase() > String(target).toUpperCase();
      case '<':  return bothNum ? vNum < tNum : String(value).toUpperCase() < String(target).toUpperCase();
      case '>=': return bothNum ? vNum >= tNum : String(value).toUpperCase() >= String(target).toUpperCase();
      case '<=': return bothNum ? vNum <= tNum : String(value).toUpperCase() <= String(target).toUpperCase();
    }
    return false;
  }

  // Flatten call arguments into a plain list of scalars (ranges expand).
  function flatten(args) {
    var out = [];
    for (var i = 0; i < args.length; i++) {
      var a = args[i];
      if (a && a.isRange) out = out.concat(rangeValues(a));
      else out.push(a);
    }
    return out;
  }
  function numericList(args) {
    var vals = flatten(args), out = [];
    for (var i = 0; i < vals.length; i++) {
      var v = vals[i];
      if (isErr(v)) return v;
      if (typeof v === 'number') out.push(v);
      else if (typeof v === 'boolean') out.push(v ? 1 : 0);
      else if (typeof v === 'string' && v.trim() !== '' && !isNaN(parseFloat(v)) && String(parseFloat(v)) === v.trim()) out.push(parseFloat(v));
    }
    return out;
  }

  // ---------- functions ----------
  var FUNCS = {
    SUM: function (a) { var n = numericList(a); if (isErr(n)) return n; return n.reduce(function (s, x) { return s + x; }, 0); },
    AVERAGE: function (a) {
      var n = numericList(a); if (isErr(n)) return n;
      if (!n.length) return DIV0();
      return n.reduce(function (s, x) { return s + x; }, 0) / n.length;
    },
    COUNT: function (a) { var n = numericList(a); if (isErr(n)) return n; return n.length; },
    COUNTA: function (a) {
      return flatten(a).filter(function (v) { return v !== '' && v !== null && v !== undefined; }).length;
    },
    MAX: function (a) { var n = numericList(a); if (isErr(n)) return n; return n.length ? Math.max.apply(null, n) : 0; },
    MIN: function (a) { var n = numericList(a); if (isErr(n)) return n; return n.length ? Math.min.apply(null, n) : 0; },
    ROUND: function (a) {
      var v = toNumber(a[0]); if (isErr(v)) return v;
      var d = a.length > 1 ? toNumber(a[1]) : 0; if (isErr(d)) return d;
      var f = Math.pow(10, d);
      return Math.round(v * f) / f;
    },
    ABS: function (a) { var v = toNumber(a[0]); return isErr(v) ? v : Math.abs(v); },
    LEN: function (a) { var v = toText(a[0]); return isErr(v) ? v : v.length; },
    UPPER: function (a) { var v = toText(a[0]); return isErr(v) ? v : v.toUpperCase(); },
    LOWER: function (a) { var v = toText(a[0]); return isErr(v) ? v : v.toLowerCase(); },
    CONCAT: function (a) {
      var vals = flatten(a), s = '';
      for (var i = 0; i < vals.length; i++) { if (isErr(vals[i])) return vals[i]; s += toText(vals[i]); }
      return s;
    },

    IF: function (a) {
      if (a.length < 2) return VALUE();
      var c = truthy(a[0]); if (isErr(c)) return c;
      if (c) return a[1];
      return a.length > 2 ? a[2] : false;
    },
    IFS: function (a) {
      for (var i = 0; i + 1 < a.length; i += 2) {
        var c = truthy(a[i]); if (isErr(c)) return c;
        if (c) return a[i + 1];
      }
      return NA();
    },
    IFERROR: function (a) { return isErr(a[0]) ? (a.length > 1 ? a[1] : '') : a[0]; },
    AND: function (a) {
      var vals = flatten(a);
      for (var i = 0; i < vals.length; i++) { var t = truthy(vals[i]); if (isErr(t)) return t; if (!t) return false; }
      return true;
    },
    OR: function (a) {
      var vals = flatten(a);
      for (var i = 0; i < vals.length; i++) { var t = truthy(vals[i]); if (isErr(t)) return t; if (t) return true; }
      return false;
    },
    NOT: function (a) { var t = truthy(a[0]); return isErr(t) ? t : !t; },

    VLOOKUP: function (a) {
      if (a.length < 3) return VALUE();
      var key = a[0], rg = a[1];
      if (isErr(key)) return key;
      if (!rg || !rg.isRange) return VALUE();
      var idx = toNumber(a[2]); if (isErr(idx)) return idx;
      if (idx < 1 || rg.c1 + idx - 1 > rg.c2) return REF();
      var approx = a.length > 3 ? truthy(a[3]) : true;
      var first = rangeColumn(rg, 0);
      if (!approx) {
        for (var i = 0; i < first.length; i++) if (looseEqual(first[i], key)) return cellValue(rg.grid, rg.r1 + i, rg.c1 + idx - 1);
        return NA();
      }
      var best = -1;
      for (var j = 0; j < first.length; j++) {
        var cv = first[j];
        if (looseEqual(cv, key)) { best = j; break; }
        var cn = parseFloat(cv), kn = parseFloat(key);
        if (!isNaN(cn) && !isNaN(kn) && cn <= kn) best = j;
      }
      if (best < 0) return NA();
      return cellValue(rg.grid, rg.r1 + best, rg.c1 + idx - 1);
    },

    XLOOKUP: function (a) {
      if (a.length < 3) return VALUE();
      var key = a[0], look = a[1], ret = a[2];
      if (isErr(key)) return key;
      if (!look || !look.isRange || !ret || !ret.isRange) return VALUE();
      var lv = rangeValues(look), rv = rangeValues(ret);
      for (var i = 0; i < lv.length; i++) if (looseEqual(lv[i], key)) return i < rv.length ? rv[i] : NA();
      return a.length > 3 ? a[3] : NA();
    },

    COUNTIF: function (a) {
      if (a.length < 2 || !a[0] || !a[0].isRange) return VALUE();
      var vals = rangeValues(a[0]), crit = a[1], n = 0;
      for (var i = 0; i < vals.length; i++) if (matchCriteria(vals[i], crit)) n++;
      return n;
    },
    COUNTIFS: function (a) {
      if (a.length < 2 || a.length % 2 !== 0) return VALUE();
      var pairs = [];
      for (var i = 0; i < a.length; i += 2) {
        if (!a[i] || !a[i].isRange) return VALUE();
        pairs.push({ vals: rangeValues(a[i]), crit: a[i + 1] });
      }
      var len = pairs[0].vals.length, n = 0;
      for (var r = 0; r < len; r++) {
        var ok = true;
        for (var p = 0; p < pairs.length; p++) if (!matchCriteria(pairs[p].vals[r], pairs[p].crit)) { ok = false; break; }
        if (ok) n++;
      }
      return n;
    },
    SUMIF: function (a) {
      if (a.length < 2 || !a[0] || !a[0].isRange) return VALUE();
      var vals = rangeValues(a[0]);
      var sumVals = (a.length > 2 && a[2] && a[2].isRange) ? rangeValues(a[2]) : vals;
      var total = 0;
      for (var i = 0; i < vals.length; i++) {
        if (matchCriteria(vals[i], a[1])) {
          var n = parseFloat(sumVals[i]);
          if (!isNaN(n)) total += n;
        }
      }
      return total;
    },
    SUMIFS: function (a) {
      if (a.length < 3 || (a.length - 1) % 2 !== 0) return VALUE();
      if (!a[0] || !a[0].isRange) return VALUE();
      var sumVals = rangeValues(a[0]), pairs = [];
      for (var i = 1; i < a.length; i += 2) {
        if (!a[i] || !a[i].isRange) return VALUE();
        pairs.push({ vals: rangeValues(a[i]), crit: a[i + 1] });
      }
      var total = 0;
      for (var r = 0; r < sumVals.length; r++) {
        var ok = true;
        for (var p = 0; p < pairs.length; p++) if (!matchCriteria(pairs[p].vals[r], pairs[p].crit)) { ok = false; break; }
        if (ok) { var n = parseFloat(sumVals[r]); if (!isNaN(n)) total += n; }
      }
      return total;
    },
    AVERAGEIF: function (a) {
      if (a.length < 2 || !a[0] || !a[0].isRange) return VALUE();
      var vals = rangeValues(a[0]);
      var srcVals = (a.length > 2 && a[2] && a[2].isRange) ? rangeValues(a[2]) : vals;
      var total = 0, count = 0;
      for (var i = 0; i < vals.length; i++) {
        if (matchCriteria(vals[i], a[1])) {
          var n = parseFloat(srcVals[i]);
          if (!isNaN(n)) { total += n; count++; }
        }
      }
      return count ? total / count : DIV0();
    }
  };

  // ---------- evaluator ----------
  function evalNode(node, grid) {
    switch (node.kind) {
      case 'num': return node.value;
      case 'str': return node.value;
      case 'bool': return node.value;
      case 'badname': return NAME();
      case 'ref': {
        var p = parseRef(node.value);
        if (!p) return REF();
        return cellValue(grid, p.row, p.col);
      }
      case 'range': {
        var a = parseRef(node.value[0]), b = parseRef(node.value[1]);
        if (!a || !b) return REF();
        return makeRange(grid, a.row, a.col, b.row, b.col);
      }
      case 'percent': {
        var pv = toNumber(evalNode(node.arg, grid));
        return isErr(pv) ? pv : pv / 100;
      }
      case 'unary': {
        var uv = toNumber(evalNode(node.arg, grid));
        if (isErr(uv)) return uv;
        return node.op === '-' ? -uv : uv;
      }
      case 'call': {
        var fn = FUNCS[node.name];
        if (!fn) return NAME();
        var args = [];
        for (var i = 0; i < node.args.length; i++) {
          var v = evalNode(node.args[i], grid);
          // IF/IFS/IFERROR must see errors as values, not short-circuit on them.
          if (isErr(v) && node.name !== 'IFERROR' && node.name !== 'IF' && node.name !== 'IFS') return v;
          args.push(v);
        }
        return fn(args);
      }
      case 'bin': {
        var l = evalNode(node.left, grid), r = evalNode(node.right, grid);
        if (l && l.isRange) l = rangeValues(l)[0];
        if (r && r.isRange) r = rangeValues(r)[0];
        if (isErr(l)) return l;
        if (isErr(r)) return r;
        if (node.op === '&') {
          var lt = toText(l), rt = toText(r);
          if (isErr(lt)) return lt;
          if (isErr(rt)) return rt;
          return lt + rt;
        }
        if (['=', '<>', '<', '>', '<=', '>='].indexOf(node.op) >= 0) {
          var bothNumeric = typeof l === 'number' && typeof r === 'number';
          switch (node.op) {
            case '=':  return looseEqual(l, r);
            case '<>': return !looseEqual(l, r);
            case '>':  return bothNumeric ? l > r : String(l).toUpperCase() > String(r).toUpperCase();
            case '<':  return bothNumeric ? l < r : String(l).toUpperCase() < String(r).toUpperCase();
            case '>=': return bothNumeric ? l >= r : String(l).toUpperCase() >= String(r).toUpperCase();
            case '<=': return bothNumeric ? l <= r : String(l).toUpperCase() <= String(r).toUpperCase();
          }
        }
        var ln = toNumber(l), rn = toNumber(r);
        if (isErr(ln)) return ln;
        if (isErr(rn)) return rn;
        switch (node.op) {
          case '+': return ln + rn;
          case '-': return ln - rn;
          case '*': return ln * rn;
          case '/': return rn === 0 ? DIV0() : ln / rn;
          case '^': return Math.pow(ln, rn);
        }
        return VALUE();
      }
    }
    return VALUE();
  }

  // Returns { ok:true, value } or { ok:false, message }
  function evaluate(formula, grid) {
    var src = String(formula == null ? '' : formula).trim();
    if (src === '') return { ok: false, message: 'Type a formula first, starting with =' };
    if (src.charAt(0) !== '=') return { ok: false, message: 'An Excel formula must start with = ' };
    src = src.slice(1);
    try {
      var value = evalNode(parse(tokenize(src)), grid);
      if (value && value.isRange) {
        var vals = rangeValues(value);
        value = vals.length === 1 ? vals[0] : VALUE();
      }
      return { ok: true, value: value };
    } catch (e) {
      return { ok: false, message: e.message || String(e) };
    }
  }

  function formatValue(v) {
    if (isErr(v)) return v.code;
    if (typeof v === 'boolean') return v ? 'TRUE' : 'FALSE';
    if (typeof v === 'number') {
      if (!isFinite(v)) return '#NUM!';
      return (Math.round(v * 1e10) / 1e10).toString();
    }
    return String(v);
  }

  // ---------- rendering ----------
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function renderSheet(grid, highlight) {
    var h = '<table class="nerdit-xl-table"><thead><tr><th class="nerdit-xl-corner"></th>';
    for (var c = 0; c < grid.colCount; c++) h += '<th class="nerdit-xl-colhead">' + indexToCol(c) + '</th>';
    h += '</tr></thead><tbody>';
    for (var r = 0; r < grid.rowCount; r++) {
      h += '<tr><th class="nerdit-xl-rowhead">' + (r + 1) + '</th>';
      for (var c2 = 0; c2 < grid.colCount; c2++) {
        var v = grid.cells[r][c2];
        if (v === undefined || v === null) v = '';
        var cls = 'nerdit-xl-cell';
        if (r === 0) cls += ' is-header';
        if (typeof v === 'number') cls += ' is-num';
        if (highlight && highlight.r === r && highlight.c === c2) cls += ' is-hit';
        h += '<td class="' + cls + '">' + esc(v) + '</td>';
      }
      h += '</tr>';
    }
    return h + '</tbody></table>';
  }

  function readGridData(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try {
      var data = JSON.parse(el.textContent);
      return makeGrid(data.headers, data.rows);
    } catch (e) { return null; }
  }

  function gridFor(box) {
    if (box.__grid) return box.__grid;
    var g = readGridData(box.getAttribute('data-grid'));
    box.__grid = g;
    return g;
  }

  // ---------- public: formula widget ----------
  function runExcel(btn) {
    var box = btn.closest ? btn.closest('.nerdit-xl') : null;
    if (!box) return;
    var grid = gridFor(box);
    var out = box.querySelector('.nerdit-xl-result');
    if (!grid) { out.innerHTML = '<div class="nerdit-tryit-error">Demo data is missing for this widget.</div>'; return; }
    var input = box.querySelector('.nerdit-xl-input');
    var res = evaluate(input.value, grid);
    if (!res.ok) {
      out.innerHTML = '<div class="nerdit-tryit-error"></div>';
      out.firstChild.textContent = res.message;
      return;
    }
    var text = formatValue(res.value);
    var bad = isErr(res.value);
    out.innerHTML = '<div class="nerdit-xl-out' + (bad ? ' error' : '') + '">' +
      '<span class="nerdit-xl-out-label">Result</span>' +
      '<span class="nerdit-xl-out-val"></span></div>';
    out.querySelector('.nerdit-xl-out-val').textContent = text;
  }

  // ---------- public: pivot builder ----------
  function buildPivot(box) {
    var grid = gridFor(box);
    var out = box.querySelector('.nerdit-xl-pivot-result');
    if (!grid) { out.innerHTML = ''; return; }
    var rowField = box.querySelector('[data-role="rowField"]').value;
    var valField = box.querySelector('[data-role="valueField"]').value;
    var aggName = box.querySelector('[data-role="agg"]').value;

    var rIdx = grid.headers.indexOf(rowField);
    var vIdx = grid.headers.indexOf(valField);
    if (rIdx < 0 || vIdx < 0) { out.innerHTML = ''; return; }

    var groups = {}, order = [];
    for (var i = 0; i < grid.rows.length; i++) {
      var key = String(grid.rows[i][rIdx]);
      if (!(key in groups)) { groups[key] = []; order.push(key); }
      var n = parseFloat(grid.rows[i][vIdx]);
      groups[key].push(isNaN(n) ? grid.rows[i][vIdx] : n);
    }
    order.sort();

    var agg = function (list) {
      var nums = list.filter(function (x) { return typeof x === 'number'; });
      if (aggName === 'COUNT') return list.length;
      if (!nums.length) return 0;
      var sum = nums.reduce(function (s, x) { return s + x; }, 0);
      if (aggName === 'SUM') return sum;
      if (aggName === 'AVERAGE') return Math.round((sum / nums.length) * 100) / 100;
      if (aggName === 'MAX') return Math.max.apply(null, nums);
      if (aggName === 'MIN') return Math.min.apply(null, nums);
      return sum;
    };

    var label = aggName.charAt(0) + aggName.slice(1).toLowerCase() + ' of ' + valField;
    var h = '<table class="nerdit-xl-table nerdit-xl-pivot"><thead><tr>' +
            '<th class="nerdit-xl-colhead">' + esc(rowField) + '</th>' +
            '<th class="nerdit-xl-colhead">' + esc(label) + '</th></tr></thead><tbody>';
    var grand = [];
    for (var k = 0; k < order.length; k++) {
      var val = agg(groups[order[k]]);
      grand = grand.concat(groups[order[k]]);
      h += '<tr><td class="nerdit-xl-cell">' + esc(order[k]) + '</td>' +
           '<td class="nerdit-xl-cell is-num">' + esc(formatValue(val)) + '</td></tr>';
    }
    h += '<tr class="nerdit-xl-total"><td class="nerdit-xl-cell">Grand Total</td>' +
         '<td class="nerdit-xl-cell is-num">' + esc(formatValue(agg(grand))) + '</td></tr>';
    out.innerHTML = h + '</tbody></table>';
  }

  function pivotChanged(el) {
    var box = el.closest ? el.closest('.nerdit-xl-pivotbox') : null;
    if (box) buildPivot(box);
  }

  // ---------- init ----------
  function init(root) {
    var scope = root || document;
    var sheets = scope.querySelectorAll('.nerdit-xl-sheet[data-grid]');
    for (var i = 0; i < sheets.length; i++) {
      var el = sheets[i];
      if (el.getAttribute('data-rendered') === '1') continue;
      var g = readGridData(el.getAttribute('data-grid'));
      if (g) { el.innerHTML = renderSheet(g); el.setAttribute('data-rendered', '1'); }
    }
    var pivots = scope.querySelectorAll('.nerdit-xl-pivotbox');
    for (var p = 0; p < pivots.length; p++) buildPivot(pivots[p]);
  }

  window.NerditExcel = {
    evaluate: evaluate,
    makeGrid: makeGrid,
    formatValue: formatValue,
    renderSheet: renderSheet,
    init: init
  };
  window.nerditExcelInit = init;
  window.nerditRunExcel = runExcel;
  window.nerditPivotChanged = pivotChanged;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { init(); });
  else init();
})();
