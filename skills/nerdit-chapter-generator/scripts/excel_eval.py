#!/usr/bin/env python3
"""Evaluate Excel formulas with the plugin's own engine, the one the lesson's Try It runs.

A drawn sheet screen shows a formula's result. That value must be what the learner gets when
they type the formula into the Try It, so it comes from references/nerdit-excel-engine.js run in
Node, never from a Python re-implementation. One Node process per call.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "references" / "nerdit-excel-engine.js"

# The engine is a browser script: give it a window and a document that is still loading, so it
# registers window.NerditExcel without trying to render a page.
PROGRAM = r"""
globalThis.window = globalThis;
globalThis.document = {readyState: "loading", addEventListener() {}};
require(__ENGINE__);
const fs = require("fs");
const input = JSON.parse(fs.readFileSync(process.env.NERDIT_XL_IN, "utf8"));
const X = window.NerditExcel;
const grid = X.makeGrid(input.headers, input.rows);
const out = input.formulas.map((f) => {
  const r = X.evaluate(f, grid);
  if (!r.ok) return {error: r.message};
  const v = r.value;
  if (v && typeof v === "object" && "code" in v) return {error: v.code};
  return {value: v, text: X.formatValue(v)};
});
process.stdout.write(JSON.stringify(out));
"""


def evaluate_many(headers: list, rows: list, formulas: list[str]) -> list[dict]:
    """[{"value", "text"} | {"error"}] for each formula, in order."""
    if not formulas:
        return []
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for Excel screens: install Node 18+")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.json"
        src.write_text(json.dumps({"headers": headers, "rows": rows, "formulas": formulas}), encoding="utf-8")
        proc = subprocess.run([node, "-"], input=PROGRAM.replace("__ENGINE__", json.dumps(str(ENGINE))),
                              capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
                              env={**os.environ, "NERDIT_XL_IN": str(src)})
    if proc.returncode != 0:
        last = (proc.stderr.strip().splitlines() or ["node exited with an error"])[-1]
        raise RuntimeError(f"Excel engine failed: {last}")
    return json.loads(proc.stdout)
