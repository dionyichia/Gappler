# START HERE — Dion's folder

This folder holds Dion's personal work on Gappler: session notes, investigation write-ups and
handoffs that haven't been folded into the shared docs yet. It is one of the per-person folders
described in [`../START_HERE.md`](../START_HERE.md).

**If you are new to the project, do not start here.** Start at [`../START_HERE.md`](../START_HERE.md)
for the reading order, then [`../ORIENTATION.md`](../ORIENTATION.md) for what the system actually is.
Those live directly in `docs/` now — they are global, not personal to anyone.

## Why this folder is nearly empty

Until 2026-09-16, `docs/dion_docs/` held both Dion's own notes and the shared reference everyone
read (`ORIENTATION`, `PROJECT_PLAN`, `NEXT_STEPS`, the published HTML pages, and so on). That made
"is this global or personal" a judgement call, and it meant only Dion's sessions reliably kept the
task tracker current. Those files all moved to `docs/` directly — see
[`../START_HERE.md`](../START_HERE.md) changelog for the full list. This folder now follows the same
shape as [`../sherman_docs/`](../sherman_docs/) and [`../zongzhe_docs/`](../zongzhe_docs/): a place
for session notes and evidence that isn't yet ready to fold into the shared docs, not a second copy
of them.

## Shared source of truth

The following documents, now directly in `docs/`, are authoritative for team task status,
priorities, schedules, and system contracts. Update them directly when your work changes what they
say — see `docs/START_HERE.md` rule 4 and the root `CLAUDE.md`.

- [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) — task tree, dependencies, owners, and milestone dates.
- [`../NEXT_STEPS.md`](../NEXT_STEPS.md) — open work register and decisions.
- [`../ORIENTATION.md`](../ORIENTATION.md) — system facts, network contract, and safety constraints.
- [`../TESTBENCH_PLAN.md`](../TESTBENCH_PLAN.md) — lab test evidence and safe bench procedures.
- [`../next-steps-map.html`](../next-steps-map.html) — the interactive task tracker. Keep its task
  data in step with `NEXT_STEPS.md` / `PROJECT_PLAN.md` and republish it when they change.

## Recording work

1. Create or extend one focused record per task or investigation, named `T<id>_TOPIC.md`, or use
   `WORK_LOG.md` for a running index — same pattern as `sherman_docs/`.
2. Cite the relevant shared-plan task and retain raw command output when it is important evidence.
3. When a finding is confirmed and ready to be load-bearing for the team, fold it into the relevant
   shared doc directly (with its citation/tag/changelog conventions) rather than leaving it here
   indefinitely — this folder is a staging area, not the record of truth.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-16 | Claude (Sonnet 5) + Dion | Folder repurposed as Dion's personal folder, matching `sherman_docs/` and `zongzhe_docs/`, as part of moving all global docs out to `docs/` directly. |
