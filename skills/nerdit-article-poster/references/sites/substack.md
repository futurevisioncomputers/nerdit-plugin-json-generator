# substack

- **Since 2026-11-26:** posted by GitHub Actions every night at 02:15 IST, web only (private repo
  `futurevisioncomputers/nerdit-cloud-poster`, `substack-post.yml`; what it posted: `state/substack.json`). Scheduled PC
  runs never do Substack. Use the steps below only when the owner asks by hand.
- **Start:** https://substack.com/home (publication: nerditin.substack.com, made 2026-11-24)
- **Signed in when:** the left sidebar with Home / Create (signed out: the orange landing page with 'Sign in').
  Signed out: sign-in is by an emailed link or code, so the owner does it (scheduled run: skip "sign in needed").
- **Kit:** opening + link (Articles page -> Copy text). The real clipboard is not reliable (it can hold something
  else by the time you paste), so build the same kit as HTML: the article's first ~250 words up to the end of a
  paragraph or list (the admin's `articleOpening`), then `<p><strong>Read the full article on NerdIT:</strong>
  <a href="URL">URL</a></p>` with URL = the article URL +
  `?utm_source=substack&utm_medium=excerpt&utm_campaign=<slug>`.
- **Steps:**
  1. Create (left) -> Article. The editor opens at nerditin.substack.com/publish/post/<id>.
  2. Title textarea = the article title; subtitle = the article description.
  3. Body (`.tiptap.ProseMirror`): focus it, caret at start, dispatch a `paste` ClipboardEvent whose DataTransfer
     has `text/html` = the kit HTML. Check: 1 heading, the list items, 1 link.
- **Canonical / original URL:** None. The kit is only the opening and ends with the link to NerdIT.
- **Images:** none needed (the opening has no images). The 'Upload' file input on the page is the file sidebar's
  thumbnail, not a body image.
- **Publish:** Continue (top right) -> Delivery: untick 'Send via email and the Substack app' -> 'Publish now' ->
  dialog 'Do you want to send this post via email?' -> 'Publish on web only'. Never send email to subscribers
  unless the owner says so.
- **Post URL:** the share page's link input: https://nerditin.substack.com/p/<slug> (drop the `?r=` part).
- **Verified:** yes, 2026-11-24 (career-roadmap article, web only)
