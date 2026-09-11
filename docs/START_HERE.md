# START HERE — documentation index

Documentation for the Gappler multimodal manipulation system: Aria glasses → voice + gaze → SAM 3
segmentation → AnyGrasp → RealMan RM65 arm on a LiDAR-navigating mobile base.

> ⚠️ **The root `README.md` is stale** — it describes a different upstream project. Ignore it.
> ⚠️ **Code in this repo moves a real robot arm within seconds of launch, unprompted.** Read
> [`ORIENTATION.md`](ORIENTATION.md) §8.1 before running anything on hardware.

## The six documents

| File | What it is | When to read it |
|---|---|---|
| **[`ORIENTATION.md`](ORIENTATION.md)** | **What the system *is*.** Repo map, ROS 2 primer, the full topic reference, the five severed seams, known defects and traps, hardware facts, the HiCo-Nav integration surface. | **First.** The main reference. Stays stable. |
| **[`ARCHITECTURE.md`](ARCHITECTURE.md)** | The same information as **diagrams** — 9 Mermaid diagrams, L0 system down to L2 module level. Renders on GitHub. | Alongside ORIENTATION. Prose there, pictures here. |
| **[`READING_GUIDE.md`](READING_GUIDE.md)** | A **guided walk through the code**, round by round, for someone new to ROS 2. What to notice in each file and why. Has check-yourself questions. | When you actually sit down to read the code. |
| **[`NEXT_STEPS.md`](NEXT_STEPS.md)** | **What we intend to *do*** — prioritised work register with the open decisions. | Planning. Churns; expect it to change. |
| **[`CODE_AUDIT.md`](CODE_AUDIT.md)** | A **line-by-line read of every file we own**, publisher to subscriber. 45 findings, all `[unverified]` — static analysis only, nothing was run. Starts with the three interlocking defects that stop the grasp path working. | Before touching the grasp path, and before the first hardware run. |
| **[`TESTBENCH_PLAN.md`](TESTBENCH_PLAN.md)** | **The cold-start handoff for building the test bench.** State at handoff, safety rules for the lab machine, known bench bugs, and a phased plan from "establish which machine this is" through build, node-behaviour and replay tiers. | **When you pick up bench work.** Read §0–§3 before touching the lab machine. |
| [`ASSETS.md`](ASSETS.md) | The files git doesn't hold — model weights and the `.venv` — with sizes, checksums, sources and why each is ignored. | Before copying or re-downloading a model file, or setting up a new machine. |

Plus **[`../bench/`](../bench/README.md)** — the offline regression bench. `./bench/run.sh` checks,
in order: whether this machine can run the stack at all (GPU, RAM, ROS, weights, and whether the arm
and LiDAR answer), whether the code is internally consistent, and whether a refactor moved any
topic / frame / parameter contract. Stdlib-only, ~1 s, no ROS or hardware needed — and every run
ends with an explicit list of what it could **not** check and why. Run it before and after any
refactor. See [`bench/README.md`](../bench/README.md).

Plus [`wiring-map.html`](wiring-map.html) — the interactive version of ARCHITECTURE (clickable
drill-down, searchable topic table). Publish it as an Artifact to get a shareable link; the source
lives here so it travels with the repo and anyone can republish under their own account.

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
`[inferred]`, promote it and say how. If something here is wrong, delete it — a confidently wrong
doc is worse than none.

## Where work stands (2026-09-10)

- **Reading:** Round 1 done. **Round 2 written but not yet read** — resume at `READING_GUIDE.md` §2.
- **Blocking decision, now sharpened:** the paper has been read (`hico-nav/PAPER_REPORT.md`).
  The RGB-D requirement is **confirmed and load-bearing** — a base-mounted RealSense D455 should be
  raised for purchase now, since nothing else has a lead time measured in weeks. HiCo-Nav emits
  **velocities**, but the recommendation is to take only the goal-level layer above that.
- **Not yet run:** no hardware bring-up has happened from this branch. `Navigation_Module` has
  never been built, and depends on a package that is not in this repo (`NEXT_STEPS.md` §3.1).
