# START HERE — documentation index

Documentation for the Gappler multimodal manipulation system: Aria glasses → voice + gaze → SAM 3
segmentation → AnyGrasp → RealMan RM65 arm on a LiDAR-navigating mobile base.

> ⚠️ **The root `README.md` is stale** — it describes a different upstream project. Ignore it.
> ⚠️ **Code in this repo moves a real robot arm within seconds of launch, unprompted.** Read
> [`ORIENTATION.md`](ORIENTATION.md) §8.1 before running anything on hardware.

## How the docs are organised — read this first

**Reorganised 2026-09-16.** `docs/` (this folder, directly) now holds the **global, shared**
documentation: what the system is, the team plan, and the test evidence — everything that describes
state shared by all three of us, not one person's session. Per-person folders,
`docs/<name>_docs/`, hold personal plans, session notes, handoffs and evidence write-ups that
haven't been folded into the shared docs yet.

| Location | Scope | What's in it |
|---|---|---|
| **`docs/`** (this folder, directly) | **Global — shared by everyone** | What the system is (`ORIENTATION`, `ARCHITECTURE`, `READING_GUIDE`, `CODE_AUDIT`, `ASSETS`, `hico-nav/`), the team plan (`PROJECT_PLAN`, `NEXT_STEPS`), the bench handoff (`TESTBENCH_PLAN`, `bench-runs/`), and the three published HTML pages (`next-steps-map.html`, `wiring-map.html`, `testbench-map.html`). |
| `docs/<name>_docs/` | Personal to that contributor | Their own plans, session notes, handoffs and evidence records not yet folded into the shared docs above. |
| `docs/archive/` | Global, historical | Old documents kept as evidence, not as instructions. Today: the 2026-08-25 startup guide from `realman_manip`. |
| `bench/` | Shared | The regression bench — tooling, not docs. |
| root `README.md` | — | Stale (a different upstream project). Ignore it. |

**Before 2026-09-16** the global docs lived in `docs/dion_docs/` and the per-person convention had
an exception baked in for whoever happened to be maintaining them. That made `dion_docs/` do two
jobs at once and made "is this global or personal" a judgement call. It no longer is one: **global
docs live directly in `docs/`; personal docs live one level down, in `docs/<name>_docs/`.**
`docs/dion_docs/` is now Dion's personal folder, same shape as everyone else's — see its own
`START_HERE.md`.

### New here? Read in this order

1. **This file**, to the end.
2. **[`ORIENTATION.md`](ORIENTATION.md), in full** — what the system is, the topic graph, the traps.
   §8.1 before running anything.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) alongside it — the same thing as diagrams.
4. Then by task: [`READING_GUIDE.md`](READING_GUIDE.md) to walk the code ·
   [`CODE_AUDIT.md`](CODE_AUDIT.md) before touching the grasp path · [`ASSETS.md`](ASSETS.md) before
   setting up a machine · [`../bench/README.md`](../bench/README.md) before any refactor ·
   [`hico-nav/`](hico-nav/PAPER_REPORT.md) for the navigation paper.

`PROJECT_PLAN.md` is the **team** plan — milestones, task tree and owners for all three of us.
`NEXT_STEPS.md` and `TESTBENCH_PLAN.md` are the working registers behind it — open decisions, work
in flight, bench status. All of it is shared: read it to know what's happening, and update it
directly (see rule 4 below) rather than filing the update somewhere personal and waiting for someone
to notice.

### Rules for every session — human or AI

1. **Know whose session you are.** Your personal folder is `docs/<first name, lowercase>_docs/`
   (e.g. `docs/alex_docs/`). A Claude session that doesn't know its user's name asks —
   `git config user.name` is a hint, not an answer.
2. **Personal work goes in your own folder.** Session notes, handoffs, investigation write-ups and
   evidence records that aren't yet ready to fold into the shared docs → `docs/<name>_docs/`. Create
   it on first need, with its own short `START_HERE.md` saying what is in it and linking back here.
3. **Don't edit another person's `*_docs/` folder.** If something there is wrong or stale, write the
   correction in your own folder (cite file and section) and tell its owner.
4. **Global docs live directly in `docs/`, and everyone keeps them current.** `ORIENTATION`,
   `ARCHITECTURE`, `READING_GUIDE`, `CODE_AUDIT`, `ASSETS`, `NEXT_STEPS`, `PROJECT_PLAN`,
   `TESTBENCH_PLAN`, `hico-nav/`, `bench-runs/` and the three published HTML pages are shared state,
   not any one person's file. **If your session's work changes what one of them says — a task moves
   from open to done, a finding gets confirmed, a decision gets settled — update that doc in the same
   session, following its citation/tag/changelog conventions.** Don't leave shared docs to drift
   while the correction sits in a personal folder waiting for someone else to notice it. See
   `CLAUDE.md` for the specific rule about `next-steps-map.html` staying in sync with `NEXT_STEPS.md`
   / `PROJECT_PLAN.md`.
5. **Code, `bench/` and `CLAUDE.md` are shared.** Change them by commit; robot code goes on a branch
   for review. The safety rules in `CLAUDE.md` bind everyone.
6. **Keep the conventions:** provenance tags (below), `file.py:123` citations, a changelog on any
   doc you substantively edit, descriptive names (ORIENTATION §0b).

### Dion's sessions: where to resume

[`TESTBENCH_PLAN.md`](TESTBENCH_PLAN.md) → "▶ Start here" (work queue W1–W8).

## The documents in this folder

| File | What it is | When to read it |
|---|---|---|
| **[`ORIENTATION.md`](ORIENTATION.md)** | **What the system *is*.** Repo map, ROS 2 primer, the full topic reference, the five severed seams, known defects and traps, hardware facts, the HiCo-Nav integration surface. | **First.** The main reference. Stays stable. |
| **[`ARCHITECTURE.md`](ARCHITECTURE.md)** | The same information as **diagrams** — 9 Mermaid diagrams, L0 system down to L2 module level. Renders on GitHub. | Alongside ORIENTATION. Prose there, pictures here. |
| **[`READING_GUIDE.md`](READING_GUIDE.md)** | A **guided walk through the code**, round by round, for someone new to ROS 2. What to notice in each file and why. Has check-yourself questions. | When you actually sit down to read the code. |
| **[`PROJECT_PLAN.md`](PROJECT_PLAN.md)** | **The plan the team works to** — 11 milestones and 70 tasks over the 20 weeks from 2026-09-14, who owns each, what blocks what, what is in scope and what is not, and the cut list decided in advance. Answers whether three people can work in parallel (yes, from week 3, after two specific obstacles go). | **Before planning your own week.** Visual version: [`next-steps-map.html`](next-steps-map.html). |
| **[`NEXT_STEPS.md`](NEXT_STEPS.md)** | **What we intend to *do*** — prioritised work register with the open decisions. | Planning. Churns; expect it to change. |
| **[`CODE_AUDIT.md`](CODE_AUDIT.md)** | A **line-by-line read of every file we own**, publisher to subscriber. 45 findings, all `[unverified]` — static analysis only, nothing was run. Starts with the three interlocking defects that stop the grasp path working. | Before touching the grasp path, and before the first hardware run. |
| **[`TESTBENCH_PLAN.md`](TESTBENCH_PLAN.md)** | **The cold-start handoff for building the test bench.** State at handoff, safety rules for the lab machine, known bench bugs, and a phased plan from "establish which machine this is" through build, node-behaviour and replay tiers. | **When you pick up bench work.** Read §0–§3 before touching the lab machine. |
| [`ASSETS.md`](ASSETS.md) | The files git doesn't hold — model weights and the `.venv` — with sizes, checksums, sources and why each is ignored. | Before copying or re-downloading a model file, or setting up a new machine. |
| [`bench-runs/`](bench-runs/) | Raw results of every lab-box bench run, one file per run, with what each result means and what it does not show. | For the evidence behind any ✅ in TESTBENCH_PLAN. |

Plus **[`../bench/`](../bench/README.md)** — the offline regression bench. `./bench/run.sh` checks,
in order: whether this machine can run the stack at all (GPU, RAM, ROS, weights, and whether the arm
and LiDAR answer), whether the code is internally consistent, and whether a refactor moved any
topic / frame / parameter contract. Stdlib-only, ~1 s, no ROS or hardware needed — and every run
ends with an explicit list of what it could **not** check and why. Run it before and after any
refactor. On the lab box it also has Tier 2–3 scripts — the arm build, MoveIt and the grasp state
machine on a simulated arm, the e-stop, the AnyGrasp env. See [`bench/README.md`](../bench/README.md).

Plus [`next-steps-map.html`](next-steps-map.html), the visual version of the project plan: the
milestone schedule as a picture and a task tree you can click through to see who is waiting on whom.
Published at <https://claude.ai/code/artifact/65c7784d-1284-4ebd-a481-43951f8ce676>. **It needs no
Claude account to read** — it is one self-contained file, so open it straight off disk, or serve the
folder with `cd docs && python3 -m http.server 8000` and open
`http://localhost:8000/next-steps-map.html`.

Plus [`wiring-map.html`](wiring-map.html), the visual version of ORIENTATION in plain language. Its
second tab, **"One grasp, start to finish"**, follows one grasp from your voice to the gripper opening:
which program runs at each step, what method it uses, what it sends, and whether it works today. Start
there if the system is new to you. Published at
<https://claude.ai/code/artifact/837635d4-0107-4248-83cc-ce1d7536d0ea>. The test bench has its own page,
[`testbench-map.html`](testbench-map.html), published at
<https://claude.ai/code/artifact/cb1f53f5-3154-4271-be1e-4daf46fca7fe>. Sources live here so they travel
with the repo, and anyone can republish them under their own account.

## `hico-nav/` — everything about the paper we are integrating

| File | What it is |
|---|---|
| [`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) | Full review of the HiCo-Nav paper: what it does, its inputs and outputs, its design, and a first-pass assessment of what should be ported here. **Closes `NEXT_STEPS.md` §1.1 and §1.2** and narrows §1.3. Reconnaissance only — no integration plan. |
| [`hico-nav/hico-nav-map.html`](hico-nav/hico-nav-map.html) | The visual version of the same, in the style of `wiring-map.html`. Six diagrams. Read this first if you have not read the paper. |
| [`hico-nav/HiCo-Nav.pdf`](hico-nav/HiCo-Nav.pdf) | The paper itself. |

Anything HiCo-Nav-related belongs in that folder.

## If you are an AI assistant pointed at this repo

Read `ORIENTATION.md` in full before making changes — it will save you re-deriving the topic
graph. Two warnings above all others:

1. **§6 lists five places where the system is deliberately cut apart.** They are integration
   seams, not bugs. Do not "fix" them without reading §6 — and §6.5 in particular, where the
   obvious fix creates a topic collision.
2. **§8.1** — launching the wrong file moves real hardware, and a running orchestrator makes that
   *message-triggered* rather than human-triggered.

**Name things descriptively** — ORIENTATION §0b. Five subsystems here have a "base", a "camera"
and a "main" each; unqualified names cause real bugs (`base_link` is the arm, `robot_base_link` is
the wheelbase). This applies to prose too.

Honour the provenance tags: `[code]` verified by reading source · `[reported]` from the
2026-08-25 hardware session · `[inferred]` reasoning, not fact. If you verify something that was
`[inferred]`, promote it and say how. If you are Dion's session and something here is wrong, delete it — a
confidently wrong doc is worse than none. Anyone else: rule 3 above.

## Where work stands (2026-09-14)

- **The project plan now exists:** [`PROJECT_PLAN.md`](PROJECT_PLAN.md). 20 weeks from 2026-09-14,
  a checkpoint demonstration on 2026-12-06 and the finish on 2027-01-31. Milestone M0 (two weeks) is
  what lets Zongzhe and Sherman work in parallel: making the repo run from a fresh clone, and getting
  the arm and the LiDAR onto the network together.
- **Planning is mid-flight. Start at [`PROJECT_PLAN.md`](PROJECT_PLAN.md) §1.1, "Open decisions".**
  Seven decisions are live and unsettled, covering who owns which stream, whether the hour estimates
  survive the code evidence, and whether the milestone Lead column stays. Nothing below §1.1 should be
  treated as settled until those are answered.
- **Four code checks were run on 2026-09-14 and are recorded in `PROJECT_PLAN.md` §2.5.** The headline
  is that this project is mostly not a build. Of 70 tasks, 18 are new code, 9 are repair or rewiring,
  and 43 are bring-up, measurement and decisions. Every task now carries that type in section 6 and on
  the map. Navigation is retrieval rather than development, the glasses gaze and image code is complete
  and merely switched off, and the memory graph is the one genuinely new component.
- **One new defect came out of those checks:** `CODE_AUDIT` E5. Two nodes react to the same spoken
  word and compete for the same Nav2 action server, and the node at fault launches unconditionally in
  normal operation. It also means E1 cannot be dropped as return-leg-only.


- **Test bench, Dion's current work:** [`TESTBENCH_PLAN.md`](TESTBENCH_PLAN.md) → "▶ Start here". Tiers 0–3
  run on the lab box (reach it over tailscale). The tests have found real bugs: the e-stop ignores
  Ctrl+C (CODE_AUDIT B2a), and the grasp state machine handles one object per launch (C7). AnyGrasp runs
  in the project's single uv env, no conda needed.
- **The lab box has been off since the evening of 2026-09-11.** Written on the Mac and waiting to run:
  the navigation build prep (`./bench/build.sh nav`), 10 navigation node tests (`./bench/nav_nodes.sh`)
  and a fix to the glasses check, which passed with the glasses unplugged. **Next: get the box back on,
  then run those three.**
- **Pages:** the wiring map and the test bench page are rewritten in plain language for readers new to
  code (links above). Dion's docs follow the same rule.
- **Standing rule: fixes go on branches for review.** Since 2026-09-19 the project is in
  implementation. Each fix lands through a PR into `main`, where CI runs the bench.
- **Things the robot needs that live outside git** — `robot_navigation`, `xpkg_demo`, the SLAM map and
  more: [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.9. The lab box now has a copy of `iot22`'s navigation
  workspace at `~/rcp-old-ros-wkspace`.
- **Hardware:** nothing has moved. Arm, base and glasses are unplugged from the box.
- **Reading:** Round 1 done. **Round 2 written but not yet read** — resume at `READING_GUIDE.md` §2.
- **HiCo-Nav:** the paper has been read (`hico-nav/PAPER_REPORT.md`). The RGB-D requirement is
  **confirmed and load-bearing** — a base-mounted RealSense D455 should be raised for purchase now,
  since nothing else has a lead time measured in weeks. HiCo-Nav emits **velocities**, but the
  recommendation is to take only the goal-level layer above that.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-11 | Claude (Opus 5) + Dion | This folder renamed `docs/dion_docs/` as more contributors join (moved under `docs/` the same evening). Added "How the docs are organised": the per-person `docs/<name>_docs/` convention, reading order, rules for every session. |
| 2026-09-11 | Claude (Opus 5) + Dion | Folder moved to `docs/`; per-person folders now live under `docs/`. "Where work stands" refreshed for a cold start; `bench-runs/` added to the table. |
| 2026-09-12 | Claude (Opus 5) + Dion | "Where work stands" refreshed: box off, three things waiting to run. `wiring-map.html` entry updated for the new tab and both page links. |
| 2026-09-13 | Claude (Opus 5) + Dion | Added `PROJECT_PLAN.md` and `next-steps-map.html`: the team plan, its milestones, the task tree and the assignment across Dion, Zongzhe and Sherman. |
| 2026-09-13 | Claude (Opus 5) + Dion | Republished the task tree map under Dion's own account, so its link is `.../65c7784d-...` and the old `.../72753a73-...` one is dead. The page content did not change. |
| 2026-09-14 | Claude (Opus 5) + Dion | "Where work stands" refreshed for a cold start: pointer to the seven open decisions in `PROJECT_PLAN` §1.1, the four code checks in §2.5, the work-type split across the 67 tasks, and the new `CODE_AUDIT` E5. |
| 2026-09-16 | Claude (Sonnet 5) + Dion | Global-docs reorg: moved everything global out of `docs/dion_docs/` into `docs/` directly (`ORIENTATION`, `ARCHITECTURE`, `READING_GUIDE`, `CODE_AUDIT`, `ASSETS`, `NEXT_STEPS`, `PROJECT_PLAN`, `TESTBENCH_PLAN`, `hico-nav/`, `bench-runs/`, and the three published HTML pages, `testbench-map.html` also moving out of `bench/`). `docs/dion_docs/` is now Dion's personal folder, matching everyone else's. Rewrote "How the docs are organised" and the rules for every session — global docs are now everyone's to keep current, not just Dion's. |
| 2026-09-19 | Claude (Opus 5) + Dion | Added `docs/archive/` to the layout table. It holds the 2026-08-25 startup guide, moved from the `realman_manip` branch in T0.0. |
| 2026-09-19 | Claude (Opus 5) + Dion | Task count 69 to 70 after `T0.11` was added to `PROJECT_PLAN`. |
| 2026-09-19 | Claude (Opus 5) + Dion | Replaced the "no fixes yet" rule. Fixes now go on branches, through a PR into `main`. |
