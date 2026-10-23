Paste this into your Claude Code session in your Gappler checkout. Replace <NAME> with your first
name (sherman or zongzhe).

---

I need a progress report of everything I have done on Gappler, from when I joined to today, for our
team progress presentation. Dion, Sherman and Zongzhe each write one. We will merge the three and cut
them down later, so make this a detailed information dump: too much detail is better than too little.
Do not worry about slide layout.

Where to look: read CLAUDE.md, docs/START_HERE.md and docs/ORIENTATION.md first. Then go through
everything of mine: my rows in the T array of docs/task-tree.html (that is the main source), my run
records in docs/bench-runs/, my folder docs/<NAME>_docs/ including local/, my git branches and
worktrees (`git worktree list`, `git log --author`), my merged and open PRs (`gh pr list --state all`),
and the lab box (read only: `ssh -o HostKeyAlias=10.91.242.76 rcp2026@100.87.133.60`, look for my
logs, bags, pictures and videos, change nothing, start nothing). Ask me when something is unclear.

Write the report to `docs/<NAME>_docs/<NAME_UPPER>_PROGRESS_REPORT_2026-10.md`. Use the same
structure as Dion's (`docs/dion_docs/DION_PROGRESS_REPORT_2026-10.md`, read it for the shape), so the
three merge easily:

0. Summary table: stage, where it stands today, one headline number each.
1. Context: how my part fits the project. The project integrates two papers, FAM-HRI (gaze and
   speech pick the object, Aria glasses, which the original authors of this repo were recreating)
   and HiCo-Nav (language navigation with a memory graph). Name the open-source parts I built on and
   what I added to each. Our framing: we build something new from open-source systems, not tune one
   old workflow.
2. What existed when I started, and what I changed.
3. onwards: one section per stage of my work, in the order it runs in the system. For each: what it
   does, step by step. A results table with numbers. Problems found and how they were fixed. What is
   still open, with task IDs.
   - Sherman: navigation to the user, mapping and localisation (FAST-LIVO2, SLAM Toolbox), the base,
     the video you collected and its outputs, calibration rigs.
   - Zongzhe: the memory graph built from that run, how a prompt like "find the box" queries it, and
     what it returns.
4. Challenges.
5. Next steps, in order, with task IDs.
6. Visualisation options for my section, ranked by impact for the effort (one judge is a
   visualisation professor), saying which data already exists and how much work each needs.
7. A media inventory table.
8. Open questions for me.

Rules for the content:
- Every number comes from a run record, a task row or a log. Cite the task ID or file. Tag claims
  `[measured]`, `[code]`, `[inferred]` or `[unverified]`. Never invent a result. A skipped check is
  reported as skipped.
- Write plainly: main point first, short sentences, plain words before jargon. No em dashes, no
  semicolons, no emojis, no hype. Readers include mechanical engineering students new to code.

Pictures and videos:
- Put every picture, GIF and video the report uses in `docs/<NAME>_docs/local/report_media/`.
  This folder is gitignored and must stay local. Never commit it. Copy files there (do not move
  originals), with descriptive names that include the date, for example
  `nav_lidar_map_lab_2026-10-21.png`.
- Embed pictures in the report with relative paths (`local/report_media/<file>`) and a one-line
  caption saying what it shows and which task it came from.
- Pull useful media from the lab box with scp into that folder. Read only on the box.
- For a video I have but is not on the machine, or one still to record, add a row marked
  **VIDEO STUB** with the planned file name and what it should show.

Do not commit, push or stage anything. Do not edit anyone else's docs folder. Do not start anything
on the lab box. When done, give me the report path, the media folder path, and your open questions.
