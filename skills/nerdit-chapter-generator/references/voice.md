# VOICE — write like a teacher talking

`check_prose.py` reads this file. A lesson **fails** on any phrase in the `banned` block below
and gets **warnings** for:
- sentences over 15 words
- paragraphs over 3 sentences
- more than one em dash in a paragraph
- concept sections that all open with the same two words

Code, tables and figures are not prose and are never checked.

Why: these phrases and that rhythm make a lesson read as machine-written. A learner trusts a
teacher who talks plainly.

- Contractions are welcome: "you'll", "it's", "don't".
- Open sections in different ways: a question, a short story beat, a surprising number, a picture.
- Name real things from the course's world: the store, the person, the amount.

One phrase per line. A line starting `re:` is a regular expression (case-insensitive).

```banned
delve
crucial
seamless
seamlessly
leverage
robust
utilize
let's dive in
dive into
it's important to note
it is important to note
in today's world
in today's fast-paced
furthermore
moreover
additionally
in conclusion
unlock the power
harness the power
game-changer
plays a vital role
plays a crucial role
a testament to
navigate the complexities
embark on
re:\bnot only\b.{1,60}?\bbut also\b
```
