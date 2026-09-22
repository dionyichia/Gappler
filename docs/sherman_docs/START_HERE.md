# START HERE - Sherman's folder

This folder holds Sherman's work on Gappler: session evidence, handoffs, investigation notes,
and bench-run reports. It is one of the per-person folders described in
[`../START_HERE.md`](../START_HERE.md).

**If you are new to the project, do not start here.** Start at
[`../START_HERE.md`](../START_HERE.md) for the reading order, then
[`../ORIENTATION.md`](../ORIENTATION.md) for what the system actually is.
Those are the shared reference. This folder does not repeat them, it links to them.

## Shared source of truth

The following Dion-owned documents are authoritative for team task status, priorities, schedules,
and system contracts:

- [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) — task tree, dependencies, owners,
  and milestone dates.
- [`../NEXT_STEPS.md`](../NEXT_STEPS.md) — open work register and decisions.
- [`../ORIENTATION.md`](../ORIENTATION.md) — system facts, network contract,
  and safety constraints.
- [`../TESTBENCH_PLAN.md`](../TESTBENCH_PLAN.md) — lab test evidence and safe
  bench procedures.

This folder records what Sherman observed or did. It does not independently declare a team task
complete. Link a record to the relevant shared task, then ask its owner to incorporate accepted
evidence into the shared documents.

## What is in here

| File | What it is | When to read it |
|---|---|---|
| [`WORK_LOG.md`](WORK_LOG.md) | Chronological index of Sherman's sessions, outcomes, and next actions | At the start or end of every session |
| [`T0.2_SESSION.md`](T0.2_SESSION.md) | Evidence for the T0.2 network-switch proof | When reviewing M0 network evidence |
| [`T0.9_BASE_FOOTPRINT.md`](T0.9_BASE_FOOTPRINT.md) | Reported base identity and pending footprint-measurement record | Before measuring or changing the navigation footprint |
| [`T0.1_D455_VALIDATION.md`](T0.1_D455_VALIDATION.md) | D455 USB 3 link and ROS-driver stream evidence | When reviewing M0 camera acceptance |
| [`T1.2_SAFETY_FIXES.md`](T1.2_SAFETY_FIXES.md) | B1 launcher wording + I1 double-launch deletion evidence | When reviewing M1 pre-power safety |
| [`T1.3_HOME_POSE.md`](T1.3_HOME_POSE.md) | Final T1.3 sim verdicts; original row retained; replacement pose still owed | When reviewing the arm home pose |
| [`T1.4_PHYSICAL_SETUP.md`](T1.4_PHYSICAL_SETUP.md) | T1.4 robot-side measurement plan; exact A–F sheet; cell half blocked | Before the physical safety visit |
| [`T5.2_D455_MOUNT.md`](T5.2_D455_MOUNT.md) | Reported D455 mount design and remaining fabrication evidence | Before fabricating the camera mount |

## Recording work

1. Create or extend one focused record per task or investigation, named `T<id>_TOPIC.md`.
2. Append a short entry to `WORK_LOG.md` with the date, record link, verified outcome, and next
   action.
3. Cite the relevant shared-plan task and retain raw command output when it is important evidence.
4. Do not duplicate or edit Dion's task status. Send the evidence link to the shared-doc owner.

## Rules this folder follows

From [`../START_HERE.md`](../START_HERE.md) and the root `CLAUDE.md`:

1. **Write here, not in someone else's folder.** If something in `../` is wrong or
   incomplete, the correction is written here, citing the file and section, and the owner is told.
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
| 2026-09-16 | OpenCode (GPT-5.6 Terra) + Sherman | Folder created. Added `T0.2_SESSION.md`. |
| 2026-09-16 | OpenCode (GPT-5.6 Terra) + Sherman | Added shared-source-of-truth rules and `WORK_LOG.md`. |
| 2026-09-16 | OpenCode (GPT-5.6 Terra) + Sherman | Added the T0.9 base-identification and footprint record. |
| 2026-09-22 | OpenCode (Muse Spark) + Sherman | Pointed T1.3 at the final verdict: original row retained, replacement pose still owed. |
| 2026-09-22 | OpenCode (Muse Spark) + Sherman | Added T1.4 measurement-plan pointer; robot-side sheet now, cell half blocked. |
