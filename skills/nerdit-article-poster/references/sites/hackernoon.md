# hackernoon

- **Start:** https://app.hackernoon.com/new -> 'Blank Draft With Editor 3.0' -> Start Draft
- **Signed in when:** your avatar in the header. Profile is done (2026-11-24: bio, NerdIT avatar, work history
  'Founder, Future Vision Computers Institute'). If /onboarding or 'WORK HISTORY REQUIRED' shows anyway, follow
  `references/profile.md`.
- **Kit:** not the Copy text kit: the editor keeps pasted Markdown as raw text (no headings, links or images).
- **Steps:**
  1. Title: click 'Title' (a 100-character textarea; a long title wraps to 3 lines, so a click lower down lands in
     the title, not the body). Type the article title.
  2. Body: open the live article (https://nerdit.in/blog/<slug>) in another tab, append a footer paragraph to its
     `<article>` ("*Originally published at* NerdIT (link to the article). NerdIT offers free online courses ... —
     browse the courses (https://nerdit.in/courses/?utm_source=hackernoon&utm_medium=syndication&utm_campaign=<slug>)"),
     select the `<article>` contents and press Ctrl+C. In the HackerNoon tab focus the `.ProseMirror` body (JS
     `focus()` + caret at start) and press Ctrl+V: headings, lists, links and images come across.
  3. Images: the pasted images still load from NerdIT storage. Move each to cdn.hackernoon.com: put the caret at the
     start of the block after the image, then upload the PNG to the editor's own hidden image input (the file input
     inside the editor menu, accept image/*). It replaces that image (and its caption) with a cdn.hackernoon.com
     one. Then type the caption into the image block's caption field (`div.image [contenteditable=true]`).
     Drop events and pasted files do nothing here.
- **Canonical / original URL:** in Story settings: original = No -> the nerdit.in article URL, Personal Site,
  Backlink (see below).
- **Story settings** (gear, top right): featured image = 'Browse File' -> the cover PNG -> Upload; Metadescription
  = the article description; Category = AI and ML (or what fits); Story Tags = 3-4 (machine-learning, python,
  data-science, ...); 'Is this story original on HackerNoon?' = No -> first published URL = the nerdit.in article
  -> 'Is this URL a...' = **Personal Site** (owner's decision 2026-11-24; Business Site means buying credits) ->
  distribution = **Backlink** (adds 'Also published here' with the canonical link). 'Path to Submission' must read 7/7.
- **Publish:** 'Submit Story' (top left) -> confirm dialog 'Do you have the rights to publish this content and have
  you disclosed all vested interests ...' -> 'Yes, I'm ready to submit.' -> 'Draft submitted!' and the story moves
  to 'Stories in Editorial' (app.hackernoon.com/writer/tracksubmissions). The bottom 'Submit Story for Review!'
  button alone does not submit.
- **Post URL:** not live yet: editors review it. Log `posted` with the draft URL
  (https://app.hackernoon.com/mobile/<draft id>); do not save it on the Articles page. Report line: "<slug>: HackerNoon
  in review, paste the live link from the review email".
- **Verified:** yes, 2026-11-24 (submitted; review pending)
