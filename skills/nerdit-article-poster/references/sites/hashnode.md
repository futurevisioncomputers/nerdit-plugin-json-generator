# hashnode

- **Start:** https://hashnode.com/
- **Signed in when:** 'Good morning, <name>' and the Write button
- **Kit:** Articles page -> Copy text
- **Steps:**
  1. Write (top left) -> a new draft opens (hashnode.com/draft/<id>; it can take ~15 s to load). The editor is
     already in Markdown mode (Rich | Markdown toggle).
  2. Paste the kit into the body textarea ('Start writing markdown...'). Move the first line (the title) into
     'Article title...' and drop it (and the blank line after it) from the body. Both are plain textareas: set
     them with the native value setter + an `input` event if typing is slow.
- **Images:** the kit's image links point at NerdIT storage (firebasestorage.googleapis.com), which every reader
  would download at the owner's cost, so move them to Hashnode: put the article's PNGs in a page `<input type=file>`
  (Chrome file upload), then dispatch `dragenter`/`dragover`/`drop` DragEvents carrying each file onto the body
  textarea. Hashnode uploads each to cdn.hashnode.com and appends `![name](https://cdn.hashnode.com/...)` at the end.
  Swap each firebasestorage URL in the body for its cdn.hashnode.com one (match by file name) and delete the appended
  line. Check: no `firebasestorage` left; Preview (eye icon) shows the 3 images at 1600 px.
  Cover: the page's hidden `input[type=file]` (accept image/*) is the cover slot: upload the cover PNG there.
- **Canonical / original URL:** Publish panel -> Discovery -> 'Are you republishing?' -> tick 'Add a canonical URL'
  -> the nerdit.in article URL.
- **Publish:** Publish (top right) opens 'Draft settings'; it does not publish yet. Discovery tab: Tags (type, then
  Enter picks the top match: #machine-learning, #python, #data-science, ... up to 5), SEO description (the article's
  description), canonical as above. Then the panel's own Publish button at the bottom. 'Article published
  successfully!' toast.
- **Post URL:** https://nerdit.hashnode.dev/<slug>. Check the live page: `<link rel="canonical">` = nerdit.in, the
  body images are cdn.hashnode.com, no firebasestorage. (og:image is Hashnode's generated card; the cover is in
  the page's `coverImage`, that is normal.)
- **Verified:** yes, 2026-11-24 (career-roadmap article: CDN images, cover, 5 tags, canonical nerdit.in)
