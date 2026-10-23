# VOICE — write like a teacher talking

`check_prose.py` reads this file. A lesson **fails** on:
- any phrase in the `banned` block below
- any hard word in the `plain` block below (it names the simpler word to use)
- sentences over 20 words
- a concept section with more than 3 key terms (`<strong>`)
- a concept section that opens with a story or example: explain the idea first, with its key
  word in the first paragraph (or the second, after a one-sentence question), then the case study

and gets **warnings** for:
- paragraphs over 4 sentences
- a concept section with under 300 words of explanation
- more than one em dash in a paragraph
- concept sections that all open with the same two words

Code, tables and figures are not prose and are never checked.

Why: these phrases and that rhythm make a lesson read as machine-written. A learner trusts a
teacher who talks plainly.

- Contractions are welcome: "you'll", "it's", "don't".
- Open sections in different ways: a question, the problem stated plainly, a surprising number.
  Never a story first; the story is the case study that follows the explanation.
- Name real things from the course's world in the case study: the branch, the person, the record.

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

Plain words: a beginner reads the simpler word faster. One `hard => simpler` pair per line.
A technical term the lesson teaches is never in this list.

```plain
facilitate => help
subsequently => then
approximately => about
commence => start
demonstrate => show
numerous => many
sufficient => enough
prior to => before
in order to => to
ascertain => find out
constitute => make up
comprehensive => full
methodology => method
mitigate => reduce
endeavour => try
bounded => limited
aforementioned => this
henceforth => from now on
whereby => where
thereby => so
nevertheless => still
optimal => best
utilise => use
```
