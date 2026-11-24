# hashnode

- **Start:** https://hashnode.com/
- **Signed in when:** 'Good morning, <name>' and the Write button
- **Kit:** Articles page -> Copy text
- **Steps:**
  1. Write (top left) -> a new draft opens (hashnode.com/draft/<id>; it can take ~15 s to load).
  2. Switch the editor to Markdown (Rich | Markdown toggle).
  3. Paste the kit into the body; move the first line (the title) into 'Article title...'.
- **Images:** Markdown image links show by themselves, but then every reader downloads them from NerdIT storage
  (firebasestorage.googleapis.com), which costs the owner. So put each image on Hashnode instead: upload the pack PNGs
  through the editor's image upload (they land on cdn.hashnode.com) and swap each firebasestorage link in the text for
  the cdn.hashnode.com one. Check: the live page has no firebasestorage image. (Not tried yet; record what works.)
  Cover: Cover (above the title) -> Upload Image -> the article cover PNG.
- **Canonical / original URL:** In the Publish panel: 'Are you republishing?' -> the nerdit.in article URL (see Publish).
- **Publish:** Publish (top right) opens the 'Draft settings' panel; it does not publish yet. Discovery tab: Tags (type,
  pick from the list: #machine-learning, #python ...), SEO description (the article's description), and 'Are you
  republishing?' -> paste the nerdit.in article URL (the canonical). Stop and get the owner's yes, then the panel's own
  Publish button at the bottom publishes. Check the live page has <link rel="canonical"> pointing at nerdit.in.
- **Post URL:** https://<blog>.hashnode.dev/<slug> (for this owner: nerdit.hashnode.dev).
- **Verified:** yes, 2026-11-23 (Regression how-to: nerdit.hashnode.dev/supervised-machine-learning-regression-algorithms-with-python-a-practical-how-to-guide, canonical nerdit.in, 3 images)
