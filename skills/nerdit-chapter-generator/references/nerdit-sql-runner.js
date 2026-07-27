/* NERDIT SQL runner — sql.js (SQLite compiled to WebAssembly).
 *
 * Lazy-loads the engine from CDN on the learner's first Run click, so a lesson
 * that is never run costs nothing at page load. Seeded per run from the
 * <script type="text/plain"> block named by the widget's data-seed, so the
 * learner always queries exactly the data shown on the page.
 *
 * Served by the website at /nerdit-sql-runner.js. Source of truth lives in the
 * nerdit plugin's references/ directory.
 */
(function () {
  if (typeof window.nerditRunSql !== "function") {
    window.nerditRunSql = function (btn) {
      var box = btn.closest('.nerdit-tryit');
      var status = box.querySelector('.nerdit-tryit-status');
      var out = box.querySelector('.nerdit-tryit-result');
      var run = function(SQL){
        try {
          var db = new SQL.Database();
          var seedEl = document.getElementById(box.getAttribute('data-seed'));
          if (seedEl) db.run(seedEl.textContent);
          var res = db.exec(box.querySelector('.nerdit-tryit-editor').value);
          status.textContent = '';
          if (!res.length) { out.innerHTML = '<div class="nerdit-tryit-empty">Query ran. No rows returned.</div>'; db.close(); return; }
          var r = res[res.length - 1], h = '<table class="nerdit-result-table"><thead><tr>';
          r.columns.forEach(function(c){ h += '<th>' + c + '</th>'; });
          h += '</tr></thead><tbody>';
          r.values.forEach(function(row){
            h += '<tr>';
            row.forEach(function(v){ h += '<td>' + (v === null ? 'NULL' : String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;')) + '</td>'; });
            h += '</tr>';
          });
          out.innerHTML = h + '</tbody></table>';
          db.close();
        } catch (e) {
          status.textContent = '';
          out.innerHTML = '<div class="nerdit-tryit-error">Error: ' + String(e.message || e).replace(/</g,'&lt;') + '</div>';
        }
      };
      if (window.__nerditSQL) return run(window.__nerditSQL);
      status.textContent = 'Loading SQL engine…';
      var boot = function(){
        window.initSqlJs({ locateFile: function(f){ return 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.2/' + f; } })
          .then(function(SQL){ window.__nerditSQL = SQL; run(SQL); });
      };
      if (window.initSqlJs) return boot();
      var s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.2/sql-wasm.js';
      s.onload = boot;
      s.onerror = function(){ status.textContent = 'Could not load the SQL engine. Check your internet connection.'; };
      document.head.appendChild(s);
    };
  }
})();
