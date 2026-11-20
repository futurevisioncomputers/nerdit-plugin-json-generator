# YouTube Shorts from social packs: Studio kit now, API later

Date: 2026-11-20. Owner: "Add YouTube stories and shorts also in social post" (channel
https://www.youtube.com/@nerditSkillLearning); chose "C. B now, A later".

## Why and constraints

- More reach: every pack Reel also goes out as a YouTube Short.
- YouTube Stories were shut down on 26 June 2023; community Posts have no API. Out of scope.
- Uploads through the YouTube Data API from a project that has not passed YouTube's compliance
  audit stay Private. The audit takes weeks, so automatic upload (A) comes later.
- Our Reels (1080x1920, at most 90 s) already qualify as Shorts.

## Approaches

- A. API upload now (private until audit, owner flips each to public).
- B. Studio kit: the plugin writes the Short files plus ready titles, descriptions and the
  schedule; the owner bulk-uploads and schedules in YouTube Studio (about 10 minutes a pack).
- C. B now, A after the audit (chosen).

## Design (B)

- Each Reel item in `pack-plan.json` gets `captions.youtube`: the title on the first line, a blank
  line, then the description with `{link}` (filled with `utm_source=youtube`). YouTube is not added
  to the item's `platforms`, so `pack.json` and the server are unchanged.
- Rules, enforced by `captions.caption_errors("youtube", ...)`: title 1-100 characters, no link, no
  Devanagari; no `<` or `>` anywhere (YouTube rejects them); at most 5000 characters; at most 15
  hashtags; the course link with `utm_source=youtube`; every number from the lesson (same rule as
  the other platforms).
- `python build_pack.py shorts <packdir> [--start YYYY-MM-DD]` writes `<packdir>/youtube/`:
  a copy of each Reel named `dNN-<title-slug>.mp4`, and `SHORTS.md` with one block per Short
  (day, date and time IST, file, title, description with the filled link, tags from its
  hashtags) plus the settings to use once (audience: not made for kids; category: Education;
  playlist: the course title). The time is the Reel's time. `--start` is the Day 1 the admin
  showed after import (packs queue, so plan dates move); every date moves by the same days.
  It refuses, naming the problem, when a Reel has no YouTube caption, a caption breaks a rule,
  or a Reel file is missing (run build first).
- `build` writes the kit at the end when every Reel has a YouTube caption; otherwise it says how.
- The admin import already leaves sub-folders out, so `youtube/` is never uploaded to the server.

## Later (A)

Google Cloud project with the YouTube Data API v3, OAuth consent screen, the owner's one-time
sign-in, then the YouTube API Services audit form. After approval: `youtube` becomes a platform
for reels on the server, uploading the same file at the scheduled time.

## My calls

Kit time = the Reel's time (19:00 IST). Tags = the description's hashtags. Files are copied, not
moved, so the pack folder still imports as before.
