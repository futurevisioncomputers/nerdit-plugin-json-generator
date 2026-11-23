# Article image style

Base rules: the lesson illustrator's `../nerdit-lesson-illustrator/references/style.md` and the figure
templates in `../nerdit-chapter-generator/references/figures.md`. The same SVG contract applies
(`svgcheck.py` enforces it). What is different for blog articles:

- **2 or 3 images per article.** More turns a reading article into a slide deck.
- **Teach, don't decorate.** Each image shows the idea of the paragraph it follows. No stock scenes,
  no AI art, no logos inside the figure.
- **Words from the article only.** Labels, numbers and names are copied from the article
  (diagrams) or are the course figure's own (reused figures). `build_pack.py` refuses anything else.
- **Light page.** White background; the lesson tokens give the colours. Code panels may be dark.
- **Readable in a copy.** The PNG is 1600 px wide and shown about 700 px wide on Medium, Dev.to and
  Hashnode: keep to the 400-unit viewBox so labels stay large.
- **alt** says what the picture shows in one sentence (for screen readers and Google Images).
- **caption** is one short plain line (at most about 90 characters), no "Figure 1".
- **Course figures** keep their course's look and get "from the NerdIT course <title>" in the
  caption, linked to the course preview (no UTM: it is an internal link on nerdit.in).
