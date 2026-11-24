# wordpress

- **How:** by API from the Articles page, never in the WordPress editor. New articles usually post by themselves
  when published ('Connected: posts by itself when you publish'); this covers articles that missed it.
- **Start:** fv.nerdit.in/articles -> the article -> Edit -> the WordPress.com row
- **Signed in when:** the row says 'Connected' and shows a **Post copy** button (no button: connection missing ->
  `failed` with "WordPress.com not connected in the admin" and a report line for the owner)
- **Kit:** none to copy: the admin sends its own copy (opening + link).
- **Steps:**
  1. Press **Post copy**. Wait for the toast 'Posted on WordPress.com.' The row then shows
     '✓ futurevisioncomputers.wordpress.com/...' and its button turns into Update copy.
- **Canonical / original URL:** None (custom canonical needs a paid plan). The copy is the opening + link.
- **Images:** None to upload.
- **Publish:** Post copy publishes it.
- **Post URL:** the row's link (https://futurevisioncomputers.wordpress.com/<yyyy>/<mm>/<dd>/<slug>/). It is
  saved on the Articles page already; only `runlog mark ... --status posted --url <link>`.
- **Never:** press **Update copy** (that edits a live copy; the owner decides).
- **Verified:** yes, 2026-11-24
