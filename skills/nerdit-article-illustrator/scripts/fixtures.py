"""Small article and course fixtures shared by the tests."""

ARTICLE = {
    "slug": "regression-basics",
    "title": "Regression Basics with Python",
    "description": "Predict a number from features.",
    "tags": ["Machine Learning"],
    "relatedCourseIds": ["reg-1"],
    "coverImage": "",
    "markdown": (
        "## What is regression?\n\n"
        "Regression predicts a number, like a house price, from features.\n\n"
        "```python\n## not a heading\nmodel.fit(X, y)\n```\n\n"
        "## Train and test\n\n"
        "Split the data into a Training set and a Test set before you fit.\n\n"
        "- Fit on the Training set\n- Score on the Test set\n\n"
        "## Evaluate\n\n"
        "Lower MAE means better predictions."
    ),
}

DIAGRAM = (
    '<svg viewBox="0 0 360 120" role="img" aria-label="Split the data into a Training set and a Test set">'
    '<title>Train and test</title>'
    '<rect x="10" y="30" width="200" height="60" fill="var(--nb-soft)" stroke="var(--nb)"/>'
    '<text x="110" y="65" text-anchor="middle" fill="var(--nb)">Training set</text>'
    '<rect x="230" y="30" width="120" height="60" fill="var(--nb-soft)" stroke="var(--nb)"/>'
    '<text x="290" y="65" text-anchor="middle" fill="var(--nb)">Test set</text>'
    '</svg>'
)

FIGURE = (
    '<div class="nerdit-figure" data-visual="flow" style="max-width:440px">'
    '<svg viewBox="0 0 360 80" role="img" aria-label="Fit then score"><title>Fit, then score</title>'
    '<text x="20" y="40" fill="var(--nb)">fit</text><text x="200" y="40" fill="var(--nb)">score</text></svg>'
    '<div class="nerdit-figure-caption">Fit on training rows, score on test rows.</div></div>'
)

COURSE = {
    "id": "reg-1", "slug": "regression-1", "title": "Regression Basics",
    "lessons": [
        {"id": "reg-01", "title": "Intro", "content": f"<p>Intro</p>{FIGURE}<p>More</p>"},
        {"id": "reg-02", "title": "Metrics", "content": "<p>No figures here.</p>" + FIGURE.replace("Fit then score", "Errors shrink")},
    ],
}
