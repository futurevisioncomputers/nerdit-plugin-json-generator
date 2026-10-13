# Runner: SQL (sql.js)

Load the engine once per lesson, after the demo-data block:

<script src="/nerdit-sql-runner.js"></script>


**SQL variant** — needs a seed block that recreates the demo tables from §5, so the
learner queries the exact data shown on the page.
```html
<div class="nerdit-tryit" data-seed="tryit-seed-1">
  <div class="nerdit-tryit-head">▶ Try It Yourself — edit the SQL and run it</div>
  <textarea class="nerdit-tryit-editor" rows="4" spellcheck="false">SELECT name, city FROM customers WHERE city = 'Surat';</textarea>
  <div class="nerdit-tryit-bar">
    <button class="nerdit-run-btn" onclick="nerditRunSql(this)">Run SQL ▶</button>
    <span class="nerdit-tryit-status" aria-live="polite"></span>
  </div>
  <div class="nerdit-tryit-result"></div>
</div>
<script type="text/plain" id="tryit-seed-1">
CREATE TABLE customers (id INT, name TEXT, city TEXT, age INT);
INSERT INTO customers VALUES (1,'Aarav','Surat',21),(2,'Diya','Surat',24),
(3,'Kabir','Mumbai',28),(4,'Meera','Delhi',19);
</script>
```
The seed script recreates the demo table from §5 — the learner runs queries against the
exact data shown on the page. `data-seed` points at the seed block's `id`. sql.js
(SQLite compiled to WebAssembly) is lazy-loaded from CDN only when the learner first
clicks Run — zero page-load cost.

**Editor size and colour are the website's job.** The website fits the textarea to its
code and colours it like the lesson's code blocks, so `rows` is only the no-script
fallback. Write a query of more than one clause on several lines (`FROM`, `WHERE`,
`ORDER BY` each starting a line); a long one-line query is laid out that way
automatically, but the written layout is what the plugin's own previews show.
