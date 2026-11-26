# linkedin

- **Since 2026-11-26:** Publish on the Articles page books this post by itself (Social posts row
  `article-<slug>-linkedin`, a day later, 10:00 IST if that lands at night). Scheduled runs never do LinkedIn. Use
  the steps below only when the owner asks by hand, for an article published before 2026-11-26.
- **How:** a link post on the owner's LinkedIn profile through the admin's **Social posts** page (LinkedIn's
  official API, token valid to 2027-01-06). Never through linkedin.com in the browser (automation gets accounts
  banned), and never a LinkedIn article (the API has no article path). The owner decided this 2026-11-24.
- **Start:** https://fv.nerdit.in/social-posts
- **Signed in when:** Connections shows LinkedIn "Connected" with `urn:li:person:…` under it. The badges read
  "Not connected" for a few seconds while the page loads (2026-11-25 run failed on that): wait until Instagram
  shows "Connected", then read LinkedIn. Still "Not connected" after that, or token expired: `failed` with
  "LinkedIn not connected in the admin" and a report line for the owner.
- **Kit:** text = the article title, a blank line, the description, a blank line, "Read it here:" and the tracked
  link (article URL + `?utm_source=linkedin&utm_medium=share&utm_campaign=<slug>`); 3 hashtags from the tags.
- **Steps:**
  1. **New post** -> Name (admin only) = "Article: <title>"; **LinkedIn & Facebook text** = the kit text; Instagram
     caption = leave empty; Image = the article cover PNG; tick **Post my image as it is (no card text)**;
     Link = the tracked link -> **Create post**.
  2. On the new row untick every platform except **LinkedIn** (Instagram, Facebook, Pinterest, YouTube off).
- **Canonical / original URL:** Not needed (it is a link post).
- **Images:** the cover, as the post image (`runlog.py images --slug <slug>`: the first path printed is the cover).
- **Publish:** **Approve & post now**. The row then reads 'LinkedIn: posted'.
- **Post URL:** the row shows no link. Log `posted` with `--url "admin social post: Article: <title>"`; do not
  save anything on the Articles page (its LinkedIn row is for the Company Page post, which stays manual).
- **Verified:** no
