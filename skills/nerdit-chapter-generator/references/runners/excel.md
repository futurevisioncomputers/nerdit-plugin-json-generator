# Runner: Excel

### 6d. Excel widgets (spreadsheet courses)

Excel has no public engine to embed, so the plugin ships its own:
`references/nerdit-excel-engine.js`. Load it once per lesson with
`<script src="/nerdit-excel-engine.js"></script>` placed after the demo-data block.
Use the **absolute** path (leading `/`) — the LMS renders lessons at routes like
`/course/<id>`, and a relative `src` would resolve against that route and 404. The file
is served from the site root (the app's `public/` folder).
It supports only the functions the v9 Excel lessons teach: `SUM AVERAGE COUNT COUNTA
MAX MIN ROUND ABS LEN UPPER LOWER CONCAT IF IFS IFERROR AND OR NOT VLOOKUP XLOOKUP
COUNTIF COUNTIFS SUMIF SUMIFS AVERAGEIF`, plus `+ - * / ^ % &` and the comparison
operators, cell refs (`B3`, `$B$3`) and ranges (`B2:E8`). Anything else returns `#NAME?`.

**Demo data** — one JSON block per lesson, referenced by id. Row 1 is the header row,
so data row 1 sits on sheet row 2 (exactly like a real sheet):
```html
<script type="application/json" id="xl-sales">
{ "headers": ["ID","Name","Region","Product","Amount"],
  "rows": [[101,"Aarav","West","Laptop",180000], [102,"Diya","West","Mouse",1300]] }
</script>
```

**Render the sheet** anywhere (usually inside `nerdit-demo-table`) — the engine fills it:
```html
<div class="nerdit-xl-sheet" data-grid="xl-sales"></div>
```

**Formula runner** (the Excel equivalent of the SQL/Python Try It):
```html
<div class="nerdit-xl" data-grid="xl-sales">
  <div class="nerdit-xl-head">▶ Try It Yourself — type a formula and run it</div>
  <div class="nerdit-xl-bar">
    <span class="nerdit-xl-fx">fx</span>
    <input class="nerdit-xl-input" spellcheck="false" value='=VLOOKUP("Kabir",B1:E8,4,FALSE)'>
    <button class="nerdit-run-btn" onclick="nerditRunExcel(this)">Run ▶</button>
  </div>
  <div class="nerdit-xl-presets">
    <button class="nerdit-xl-preset" onclick="nerditLoadFormula(this)">=SUM(E2:E8)</button>
  </div>
  <div class="nerdit-xl-result"></div>
</div>
```
Preset chips are optional but recommended — a learner can try a formula without typing.
Their text content IS the formula, so write it exactly as it should run.

**Pivot builder** — for PivotTable lessons, where there is no formula to type:
```html
<div class="nerdit-xl-pivotbox nerdit-xl" data-grid="xl-sales">
  <div class="nerdit-xl-head">▶ Try It Yourself — build a PivotTable</div>
  <div class="nerdit-xl-controls">
    <div class="nerdit-xl-field"><label for="pv-row">Rows</label>
      <select id="pv-row" data-role="rowField" onchange="nerditPivotChanged(this)">
        <option>Region</option><option>Product</option></select></div>
    <div class="nerdit-xl-field"><label for="pv-val">Values</label>
      <select id="pv-val" data-role="valueField" onchange="nerditPivotChanged(this)">
        <option>Amount</option></select></div>
    <div class="nerdit-xl-field"><label for="pv-agg">Summarise by</label>
      <select id="pv-agg" data-role="agg" onchange="nerditPivotChanged(this)">
        <option>SUM</option><option>COUNT</option><option>AVERAGE</option>
        <option>MAX</option><option>MIN</option></select></div>
  </div>
  <div class="nerdit-xl-pivot-result"></div>
</div>
```
The `data-role` values and the option text must match exactly — the builder reads the
row/value option text as a column name and looks it up in `headers`.

Excel lessons also need `nerditLoadFormula` in their lesson script:
```js
if (typeof window.nerditLoadFormula !== "function") {
  window.nerditLoadFormula = function(btn){
    var box = btn.closest('.nerdit-xl');
    box.querySelector('.nerdit-xl-input').value = btn.textContent.trim();
    window.nerditRunExcel(box.querySelector('.nerdit-run-btn'));
  };
}
```

> **Every formula you document must actually evaluate to the output you claim.** The
> engine is the source of truth — if a worked example says the answer is `301300`, running
> that formula in the widget must produce `301300`. Verify before shipping the lesson.
