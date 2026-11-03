---
name: ship
description: Ship one Gappler task. Reviews the changes (a senior lead engineer review plus a background ponytail bloat review) and stops on major findings, checks the task's full scope, updates the task tree and docs in the branch, runs the quick bench, commits, merges the latest dev in, opens or updates the PR into dev, republishes the edited pages, watches CI until green, and merges once the user says yes. Nothing is left for after the merge. Use when someone types /ship, or says "ship it", "open the PR", "commit and PR this", or "get this merged". Run it per task, whenever a task is ready. It does not write the session handoff (Dion's /cold-start does that). Flags in the arguments: "no merge" stops at green CI, "no pony" skips the ponytail review, "no pub" skips republishing HTML pages. Flags chain.
model: claude-sonnet-5-5
effort: medium
---

# Ship a task

Takes the work on the current branch from "done locally" to "merged into `dev`". It follows the
git rules in `CLAUDE.md`. Stop and ask whenever a step below says so, or when something is unclear.

**Everything the task changes goes in before the merge**: code, task tree, global docs and the
republished pages. After the merge there is nothing left to do but switch branches. A doc fix found
after a merge means a second PR, which is what this rule exists to avoid.

`$ARGUMENTS` may name the task ID and carry flags. Flags chain in any order (`/ship no pony no pub`),
and the spelling is loose: dashes, spaces and "skip" for "no" all count.

- **no merge**: stop once CI is green.
- **no pony** (also `no ponytail`, `skip pony`, `skip-pony`, `no-pony`): skip the ponytail review
  in step 3. The lead review still runs.
- **no pub** (also `no publish`, `skip pub`, `skip-pub`, `no-pub`): do not republish HTML pages in
  step 8. Write "republish owed" in each edited page's changelog instead.

**Model and effort.** Run this skill, and every background agent it starts, on Sonnet 5.5 at
medium effort (`model: "sonnet"`, `effort: "medium"` on each Agent call). A fork ignores the model
setting, so background work uses a fresh `general-purpose` agent with a self-contained brief.

## 1. Check where you are

- `git fetch origin`, then `git branch --show-current`. The branch must start with a task ID
  (`t1.8-...`). If you are on `dev` or `main`, stop: make a branch first (`git switch -c t<id>-<short-name>`).
- Find the task in the `T` array of `docs/task-tree.html`. If no task covers the work, stop and add
  one with the user first.
- Read the task's whole row: description and notes (9th field). Another open branch may hold a
  newer copy of it, and so may the live page. Check with
  `for b in $(git branch -r --format='%(refname:short)'); do git show $b:docs/task-tree.html | grep -F '["<ID>"'; done`.
  Use the newest text as the task's scope. List every item it names: step 4 checks each one.
- If `gh pr list --head <branch> --state merged` shows the branch already merged, stop and say so.

## 2. Choose what goes in

- Show `git status` and `git diff --stat`.
- List the files you plan to commit and ask the user to confirm. Add files by name. Never use
  `git add -A` or `git add .`: personal notes, logs and recordings often sit untracked in the tree.
- Leave out files in other people's `docs/<name>_docs/` folders.

## 3. Review the changes

Two reviews of the files chosen in step 2. The diff is `git diff $(git merge-base HEAD origin/dev)`
(committed and uncommitted work on the branch) plus any new files being added.

Skip both reviews, say why in one line, and go on to step 4 when the change is minimal:

- only docs, comments or prose changed, or
- a small code change (roughly under 20 lines) with no new logic: a rename, a typo, a log
  message, a constant.

Always review a change that touches arm, gripper or base motion, safety checks, or ROS topics,
however small.

**Ponytail review (background).** Skip it on "no pony". Start it first so it runs while you do the
lead review. Use the Agent tool with `subagent_type: "general-purpose"`, `model: "sonnet"`,
`effort: "medium"`, `run_in_background` and this brief, filled in (it starts cold, so include the
repo path):

> Ponytail review of branch <branch> against `origin/dev`, files: <file list>. Review it the way
> the `ponytail:ponytail-review` skill does: reinvented stdlib, speculative abstractions, dead
> flexibility, duplicated helpers, needless comments or boilerplate. Only look at changed lines.
> Report only. Do not edit, stage, commit or push, and do not touch the lab box. One line per
> finding: file:line, what to cut, what replaces it. Mark each finding major or minor. Major means
> bloat that should not merge as is.

**Lead engineer review (you, inline).** Act as a senior lead engineer with long experience in
robotics, computer vision and complex systems. Read the whole diff and check:

- Correctness: logic, edge cases, units and frames (metres vs mm, which TF frame), timing and
  threading, error handling at hardware and network boundaries, anything that could move the arm or
  base unexpectedly.
- Viability: will this work on the real robot and the lab box, not just in the bench? Hardcoded
  paths, missing config, assumptions about sensors or timing.
- Structure: does the code sit in the right node or folder (one-folder-per-node), follow the
  naming rules (ORIENTATION §0b), and keep ROS topics and contracts consistent
  (`docs/CHANNEL_CONTRACT.md`)?
- Principles: YAGNI, KISS, DRY, single responsibility, clear names, no dead code, no premature
  abstraction, tests or a bench check for non-trivial logic.

Write each finding as one line: file:line, the problem, the fix, and major or minor. Major means a
bug, a safety risk, or a design problem that should not merge.

**Gate.** Before step 5 (commit), wait for the ponytail result (if it ran), then show the user the reviews.
If neither has a major finding, say so in one line and continue. If either has one, stop and ask
the user whether to fix it now or ship anyway. Minor findings go in the PR body under "Review
notes".

## 4. Update the docs that this task changes, in this branch

These edits are part of this PR's commit. Never leave one for after the merge.

- **Scope check first.** Go through every item listed in step 1. Each one is either done in this
  branch, or written into the task as still open (or moved to a named task). If an item was missed,
  do it now or tell the user before going on.
- Task tree: if every item is done, start the description with `"DONE <date>. ..."` plus one line
  of evidence (bench run, box run, log file). If not, update its progress note and do not mark it
  DONE. If another open branch holds an older copy of the row, say so in the PR body, so whoever
  merges keeps one row.
- Any global doc the work made wrong (see `CLAUDE.md` "Keep the global docs current"), with a
  changelog row.
- The edits where you already know the exact text (a `DONE` prefix, a changelog row) can go to a
  background agent (`general-purpose`, `model: "sonnet"`, `effort: "medium"`) with the file paths
  and exact text. Wait for it before step 5. Judgment edits stay inline.

## 5. Check, then commit

- Run `./bench/run.sh quick`. Report the result as printed. Skipped is skipped, not passed. If it
  fails, fix it or stop and show the user.
- Commit with a message that starts with the task ID: `T1.8: <what changed, in plain words>`.
  Add a body only if the why isn't obvious.

## 6. Bring in the latest dev

- `git merge origin/dev`. Never rebase a pushed branch, and never force-push.
- If there are conflicts, resolve them and explain each one to the user in a line.
  `docs/task-tree.html` conflicts are usually two people editing different rows: keep both.
- If the merge brought in changes, rerun `./bench/run.sh quick`.

## 7. Push and open the PR

- `git push -u origin <branch>`.
- If no PR exists: `gh pr create --base dev --title "T1.8: <summary>"`. The body says what changed,
  why, how it was checked (bench result, robot step, log path), and what is still open.
- If a PR exists, the push updates it. Edit its description if what it claims has changed.

## 8. Republish the pages this PR edits, before the merge

Skip on "no pub" (step 4 wrote "republish owed").

- For each HTML page the branch changed (`git diff --name-only origin/dev... -- '*.html'`), publish
  the branch's file with the `Artifact` tool to the page's existing URL (the tool's `list` action
  finds it by title). Read the live version first (the tool requires it). The branch already has the latest `dev` (step 6), so the live page then
  shows `dev` plus this PR.
- If the live page holds notes this branch does not (another open branch published its file
  before merging), do not overwrite them. Find the commit the live page came from (compare the live
  copy with `git show <commit>:<page>` on the open branches), then publish a three-way merge:
  `git merge-file -p <live copy> <merge-base copy> <branch copy>`. On a conflict keep both sides.
  If both copies hold the same task row, keep this branch's row. Build it in the scratchpad, never
  commit it, and tell the user in one line which branch's notes it kept.
- If publishing fails, add "republish owed" to that page's changelog, commit and push it now, before
  the merge.

## 9. Wait for CI

- `gh pr checks <pr> --watch`.
- If a check fails, read the log (`gh run view <run-id> --log-failed`), fix it, commit with the task
  ID, push, and watch again. After two failed fixes, stop and show the user. If a fix changes an
  HTML page, republish it again (step 8).
- Don't start the full lab-box CI job (the "Run workflow" button or `gh workflow run`) unless the
  user asks. It holds the box for about 30 minutes, and only one bench run can use the box at a time.

## 10. Merge, only on a yes

- Stop here if `$ARGUMENTS` says "no merge".
- Show the PR link and CI result, then ask: "Merge PR #N into dev?" Merge only on an explicit yes:
  `gh pr merge <pr> --merge --delete-branch`.
- Never merge into someone else's branch, and never merge a PR that someone else opened unless they
  asked you to.

## 11. After the merge

- `git switch dev && git pull`, or, in a worktree, ask before removing it.
- No doc or page work happens here: steps 4 and 8 did it. If something turns up anyway, tell the
  user, and put it in the next PR for that task rather than a docs-only PR.
- Don't pull on the lab box (`~/rcp-Gappler`) unless the user asks: someone may be in the middle
  of a robot session there.
- Report in a few lines: PR link, merged or waiting, bench result, docs updated, anything left open
  with its task ID.
