# START HERE - Zongzhe's folder

This folder holds Zongzhe's work on Gappler: plans, session notes, handoffs, investigation
write-ups and bench-run reports. It is one of the per-person folders described in
[`../START_HERE.md`](../START_HERE.md).

**If you are new to the project, do not start here.** Start at
[`../START_HERE.md`](../START_HERE.md) for the reading order, then
[`../ORIENTATION.md`](../ORIENTATION.md) for what the system actually is.
Those are the shared reference. This folder does not repeat them, it links to them.

## What is in here

| File | What it is | When to read it |
|---|---|---|
| [`T0.3_SESSION.md`](T0.3_SESSION.md) | The 2026-09-15 session that made the repository run from a fresh clone. What changed, what the evidence is, what was deliberately left, and five items for Dion. | Before T0.4 or T0.5, and before trusting `../NEXT_STEPS.md` section 2.5, which this supersedes. |
| [`BUILD_WORKSPACES.md`](BUILD_WORKSPACES.md) | Why `deps_ws` and `ros2_robot_ws` are built separately instead of together, answered by Puneet on 2026-08-25, checked against the code. Explains the underlay and overlay idea for anyone who has not used colcon. | Before your first build, and before changing anything about how the project is built. |

## Rules this folder follows

From [`../START_HERE.md`](../START_HERE.md) and the root `CLAUDE.md`:

1. **Write here, not in someone else's folder.** If something in `../` is wrong or
   incomplete, the correction is written here, citing the file and section, and the owner is told.
   `BUILD_WORKSPACES.md` has a "For Dion" section that exists for exactly that reason.
2. **Tag where a claim came from.** `[code]` means it was read from the source at the cited line.
   `[reported]` means a person said it, and the doc names who and when. `[inferred]` means it is
   reasoning rather than fact. `[unverified]` means a static finding nobody has confirmed at the
   machine yet. If you verify something, retag it and say how. If it turns out wrong, delete it.
3. **Cite `file.py:123`** for anything specific. Line numbers drift. If one is wrong, fix it rather
   than deleting the claim.
4. **Every document keeps a changelog** at the bottom, appended to on any substantive edit.
5. **Plain language.** Readers include people who are new to code. Main point first, jargon
   explained the first time it appears.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-15 | Claude (Opus 5) + Zongzhe | Folder created. Added `BUILD_WORKSPACES.md`. |
| 2026-09-15 | Claude (Opus 5) + Zongzhe | Added `T0.3_SESSION.md`. |
