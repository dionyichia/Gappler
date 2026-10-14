---
name: ship
description: Ship one Gappler task. Updates the task tree, runs the quick bench, commits, merges the latest dev in, opens or updates the PR into dev, watches CI until green, and merges once the user says yes. Use when someone types /ship, or says "ship it", "open the PR", "commit and PR this", or "get this merged". Run it per task, whenever a task is ready. It does not write the session handoff (Dion's /cold-start does that).
---

# Ship a task

Takes the work on the current branch from "done locally" to "merged into `dev`". It follows the
git rules in `CLAUDE.md`. Stop and ask whenever a step below says so, or when something is unclear.

`$ARGUMENTS` may name the task ID or say "no merge" (stop once CI is green).

## 1. Check where you are

- `git fetch origin`, then `git branch --show-current`. The branch must start with a task ID
  (`t1.8-...`). If you are on `dev` or `main`, stop: make a branch first (`git switch -c t<id>-<short-name>`).
- Find the task in the `T` array of `docs/task-tree.html`. If no task covers the work, stop and add
  one with the user first.
- If `gh pr list --head <branch> --state merged` shows the branch already merged, stop and say so.

## 2. Choose what goes in

- Show `git status` and `git diff --stat`.
- List the files you plan to commit and ask the user to confirm. Add files by name. Never use
  `git add -A` or `git add .`: personal notes, logs and recordings often sit untracked in the tree.
- Leave out files in other people's `docs/<name>_docs/` folders.

## 3. Update the docs that this task changes

- Task tree: if the task is finished, start its description with `"DONE <date>. ..."` plus one line
  of evidence (bench run, PR, log file). If it is not finished, update its progress note.
- Any global doc the work made wrong (see `CLAUDE.md` "Keep the global docs current"), with a
  changelog row.
- If you edited an HTML page and have the `Artifact` tool, republish it after the merge. If not, add
  "republish owed" to its changelog.

## 4. Check, then commit

- Run `./bench/run.sh quick`. Report the result as printed. Skipped is skipped, not passed. If it
  fails, fix it or stop and show the user.
- Commit with a message that starts with the task ID: `T1.8: <what changed, in plain words>`.
  Add a body only if the why isn't obvious.

## 5. Bring in the latest dev

- `git merge origin/dev`. Never rebase a pushed branch, and never force-push.
- If there are conflicts, resolve them and explain each one to the user in a line.
  `docs/task-tree.html` conflicts are usually two people editing different rows: keep both.
- If the merge brought in changes, rerun `./bench/run.sh quick`.

## 6. Push and open the PR

- `git push -u origin <branch>`.
- If no PR exists: `gh pr create --base dev --title "T1.8: <summary>"`. The body says what changed,
  why, how it was checked (bench result, robot step, log path), and what is still open.
- If a PR exists, the push updates it. Edit its description if what it claims has changed.

## 7. Wait for CI

- `gh pr checks <pr> --watch`.
- If a check fails, read the log (`gh run view <run-id> --log-failed`), fix it, commit with the task
  ID, push, and watch again. After two failed fixes, stop and show the user.
- Don't start the full lab-box CI job (the "Run workflow" button or `gh workflow run`) unless the
  user asks. It holds the box for about 30 minutes, and only one bench run can use the box at a time.

## 8. Merge, only on a yes

- Stop here if `$ARGUMENTS` says "no merge".
- Show the PR link and CI result, then ask: "Merge PR #N into dev?" Merge only on an explicit yes:
  `gh pr merge <pr> --merge --delete-branch`.
- Never merge into someone else's branch, and never merge a PR that someone else opened unless they
  asked you to.

## 9. After the merge

- `git switch dev && git pull`, or, in a worktree, ask before removing it.
- Republish any HTML page you edited (step 3).
- Don't pull on the lab box (`~/rcp-Gappler`) unless the user asks: someone may be in the middle
  of a robot session there.
- Report in a few lines: PR link, merged or waiting, bench result, docs updated, anything left open
  with its task ID.
