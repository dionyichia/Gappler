# PROJECT PLAN: milestones, task tree and who does what

**What this is.** The layer above [`NEXT_STEPS.md`](NEXT_STEPS.md). `NEXT_STEPS` is a register of
everything we could do. This file decides what we *will* do, in what order, by when, and who owns
each piece. It also answers one question Dion raised directly: can three people work on this at the
same time without blocking each other.

**Who this is for.** Dion, Zongzhe and Sherman. Written so a reader who has never used ROS 2 can
follow it. Where a term is needed, it is explained on first use.

**Horizon.** Four fixed dates set by the university anchor this plan, not a week count we chose:
the project plan and Gantt chart are due **2026-10-05**, the interim presentation falls between
**2026-10-26 and 2026-11-13**, the final report is due **2027-03-28**, and the oral presentation and
demonstration run **2027-04-05 to 2027-04-16**. Section 5.2 has the detail and who each goes to.
Mapped onto the same 20 weeks of work the first version of this plan estimated, and with the
end-of-September recess, the November exam period plus the first days of December, and half the
winter break removed as non-working time, that work now spans **31 calendar weeks**: week 1 starting
Monday 2026-09-14, week 31 ending Sunday 2027-04-18. The goal of the whole effort is a published
result, so the plan protects the one milestone that carries a research claim and treats several other
milestones as droppable.

**Effort available.** Dion about 12 hours a week, Sherman 8 to 10, Zongzhe 8 to 10. Call it 30
person-hours a week. Of the 31 calendar weeks, 22 are full working weeks and 2 (the back half of the
winter break) run at half speed; the rest — the recess, the exam period, and the front half of the
winter break — are not working time at all. That is about 690 nominal person-hours, roughly 620 once
travel and meetings are taken out at the same ratio the original 20-week estimate used. Named work in
this plan comes to roughly 406 hours excluding the optional milestone, which is about 65 percent of
capacity — more slack than the original 79 percent, because the real deadline is mid-April, not the
end of January. Section 8 says what we drop first if that slack does not hold.

**The visual version** of this plan is [`next-steps-map.html`](next-steps-map.html), published at
<https://claude.ai/code/artifact/65c7784d-1284-4ebd-a481-43951f8ce676>. It carries the milestone
schedule as a picture and the task tree as something you can click through to see who is waiting on
whom. Republish it to the same link after any change here.

**Reading order.** Section 1 for the answer. Section 3 if you doubt the split. Section 5 for the
milestones. Section 6 for your own tasks. Section 8 before you panic about the schedule.

**Priority labels used here.** `P0` blocks other people. `P1` on the path to the research claim.
`P2` useful, droppable. These replace the coloured markers used in `NEXT_STEPS`.

**Provenance tags** are the same as everywhere else in these docs: `[code]` read from source,
`[reported]` told to us by a person, `[inferred]` reasoning, `[unverified]` found by static analysis
and not yet confirmed at the machine, `[paper]` from the HiCo-Nav paper.

---

## 1. Summary and results

**The short version.** The work *can* be split three ways, starting in week 3. It cannot be split
today, and the reason is two specific removable obstacles, not the shape of the code. Removing both
is the entire content of milestone M0 and costs about two weeks. After that there are three streams
that touch almost nothing in common: the arm and perception stream (Dion), the navigation and
algorithms stream (Zongzhe), and the hardware and experiment stream (Sherman).

**The two obstacles.**

| # | Obstacle | Why it stops a split | Cost to remove | Owner |
|---|---|---|---|---|
| 1 | Nothing in this repository runs from a fresh clone. Every absolute path points at a user and a repository name that no longer exist. `[code]` `NEXT_STEPS` 2.5 | Only the one machine that already holds working state can run anything, so only one person can do real work at a time | About 12 hours | Zongzhe |
| 2 | The arm and the LiDAR both need the workstation's only wired network port, at two different addresses. `[unverified]` `ORIENTATION` 8.13 | The arm and the navigation base cannot be powered on together, so arm work and navigation work cannot happen in the same session | About 5 hours plus a network switch | Sherman |

**The critical path to a publishable result** runs M0, then M1 arm, then M2 gaze and voice, then M5
camera mounted and calibrated, then M6 memory graph, then M8 the contribution. Navigation (M3) and
goal ordering (M9) are **not** on that path. That is worth saying plainly, because M9 is the part of
the HiCo-Nav paper with the largest reported benefit, and it is still the first thing we cut.

**The research claim this plan is built to support.** The memory graph in HiCo-Nav is queried with a
sentence, which finds an object *class*. The Aria glasses give us something the paper does not have,
which is where the wearer was looking. Carrying a gaze-cropped image feature into that query should
resolve a specific *instance*, "that mug", not "a mug". That is one ablation with a number attached,
and it needs the graph, the gaze and the arm all working. Everything before M8 exists to make M8
measurable.

**What we are explicitly not building.** The return-to-user leg of the original demonstration, the
pose fusion node, the ArUco marker path, and cross-camera feature matching as a requirement. Reasons
and evidence in section 4.

---

### 1.1 Open decisions, for whoever picks this up next

These are live and unsettled as of 2026-09-16. A new session should start here.

> **Seven of these were settled on 2026-09-20** in `T0.7`, the channel contract. The reasoning for
> each is in [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md) §6. The rows below say what was decided.

| # | Decision | Why it is open | Where the evidence is |
|---|---|---|---|
| ✅ D1 | **Answered 2026-09-20.** Sherman takes nav bring-up (T3.3 to T3.6) and the pose-source study, not M0 portability. Zongzhe keeps the memory graph and the bridge nodes. The line between them is the goal: Sherman gets the robot to a commanded point, Zongzhe decides which point | `CHANNEL_CONTRACT` §1, §6 T-1 |
| ✅ D2 | **Answered 2026-09-20.** Dion keeps T5.5 to T5.7 | `CHANNEL_CONTRACT` §6 T-2 |
| D3 | Drop the milestone Lead column, or replace it with a single "accepted by" name? | Per-task owners already exist and M5 needed two leads, which is the proof the column does not fit | §5.1 |
| ✅ D4 | **Answered 2026-09-20.** In scope, staged: 2D localisation first, then T5.7's error study, then FAST-LIVO2 if the evidence says 2D localisation is the limit. Sherman owns it, now T5.9. Stretch goal S4 becomes planned work | `CHANNEL_CONTRACT` §6 N-5 |
| ✅ D5 | **Answered 2026-09-20.** No fix. `goto_glasses` comes out of the launch file, commented out with the reason, since the return leg is out of scope. That removes the race | `CHANNEL_CONTRACT` §6 N-1 |
| D6 | Rework the M1 and M2 hour estimates on the repair evidence? | The code volume is far smaller than budgeted, but verification time may absorb the difference | §2.5, §6.3, §6.4 |
| D7 | Zongzhe's pronouns | This document guesses at "he" and nobody has confirmed it | — |
| ✅ D9 | **Answered 2026-09-20: build the appearance baseline in M2 first, then decide on the evidence.** Original question kept below. Should gaze pick the object by geometry as well as by appearance? Raised by Dion 2026-09-19 | Today's cross-camera step, and M8's image feature as planned, cannot tell two identical objects apart `[inferred]`. A geometric method can, and it would strengthen the M8 claim. Try the cheap option in M2 first and decide on the evidence. If asked "isn't this niche?", the answer is in §2.13 under "Why this is worth doing" | `NEXT_STEPS` §2.13, S9 |
| ✅ D8 | **Answered 2026-09-20: buy a replacement, replacements are available `[reported]`.** Original question kept below. If the wrist D435i does not survive a replug, do we repair it or buy a replacement? | It is the arm's only camera, so M1's live-mask step and every fallback that used it are blocked until this is answered. A provided base D455 does not settle the wrist-camera decision | §2.6, §8.2, T0.1 |

---

## 2. Current state

Condensed from `ORIENTATION`, `CODE_AUDIT`, `TESTBENCH_PLAN` and the HiCo-Nav paper review. Nothing
here is new. It is here so the plan can be read without the other five documents open.

### 2.1 What works today

| Thing | Evidence |
|---|---|
| The glasses transcribe speech and publish the object word | `ORIENTATION` 6.1. This is the one part of the perception chain that is connected |
| The arm workspace compiles, 22 packages | `TESTBENCH_PLAN` W4, lab box, 2026-09-11 |
| MoveIt plans and executes against a simulated arm | `bench/sim_moveit.sh` passes |
| The grasp state machine runs a full cycle against a simulated arm | `bench/state_machine_sim.sh`, W2 |
| AnyGrasp runs in the project's single Python environment, licence passes, grasps found | W5 survey |
| The navigation workspace compiles, 10 packages, 2 min 34 s | `TESTBENCH_PLAN` W4b, lab box, 2026-09-14 |
| The five navigation nodes run against a stand-in Nav2 and behave as the audit predicted | `bench/nav_nodes.sh`, W7, 2026-09-14 |
| The regression bench catches renamed channels, frames and parameters, and all of tiers 0 to 3 now run on the box | `bench/` tiers 0 to 3 |

### 2.2 What does not work today

| Thing | Consequence | Source |
|---|---|---|
| Nothing runs from a fresh clone | No second machine, no second person | `NEXT_STEPS` 2.5 |
| The grasp path cannot produce a grasp as written, for three interlocking reasons | The arm cannot pick anything up under its own perception | `CODE_AUDIT` A |
| The navigation code compiles and its nodes run, but nothing has ever driven the base from this repository | Navigation is untested above the node level | `TESTBENCH_PLAN` W4b, W7 |
| Four things the robot needs are in nobody's repository | The navigation launch fails at run time | `NEXT_STEPS` 2.9 |
| The wrist D435i is faulty. Its colour stream fails with an I/O error, and a reset took it off the USB bus entirely | No live mask for the arm, and no recorded frames for anything else, until someone replugs it and it is confirmed working | `TESTBENCH_PLAN` W6, 2026-09-14 `[observed]` |
| The glasses publish only the spoken word. Images, gaze, and pose are switched off | Gaze cannot reach the robot | `ORIENTATION` 6.1 |
| Two different programs claim the same three segmentation channels | Turning one on collides with the other | `ORIENTATION` 6.5 |
| The segmentation program the arm actually uses never listens for the spoken word. It looks for the literal word "box", fixed in the source | Speech cannot change what the arm looks for, and nothing reports that the request was dropped | `CODE_AUDIT` L1 |
| There is no forward-facing camera on the base | The memory graph has no input | `ORIENTATION` 9, paper review 6.1 |
| The arm has never been commanded to move | Every arm number in these docs is a prediction | `ORIENTATION` 8.1 |

### 2.3 Resources and their limits

| Resource | Count | Limit it imposes |
|---|---|---|
| Workstation in the lab | 1 | Shared with other accounts. CPU is throttled to 800 MHz, so builds take about four times longer than they should. Home directory is 96 percent full |
| Wired network port | 1 | See obstacle 2 above |
| RealMan RM65 arm | 1 | One arm session at a time, and a person must be present |
| Mobile base and LiDAR | 1 | Same |
| Aria glasses | 1 | Cannot leave the lab `[reported]` |
| Travel to the lab | 20 minutes each way | Lab work should be batched into planned sessions with a written agenda, not done ad hoc |

---

## 2.5 What four code checks established, 2026-09-14

Four read-only passes over the working tree, run to test whether the estimates in section 6 matched
what the code actually is. All `[code]` unless marked. They change how several tasks should be read.

**Navigation is retrieval, not development.** The `robot_slam` package in this repo is the code that
actually drove the base, and it is the newer copy: W4a diffed it against `~iot22/Ros2Workspaces` and
found the repo's version tidier and functionally equal, with `qos_relay.py` fixing a shutdown crash
the working copy still has. What is missing is not code but four artifacts that live in nobody's git:
`xpkg_demo`, `robot_navigation` (the Nav2 launch), the generated Livox manifest, and the saved map.
`Navigation_Module` has since been compiled here for the first time, 10 of 10 packages, 2026-09-14: see 2.6.

**The perception and arm work is overwhelmingly repair.** Roughly 3,000 lines of written, largely
complete code across the nine files that matter. The blocking defects total 100 to 150 lines of
change and none of them imply a redesign. Specifically: A1 is one inverted condition at
`anygrasp_detection_node.py:182`, and fixing it correctly makes **A2 a no-op**, because
`grasp_state_machine.cpp:178-179` already gates on the state A1 should have used. A3 is a flag at
`grasp_state_machine.cpp:41`; flipping it is trivial, but it exposes about 150 lines of complete,
never-executed candidate-handling code, and that debugging is the real cost. C1 to C7 come to 15 to
25 lines changed.

**The glasses are not missing features, they are switched off.** Four of six stages are commented out
in `src/main.py:102-113`, which is four comment characters. Behind them sit `rgb_worker` (71 lines),
`et_worker` (42 lines), a 184-line `EyeTrackingPipeline` and its weights on disk at
`src/models/projectaria_eyetracking/weights.pth`. Gaze estimation is complete and publishes to a real
topic declared in `shared/global_config.yaml:13`. **What is absent is the consumer:** nothing in
`ros2_robot_ws/` subscribes to it. T2.2 is therefore much smaller than budgeted and the real work is
on the arm side.

**Segmentation is already half-unified.** Both call sites already share one `SAM3Model` and one
`ObjectMaskVisualizer.get_best_mask()`. The duplication is about 40 lines of ROS message-building
glue. One service is 50 to 100 lines of new code, not a rewrite.

**The memory graph is genuinely from scratch.** No graph structure, no embedding of any kind, no CLIP
in `pyproject.toml`, no solver, no VLM call anywhere in the repository. `src/services/feature_matching.py:1-77`
looks close but is SuperPoint plus LightGlue producing geometric keypoint descriptors, which answers
"where is this point in the other image", not "is this the same object". It cannot substitute. The
nearest precedent for a model call is `src/services/prompt_extractor.py:31-36`, which loads
Qwen2.5-0.5B-Instruct locally. It is text-only and has never been given an image.

**Two facts that change the pose-source question.** The LiDAR's own inertial sensor is already
publishing: `livox_lidar_callback.cpp:107` enables it unconditionally and `lddc.cpp:664-687` always
creates the publisher, so `livox/imu` is live and nothing subscribes. That closes the open question in
the paper review §6.2. And the vendored OpenVINS copy is not the shortcut it looks like: it has never
been built, it sits in a nested `src/` the built workspace never sees, and its only calibration is
`config/aria/`, tuned to the glasses rather than to a base camera.

**One new defect, recorded as `CODE_AUDIT` E5.** `goto_glasses.py` has an outbound path on
`/aria/audio/prompt`, the same spoken command that starts the forward leg, and both send goals to the
one Nav2 action server. It launches unconditionally in `slam_localization.launch.py:156-159`. This
means the out-of-scope decision on the return leg in §4.2 does **not** make E1 droppable.

---

## 2.6 What the bench established on the box, 2026-09-14

The bench backlog that had been waiting since the lab box went off is cleared. Full detail and the
raw output are in `TESTBENCH_PLAN` "▶ Start here" and `docs/bench-runs/`. Four results
change something in this plan.

**Tiers 0 to 3 are complete. Both workspaces build.** `./bench/build.sh nav` compiled
`Navigation_Module` for the first time: **10 of 10 packages, 2 min 34 s, colcon exit 0**
`[observed]`. The blocker the plan expected did not exist. Livox-SDK2 is already installed on the
box at `/usr/local/lib/`, so there was no sudo step, and `Livox-SDk2/` is itself built by colcon as
`livox_sdk2` through plain-CMake support despite having no manifest. That corrects an earlier
`[code]` claim that colcon ignores it. The bench's Livox manifest template turned out byte-identical
to `iot22`'s generated one. **T3.1 is done before M3 started.**

**The navigation nodes behave exactly as the audit predicted.** `./bench/nav_nodes.sh` passed on the
first run with no fix: 6 controls pass, all 4 expected failures reproduced, nothing skipped
`[observed]`. **E1, F1 and F2 move from `[unverified]` to `[observed]`**, which means the audit's
reasoning about this subsystem is now evidence-backed rather than static analysis. E1's goal landed
2.0 metres from where the wearer actually was. F1 wedged the approach node so a second object got no
goal at all. F2's latch refused every later return. J4, the point cloud relay, is **not** a problem
at this LiDAR's rates: 50 of 50 frames of 520 kB at 10 Hz, 1.9 ms mean latency, nothing dropped.
New finding **F4**: all five navigation nodes exit with a traceback on Ctrl+C, and
`goto_glasses`'s cancel is never called on shutdown, so an interrupt mid-leg would leave the Nav2
goal live and the base driving `[inferred]`. The audit now holds **51 findings**.

**The wrist camera is faulty, and this is the one result that costs us something.** With Dion's
go-ahead the D435i was started to record frames for W6. It was already broken before anything was
launched: depth opened, colour failed with `xioctl(VIDIOC_S_FMT) errno=5 Input/output error`
followed by a loop of protocol errors, on a healthy USB 3.2 link with nothing else holding the
device. Passing librealsense's own documented `initial_reset` made it worse and the camera dropped
off the USB bus entirely, with no re-enumeration. It **needs a physical replug**, and whether it
survives one is unknown `[observed]`. Until then there is no live mask for the arm and no recorded
frames for anything. This touches T1.12, the M5 fallback and T6.2. It is now a named risk in §8.2
and a new open decision, D8.

**Two bench bugs found and fixed.** The glasses check used to pass with no glasses plugged in, and
the camera check used to pass on the USB vendor id alone, matching even the Bluetooth adapter. Both
are corrected and confirmed on the box, and a new check now grabs an actual frame rather than
trusting an id. Worth noting as a pattern: **a check that cannot fail is worse than no check**, and
two of them survived in a bench built specifically to catch silent failures.

---

## 3. Findings: can three people work in parallel

This section answers Dion's question directly. The claim under test was "there are no obvious splits
for us to segregate work for now".

### 3.1 Verdict

**Partly false.** The claim is true for the next two weeks and false after that. Three streams exist
and they are cleanly separable. What hides them is that the two obstacles in section 1 sit in front
of all three, so from where we stand today everything looks like one queue.

### 3.2 Why it looks unsplittable

Four reasons, all real.

1. **One robot and one workstation.** Physical contention is genuine and does not go away.
2. **Nothing runs anywhere else.** Obstacle 1. Until a second person can build and run the code on
   their own machine, delegation means handing someone a task they cannot execute.
3. **Nobody on the team has deep ROS 2 experience yet.** Anything shaped like a ROS task therefore
   looks like it needs whoever last read that part of the code.
4. **The subsystems already look entangled.** Reading the topic map, everything talks to everything.

### 3.3 What actually constrains parallel work, and what does not

The third and fourth reasons above do not survive inspection.

**ROS 2 couples subsystems by channel name and message type and by nothing else.** `ORIENTATION` 1
states this and the code confirms it: no subsystem imports another. That property is exactly what
makes parallel work possible. If we write down the channel contract first, three people can build
against it independently and find out at integration time whether they agreed. The bench already
freezes those names, so a disagreement fails loudly instead of silently.

**The bench already supplies stand-ins for the hardware.** A simulated arm with fake joints, a fake
navigation server that can be told to fail, synthetic camera and depth publishers, and a private
message channel so two people on the same workstation cannot see each other's traffic. Two people
can run node-level work on that box at the same time. The only things that genuinely cannot be
shared are the physical arm, base and glasses.

**Most of the open work needs no hardware at all.** Counting the open items in `NEXT_STEPS` and
`CODE_AUDIT`, roughly two thirds can be done from a laptop or over the network: path portability,
the configuration tree, the vendor and owned-code separation, most of the 49 audit findings, the
HiCo-Nav memory graph built from recorded data, and the goal-ordering work which is LiDAR-only and
testable in a simulator.

**Mechanical work does not contend with code at all.** The camera mount, the network switch, the
physical measurements that three separate constants currently disagree about, the arm's swept volume,
a fixture that puts the target object in the same place every trial. None of it touches the
repository.

### 3.4 The real constraints, stated precisely

| # | Constraint | Effect on the plan |
|---|---|---|
| C1 | One arm, one base, one pair of glasses, and a person must be in the room | At most one hardware session at a time. Batch them. Write the agenda before travelling |
| C2 | One wired port, two devices, two required addresses | Until obstacle 2 is removed, arm sessions and navigation sessions are mutually exclusive. This is the least appreciated blocker in the project |
| C3 | Nothing runs from a fresh clone | Until obstacle 1 is removed, there is one working machine and therefore one worker |
| C4 | Dion is on the critical path for the arm, the perception chain and the contribution | Dion is the contention point, not the hardware. Mitigated by handing navigation to Zongzhe entirely and by writing the contract in week 1 |

### 3.5 The three streams

**Revised 2026-09-20 (`T0.7`).** The streams are named after kinds of work, not after subsystems.
That matters because navigation is not one person's: it has a software half and a physical half, and
they suit different people.

| Stream | Owner | What it covers | Where the work happens |
|---|---|---|---|
| **Arm and perception** | Dion | Arm bring-up, the grasp path defects, one segmentation service, gaze, the calibration and localisation-error study, the contribution | Lab plus the box |
| **Algorithms and graph** | Zongzhe | The memory graph, the reasoning layer, goal ordering, the nav bridge nodes and the goal-emitting node | Laptop and the box |
| **Platform and experiments** | Sherman | Network, nav bring-up, mapping and localisation, the pose-source and FAST-LIVO2 study, camera mount, the calibration rig, physical measurements, the runbook, trial fixtures, running trials | Lab plus the box |

**The line inside navigation is the goal.** Sherman owns everything that gets the robot to a
commanded point: drivers, SLAM, Nav2 configuration, the static transforms, mapping, localisation and
the pose source. Zongzhe owns everything that decides which point: the memory graph, goal ordering,
and the bridge nodes that turn an object position into a drive goal.

**The handover points are written down.** Twelve live channels, four planned ones, five measurements
and the hidden channels are in [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md), which is the single
source for all of it. The three headline ones remain the approach goal, the drive-here goal and the
arrived signal.

---

## 4. Scope: what is in and what is out

Dion's instruction was that we are not reproducing the whole original demonstration. We are building
what the HiCo-Nav integration and the research claim need. This section writes that down so it is
not relitigated later, and so a supervisor cannot reasonably expect both.

### 4.1 In scope

| Capability | Why it is needed |
|---|---|
| Speech to an object word | The instruction input for the memory graph. Already works |
| Gaze published from the glasses | The contribution depends on it. Currently switched off |
| Glasses RGB image published | The gaze crop comes from this frame. Currently switched off |
| One segmentation service, close range, on the wrist camera | Feeds the grasp predictor |
| Grasp prediction and execution on the real arm | Without it there is no task to navigate for |
| Navigation: map, localise, drive to a goal, report arrival | The graph produces a place, something has to drive there |
| A forward-facing camera on the base, mounted and calibrated | The memory graph is built from its images and depth |
| The memory graph and the reasoning layer | This is the integration |
| The gaze-conditioned instance query and its ablation | This is the claim |

### 4.2 Out of scope, with reasons

| Capability | Why it is out | Source |
|---|---|---|
| Return to the user after grasping | Needs the pose fusion node, the ArUco path and the glasses localised in the map. Three separate broken things for a leg the research claim does not use | `ORIENTATION` 6.1, 6.3, 6.4 |
| The pose fusion node as documented | Its code and its documentation describe different programs. Fixing it only matters for the return leg | `ORIENTATION` 6.4 |
| Cross-camera feature matching as a requirement | The contribution proposes replacing it. It stays as the comparison baseline, not as a dependency | `ORIENTATION` 5 |
| The HiCo-Nav motion layer, meaning its own planner and controller | Nav2 already does this and is tuned for this chassis. Adopting it means retuning the part that can drive a robot into a wall, for no benefit to the claim | Paper review 5.1 tier C |
| FAST-LIVO2 localisation | A bring-up project of its own. Start with the existing 2D localisation and measure whether it is good enough | Paper review 6.2 |
| ~~The full repository reorganisation into one folder per node~~ **In scope since 2026-09-21 (Dion).** Specified in `NEXT_STEPS` §2.15, done on the T0.10/T0.11 branch alongside T0.11's per-subsystem suites | ~~Referenced in four documents and specified in none. Do the vendor separation only, as part of M0, and leave the rest~~ | `NEXT_STEPS` 2.11, 2.15 |
| The Habitat simulator baseline | Only needed to evaluate goal ordering, which is the optional milestone | Paper review 5.6 |

### 4.3 Deferred, meaning wanted but after this plan ends (mid-April 2027)

Naming things descriptively across the whole repository, the full configuration tree, and replaying
recorded data as a regression test.

**No longer deferred, as of 2026-09-16:** a continuous integration job running the bench on push.
It is now `T0.10` in the task tree below, gated on `T0.5` (M0's acceptance test, a second clone
building and passing the bench) rather than on the whole plan finishing — see `NEXT_STEPS.md` §2.12
for the reasoning and scope.

---

## 5. Milestones

### 5.1 The spine

Eleven milestones. M0 is a tax. M1 to M4 make the system we already have work. M5 to M7 are the
integration. M8 is the claim. M9 is optional. M10 is the write-up.

| # | Milestone | Done means | Dates | Lead | Priority |
|---|---|---|---|---|---|
| **M0** | Everyone can build and run | Two people who are not Dion have cloned the repository on their own machine, built it, run the bench and got the same result. The arm and the LiDAR answer on the network at the same time | 14–27 Sep 2026 | Zongzhe | P0 |
| **M1** | The arm picks something up | With the emergency stop verified and a validated home pose, the arm grasps a box from a table using a mask from its own camera. Five attempts, success rate recorded | 5 Oct – 1 Nov 2026 | Dion | P0 |
| **M2** | Voice and gaze reach the arm | You say "grab the box", you look at one of two boxes, and the arm picks the one you looked at | 26 Oct 2026 – 3 Jan 2027 | Dion | P1 |
| **M3** | The base navigates | A map of the lab exists, the robot localises in it, and it drives to a commanded point and reports arrival. Ten runs, repeatability recorded | 12 Oct – 27 Dec 2026 | Zongzhe | P1 |
| **M4** | The current system, closed loop | One run: speak, look, the base drives, the arm grasps. Per-stage timing recorded | 28 Dec 2026 – 17 Jan 2027 | Dion | P1 |
| **M5** | The base has a calibrated forward camera | A RealSense D455 is mounted on the base, its position relative to the LiDAR is calibrated, LiDAR points project onto the right pixels in its image, and the camera-pose error is written down as a number | 5 Oct 2026 – 17 Jan 2027 | Sherman mount, Dion calibration | P0 |
| **M6** | The memory graph is built offline | From recorded data, the system produces a set of object entries with a 3D position and an image feature each, merged so the same physical object appears once. Querying it with a sentence returns sensible objects | 28 Dec 2026 – 7 Feb 2027 | Zongzhe | P1 |
| **M7** | The graph drives the robot | A spoken instruction produces an approach goal read out of the graph rather than from live perception, the base drives there, and close-range perception takes over | 1–28 Feb 2027 | Dion | P1 |
| **M8** | Gaze picks the instance | The gaze-cropped image feature is carried into the graph query. Ablation with and without, N trials each, success rate reported | 8 Feb – 14 Mar 2027 | Dion | **P1, protected** |
| **M9** | Frontier scoring and visit ordering | The robot chooses where to explore next using the paper's scoring, measured against a baseline | 2 Nov 2026 – 21 Feb 2027 | Zongzhe | P2, optional |
| **M10** | Demonstration and paper | A recorded end-to-end run and a paper draft whose claim is M8's number | 1–21 Mar 2027 | All | P1 |

Several milestones (M2, M3, M5, M9) run calendar-long because the exam period and the winter break
sit inside their span, not because the work itself takes that long — see 5.3 for how many of those
weeks are actually working weeks.

### 5.2 The four dates that are not negotiable, and two internal checkpoints

Set by the university, not by us. Miss one and there is no recovering the mark, so everything else in
this section is built to protect them.

| Deliverable | Due | Goes to |
|---|---|---|
| Project plan, Gantt chart and budget | **Monday 2026-10-05** | Supervisor |
| Interim presentation | **2026-11-10 to 2026-11-13** (university window: 2026-10-26 to 2026-11-13) | Panel |
| Final report, softcopy plus similarity report | **Sunday 2027-03-28** | Main supervisor and the REP Office (Ms Yang Huixin) |
| Oral presentation and demonstration | **2027-04-05 to 2027-04-16** | Panel |

Have the finished, similarity-checked report with the supervisor at least a week or two before
2027-03-28 — that date is when the final copy is due, not when a draft may first reach them, and the
plan should leave time for review and amendments before it.

The interim presentation lands seven working weeks in, well before this plan's own "system working
end to end" milestone (M5, done means a calibrated camera and a recorded speak-look-drive-grasp run)
is anywhere near finished. What gets shown there is necessarily a progress report, not a demo — the
table below keeps the original December checkpoint concept, moved to fit the real calendar:

| Date | What should exist |
|---|---|
| **2026-11-10 to 2026-11-13**, interim presentation | M0 done. M1 and M3 under way. A progress report, not a working demo |
| **2027-01-17**, internal checkpoint | M0 to M5 done. A recorded run of the current system: speak, look, drive, grasp. A camera on the base with a calibration you can show a picture of |
| **2027-03-28**, final report due | M6 to M8 and M10 done. A recorded run driven by the memory graph, and an ablation table, written up |
| **2027-04-05 to 2027-04-16**, oral presentation | The same result, presented and demonstrated live |

### 5.3 Calendar

Week 1 is Monday 2026-09-14. Four spans of calendar time are not working time and nobody should plan
to touch this project in them: the recess in the last week of September (2026-09-28 to 2026-10-04),
the November exam period plus the first days of December (2026-11-09 to 2026-12-06), and the front
half of the winter break (2026-12-07 to 2026-12-20). The back half of the winter break (2026-12-21 to
2027-01-03) is kept as working buffer at half speed, the same treatment the original plan gave those
two weeks. Stretched over those gaps, the original 20 weeks of work now spans 31 calendar weeks,
ending Sunday 2027-04-18.

```
wk    1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
M0    #  #
M1             #  #  #  #
M2                      #  #  #  #  #  #  #  #  #  #
M3                #  #  #  #  #  #  #  #  #  #  #
M4                                                 #  #  #
M5             #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
M6                                                 #  #  #  #  #  #
M7                                                                #  #  #  #
M8                                                                   #  #  #  #  #
M9                         .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
M10                                                                           #  #  #
key         R                 E  E  E  E  O  O  B  B
               ^              ^                                                        ^     ^  ^
            plan due       interim pres.                                          report due  oral pres.
```

`R` recess, no work · `E` exam period including the first days of December, no work · `O` winter
break, off, no work · `B` winter break kept as buffer, half speed · `#` a milestone with a lead
already named · `.` M9, optional and the first thing cut. The four carets are the dates in 5.2: the
plan and Gantt chart due at the start of week 4 (2026-10-05), the interim presentation in week 9
(2026-11-10 to 2026-11-13), the final report due at the end of week 28 (2027-03-28), and the oral
presentation across weeks 30 to 31 (2027-04-05 to 2027-04-16).

### 5.4 Milestone detail

Each entry gives the acceptance test, the main risk, and what it depends on.

**M0. Everyone can build and run.** Accept when Zongzhe and Sherman each run `./bench/run.sh` on a
fresh clone on their own machine and get the same verdict as Dion, and when `ping` reaches both the
arm and the LiDAR from the workstation in the same session. Risk: the path work touches four entry
points at once and there is no test that proves the old behaviour is preserved, because the old
behaviour never worked. Mitigation: change paths only, land it as its own commit, and re-run the
contract check before and after.

**M1. The arm picks something up.** Accept on five grasp attempts of a box on a table, with the
success rate written down whatever it is. Risk: the arm has never been commanded to move, so the
first session is discovery rather than verification. Mitigation: three short sessions rather than
one long one, in the order handshake, then one commanded motion, then grasping. Depends on M0
obstacle 2, because the arm needs its network address.

**M2. Voice and gaze reach the arm.** Accept when, with two boxes on the table, the arm picks the
one the wearer looked at, three times out of four. Risk: the published gaze point assumes every
object is 1.5 metres away, so it drifts for objects nearer or further `[code]` `ORIENTATION` 8.8.
Mitigation: measure the error against known distances before relying on it, and record the usable
range as a number in the results.

**M3. The base navigates.** Accept on ten drives to a commanded point with the position error
recorded. Risk: **lowered on 2026-09-14.** The workspace now compiles, 10 of 10 packages, and the
five nodes pass the bench against a stand-in Nav2, so T3.1 and T3.2 are done before M3 opens. What
is left is the part that was always the real risk, which is that nothing in this repository has ever
driven the base, and that `robot_navigation` and `xpkg_demo` still live in nobody's git. M0 brings
those in.

**M4. The current system, closed loop.** Accept on one complete recorded run. Risk: this is the
first time the arm and the base are powered together, which is exactly what obstacle 2 prevents
today. Mitigation: obstacle 2 is removed in week 1.

**M5. The base has a calibrated forward camera.** Accept when LiDAR points projected into the
camera image land on the right objects, shown as a picture, and when the camera-pose error over a run
is written down as a number. The mount half is Sherman's. The calibration and error half, T5.5 to
T5.7, is Dion's and is the part that produces a result rather than a setup step. Risk: a project D455
is provided, but its USB 3 connection and live RGB-D stream remain unverified. The mount CAD is
complete; physical fabrication, fit, and calibration remain.

**M6. The memory graph is built offline.** Accept when a recorded drive through the lab produces
object entries, the same physical object is not registered twice, and a sentence query returns it.
Risk: the merge test depends on camera pose accuracy, and our pose comes from 2D localisation which
has no reliable pitch or roll `[inferred]` paper review 6.2. Mitigation: duplicated object entries
are directly visible, so measure the duplication rate and decide from data whether a better pose
source is needed.

**M7. The graph drives the robot.** Accept when a spoken instruction with no object in view causes
the robot to drive to the right place and then grasp. Risk: the graph's object position is at
navigation precision, not grasping precision. This is expected and is why close-range perception
takes over on arrival.

**M8. Gaze picks the instance.** Accept on N trials with the feature and N without, with the
success rates reported side by side. Risk: N is small and the effect may be small. Mitigation: fix
the trial procedure and the object placement before running anything, which is why Sherman builds a
fixture in M5. **This milestone is protected. It is the only one that produces a claim rather than a
system.**

**M9. Frontier scoring and visit ordering.** Accept when the robot's chosen exploration order beats
a nearest-first baseline on a measured metric. Risk: it is a reimplementation of someone else's
contribution and it is not on the path to M8. **This is the first thing we cut.**

**M10. Demonstration and paper.** Accept when a recorded run exists and a draft exists whose
central table is M8's ablation.

---

## 6. The task tree

### 6.1 How to read it

Each row is a task node. A task can start when every task in its "after" column is finished.
`Where` says `off` for anywhere with a laptop, `box` for the lab workstation over the network, and
`lab` for physically at the robot. `Hours` is one person's time unless two owners are listed, in
which case it is the total across both.

The point of the tree is not the estimates. It is the "after" column. If your task has nothing in
that column and nobody has started it, you are free to pick it up.

### 6.1b What kind of work each task is

Every task carries a **type** as well as an owner. The type says what the work actually is, which
turns out to matter more for estimating than who does it.

| Type | Means | Count |
|---|---|---|
| `build` | New code. None of it exists today | 18 |
| `fix` | Repair of existing code that is written but defective | 6 |
| `rewire` | Existing, complete code reconnected, re-enabled or consolidated. No new logic | 3 |
| `bring-up` | Make existing things run: retrieve, compile, install, mount, power on | 13 |
| `measure` | Trials, calibration, error characterisation, tests. Produces numbers, not code | 18 |
| `decide` | A decision to settle, or a document to write | 12 |

**Read that table before the schedule.** Eighteen of seventy tasks are new code and nine are
repair or rewiring. The remaining forty-three are bring-up, measurement and decisions. This is not a
project that builds a robot. It repairs one, measures it, and adds one new component, which is the
memory graph. (`T0.10`, the CI job added 2026-09-16, and `T0.11`, per-subsystem tests added 2026-09-19, are the seventeenth and eighteenth `build` tasks.)

Two consequences for the hours in the tables below. Where the work is `fix`, the code change is
usually small and almost all the time goes into verifying it, so an estimate that looks large for the
line count is not necessarily wrong. Where the work is `measure`, the time is lab hours and travel
and cannot be compressed by working harder.

### 6.2 M0. Everyone can build and run (14–27 Sep 2026)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T0.0 | **DONE 2026-09-21.** ~~Cherry-pick what is worth keeping off the `realman_manip` branch onto `main`, then stop treating that branch as live~~. `calibration.json`, `env.sh` and `anygrasp_node.sh` taken, the startup guide archived, `SETUP.md` skipped. Box checks passed for the calibration file and `env.sh`. One check still owed: compare the glasses serial with the file's, when the glasses are plugged in. Per-file table in `NEXT_STEPS` §3.3 | bring-up | Dion | 3 | off | none |
| T0.1 | **Progress 2026-09-16:** an Intel RealSense D455 is provided to the project. USB 3 connection and live RGB-D stream remain unverified | decide | Sherman | 2 | lab | none |
| T0.2 | ~~Get a network switch. Add the second host address to the wired port. Prove the arm and the LiDAR both answer in one session~~ **Done 2026-09-16.** Switch wired: workstation port 1, LiDAR port 2, arm port 3. NetworkManager persists `.100`, `.10`, and `.5`; RM65 and MID-360 each replied from their required host address after a connection cycle | bring-up | Sherman, Dion | 5 | lab | none |
| T0.3 | **DONE 2026-09-19.** Make the repository run from a fresh clone. Paths inside the repository are computed from the repository root. Paths outside it move to one configuration file with sensible defaults | fix | Zongzhe | 12 | off | none |
| T0.4 | **DONE 2026-09-21, by Dion (was Zongzhe's).** `robot_navigation` and `xpkg_demo` copied from `~/rcp-old-ros-wkspace`, both build on the box. The Livox manifest moved out of `bench/nodes/` into its package. The map stays outside git by design (T0.3), recorded in `ASSETS.md`. `mtc_sim_test.launch.py` deleted rather than built, because `trivial_mtc.cpp` executes arm motion to an all-zero pose. `./bench/run.sh` exits 0 locally. **Left for Dion:** confirm the `bench` check is green on the PR, then turn on branch protection. ~~Bring into git the four things the robot needs that live in nobody's repository: the base bring-up package, the navigation launch package, the LiDAR package manifest, and the saved map~~. **Added 2026-09-19, to turn CI green:** also settle `rm_mtc/launch/mtc_sim_test.launch.py`, which starts an executable `rm_mtc` never builds. Either add the build target (`src/trivial_mtc.cpp` may be the missing source `[inferred]`) or delete the launch file. With that, all 7 static findings CI fails on today are cleared. **Done means `./bench/run.sh` exits 0, then Dion turns on branch protection for `main`** (require the `bench` check), so a red bench blocks merges from then on | bring-up | Zongzhe | 6 | box | T0.3 |
| T0.5 | Zongzhe and Sherman each clone the repository on their own machine, build it and run the bench. This is the acceptance test for M0 | bring-up | Zongzhe, Sherman | 8 | off | T0.3 |
| T0.6 | ROS 2 ramp, all three of us. Reading guide round 1, then run the simulated arm test and read what it printed | bring-up | All | 24 | box | T0.5 |
| T0.7 | ~~Write the channel contract: which stream owns which message channels, and the exact handover points between streams~~ **DONE 2026-09-20.** [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md): 12 live handovers, 4 parked with the return leg, 4 planned, 5 measurements, 11 hidden channels, the TF edge table, and 28 decisions including the nav split and the rename targets. It is the single source. `ORIENTATION` §5, §3.5 above and both HTML pages point to it | decide | Dion | 4 | off | none |
| T0.8 | ~~Clear the bench backlog that has been waiting since the box went off~~ **Done 2026-09-14.** Environment check, navigation build and the ten navigation node tests all ran, all passed, no fix needed. What is left of this task is W6, which is blocked on the faulty camera, and W8, which needs a person at the robot. See §2.6 | measure | Dion | 5 of 5 spent | box | none |
| T0.9 | ~~Measure the real base footprint and compare it with the 0.2 metre radius the navigation configuration assumes~~ **Done 2026-09-16 for the manufacturer chassis.** The Hexman Robotics ECHO-PLUS manual specifies `460 x 380 x 140 mm` and a `265 mm` stated rotation radius, so the `200 mm` Nav2 radius is not supported as conservative. Recheck the integrated footprint after mount fabrication | measure | Sherman | 3 | lab | none |
| T0.10 | **DONE 2026-09-21.** `bench` (L0-L2) runs on every PR into and push to `main` and `dev`, and both branches are protected, requiring `bench`. `dev` is the default branch. L3-L4 in CI moved to T0.11. **Stays with Dion (2026-09-20).** Briefly reassigned to Zongzhe in the rebalance, then kept: Dion wrote the bench and already has the design in mind, so it is faster with him even though it is not on the critical path. **Added 2026-09-16.** CI: wire up `./bench/run.sh` (and whichever Tier 3 scripts prove containerizable) to run automatically on every push, once a second clone has actually proven the fresh-clone story works. See `NEXT_STEPS.md` §2.12 for scope, provider choice, and what a green run does and does not prove. **Progress 2026-09-19:** started ahead of T0.5 on purpose, to test it on the next merge. `.github/workflows/bench.yml` runs Tiers 0-1 on every PR into `main` and every push to `main`. It fails strictly. It was red on the 7 known static findings until T0.4 cleared all of them on 2026-09-21. Tiers 2-3 still open. Later, with a `dev` branch: fast per-subsystem tests on PRs into `dev`, the full suite on `dev` into `main`. Merges are not blocked yet: branch protection goes on when T0.4 turns the bench green | build | Dion | 6 | off | T0.5 |
| T0.11 | **Added 2026-09-19.** Split the bench into one test suite per subsystem: glasses (`aria`), arm (`rm_mtc`), grasp (AnyGrasp and MinkowskiEngine), and navigation. Each suite covers its own code plus the channels it shares with other subsystems. CI then runs only the suites whose files a PR touched, plus the contract check. Do it alongside the one-folder-per-node refactor, since the folder layout decides how files map to suites. Also add a scheduled run of the full suite on `dev` every Monday and Wednesday night, so a break is traced to a few days of commits rather than a whole release. **Open, decide when this task starts:** Tiers 2-3 need ROS Humble and today only run on the lab box. Either register the lab box as a self-hosted GitHub runner (free, but tied to a box we may lose after 2026-11-16) or build a Docker image of the environment (portable, may cost image storage). **Decided 2026-09-19: self-hosted runner on the lab box, running L0-L4 only, never L5-L6 (robot check and hardware, not needed to merge; L6 was L5 until 2026-09-21).** Then create the `dev` branch: PRs into `dev` may pass with L3-L4 skipped, PRs into `main` must run L0-L4 with no level skipped. `run.sh` already runs every level a machine can and skips the rest; what remains is the runner, the branch, a no-skips switch for `main`, and branch protection. Before registering the runner, check the fork-PR risk: the repo is public. **Progress 2026-09-21:** `dev` created and made the default branch, both branches protected. Left: the runner, the no-skips `full` job on `dev` into `main`, the night schedule, the per-subsystem suites, and the fork-PR risk. Runner details: `runs-on: [self-hosted, lab-box]`, `concurrency: lab-box` so two runs never share the GPU and ROS channel, run it in `tmux` under `rcp2026` (no sudo). The night `schedule` only reads workflow files on the default branch, `dev`. Fork-PR risk, settle before registering: a self-hosted runner runs whatever a PR contains, on a box wired to the arm and base network. Either make the repo private (after GitHub Pro) or run the lab job only for PRs from this repo. Promote `dev` to `main` with a merge commit, never a squash, or later promotions conflict. **Stays with Dion (2026-09-20)**, same reason as T0.10 | build | Dion | 8 | off | T0.10 |
| T0.12 | **Added 2026-09-21, was `TESTBENCH_PLAN` W6.** AnyGrasp gate test and perception replay: record frames from the wrist camera, then replay them through segmentation and AnyGrasp on the box, so a perception change can be tested without the arm. Blocked: the wrist D435i is off the USB bus and needs a replug (T1.12 needs the same camera) | measure | Dion | 6 | box | none |

**T0.0 in detail. Done 2026-09-21, kept as the record.** `origin/realman_manip` shares no commit history
with `main`, so this is a file copy, not a merge `[code]` `ORIENTATION` 7. **Exactly 15 files exist
there and not on `main`**, and 10 of them are the pre-reorg flat layout `main` already reorganised
into subpackages. `main` is later on every shared arm file. **No code comes across.**

| File | Size | Take it? | Why |
|---|---|---|---|
| `RCP_NEW_USER_STARTUP_GUIDE.md` | 15.7 kB | **Taken 2026-09-19** into `docs/archive/`, marked historical | The only written account of the 2026-08-25 session that actually ran the arm |
| `docs/SETUP.md` | 21.2 kB | **Skipped 2026-09-19.** Nothing in it is missing from `main`'s docs | Same. It lands in `docs/`, so move it into `docs/` rather than the shared root, per the per-person rule |
| `env.sh` | 635 B | **Taken 2026-09-21**, box check passed, guard added | It already computes its own repo root from `BASH_SOURCE`, so it is portable as written. What needs re-checking on this clone is its claim that a repo-root `install/` is one complete overlay covering both workspaces |
| `calibration.json` | 9.1 kB | **Yes** | The Aria factory calibration dump for device `1WM10350101291`. `main` has only the derived kalibr chains, and this doubles as an offline test fixture for calibration parsing |
| `ros2_robot_ws/src/rm_mtc/src/perception/anygrasp_node.sh` | 1 line | **Taken 2026-09-21.** Both checkpoints are at the relative path it assumes on the box. It launches the tracker node, a different method from the detector `main` launches, not just a different checkpoint. See `NEXT_STEPS` §3.3 | Not named in the earlier audit. It records the invocation the verified session used: `--checkpoint_path log/checkpoint_tracking.tar --filter oneeuro`. `main` launches the **other** checkpoint, `checkpoint_detection.tar` (`ros2_robot_ws/src/main.py:28`). The bench already knows both exist (`bench/preflight.py:421-422`). Taking it costs nothing, nothing calls it, and it is the only written record of which checkpoint was proven to work. It feeds T1.10 |
| the other 10 | — | **No** | Pre-reorg duplicates: `src/config.py`, `src/services/eye_tracking.py`, `sam3.py`, `playback.py`, `ros_subscriber.py`, `realman_camera_subscriber.py`, `visualizer_archive.py`, `streaming_client_observer.py`, `model_inference_demo.py`, `temp.txt` |

⚠️ **Do not take `sensors_3d.yaml`.** It looks like a gain at `+25/-1` but the added content is
MoveIt Setup Assistant boilerplate pointing at a PR2 Kinect topic that does not exist on this robot.
`main`'s empty value is correct `[code]` `ORIENTATION` 7.

**Why this is first.** It is three hours, it needs no hardware and no lab box, it unblocks nobody
else so it cannot go wrong for anyone, and it closes a branch that four documents currently have to
explain. It also settles one thing T1.10 will otherwise have to rediscover, which is that two
different AnyGrasp checkpoints are in play and only one of them has ever been seen to work. Doing it
now means the startup guide and `SETUP.md` are on `main` before Zongzhe and Sherman clone in T0.5.

### 6.3 M1. The arm picks something up (5 Oct – 1 Nov 2026)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T1.1 | Answer the six open questions in the code audit and record the decisions. Several are choices, not fixes | decide | Dion | 3 | off | T0.7 |
| T1.2 | Safety fixes before any power: the emergency stop key that the launcher promises but does not exist, the stop program ignoring Ctrl+C, and the arm driver being launched twice. **Progress 2026-09-21:** the stop program is fixed (`CODE_AUDIT` B2, B2a, B2c). Ctrl+C, kill and a closed terminal all send the stop, no key is lost, and `bench/estop_delivery.sh` checks every path. Left: the launcher's stop key and the double driver launch | fix | Dion | 8 | off | T1.1 |
| T1.3 | Decide which home pose is correct and validate it on the simulated arm before using it on the real one. Fix the safety warning that still quotes the old pose (`CODE_AUDIT` B4) | decide | Dion | 4 | box | T1.1 |
| T1.4 | Physical safety setup at the robot: clear working volume, stop button within reach, mount and cable check | bring-up | Sherman | 3 | lab | none |
| T1.5 | Write the bring-up runbook. Power on to ready, in order, with the check at each step and what a failure looks like | decide | Sherman | 8 | lab | T1.6 |
| T1.6 | First powered arm session. Driver handshake, joint feedback arriving, no motion commanded | bring-up | Dion, Sherman | 3 | lab | T0.2, T1.2, T1.4 |
| T1.7 | First commanded motion, to the validated home pose, with a hand on the stop | bring-up | Dion, Sherman | 3 | lab | T1.3, T1.6 |
| T1.8 | Fix the three interlocking defects that stop the grasp path working: the inverted state condition in the grasp predictor, the consumer that only accepts candidates in one state, and the flag that makes the whole path unreachable | fix | Dion | 10 | off, box | T1.1 |
| T1.9 | Fix the concurrency defects in the state machine. One condition variable with two locks, and an unlocked read, are undefined behaviour rather than untidiness. Also the queue that grows without limit after a successful grasp (`CODE_AUDIT` C7, `[observed]` on the simulated arm) | fix | Dion | 8 | off, box | T1.8 |
| T1.10 | Decide which grasp prediction program is authoritative and make its Python environment reproducible from a script in the repository. **Progress 2026-09-21:** the environment half is done, `./envs/anygrasp/build.sh` (TESTBENCH_PLAN W5). Left: the decision, and stopping `main.py` launching it through `conda run` | decide | Dion | 6 | box | T1.1 |
| T1.11 | Grasp using the stand-in mask publisher, on hardware. Fix its wrong channel name first | bring-up | Dion, Sherman | 4 | lab | T1.7, T1.8, T1.9, T1.10 |
| T1.12 | Grasp using a live mask from the wrist camera with a fixed prompt word. Five attempts, success rate recorded | measure | Dion, Sherman | 4 | lab | T1.11 |

### 6.4 M2. Voice and gaze reach the arm (26 Oct 2026 – 3 Jan 2027)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T2.0 | Settle the open decision in `NEXT_STEPS` 2.2: patch the spoken word into the existing arm-side segmentation program, or retire it and restore the pipeline call site. Recommendation below | decide | Dion | 2 | off | T1.1 |
| T2.1 | Build one segmentation service that owns the model and is the only publisher of the three mask channels. Both current call sites become clients of it | rewire | Dion | 12 | off, box | T1.12, T2.0 |
| T2.2 | Switch the glasses image stream back on, one stage at a time so failures are attributable | rewire | Dion | 6 | lab | T0.3 |
| T2.3 | Verify the gaze path and measure the error introduced by the fixed 1.5 metre depth assumption. Record the usable distance range | measure | Dion | 6 | lab | T2.2 |
| T2.4 | Decide when segmentation runs, instead of on every frame, and add an age limit so the arm never moves toward a stale position | build | Dion | 8 | off | T2.1 |
| T2.5 | Voice and gaze to grasp, on hardware. Two boxes, pick the one you looked at | measure | Dion, Sherman | 5 | lab | T1.12, T2.3, T2.4 |

**Recommendation on T2.0: option 2, retire the arm-side program.** The reasoning is that M2's
acceptance test needs gaze, and gaze disambiguation exists only in the pipeline, not in the arm-side
program. Patching the spoken word into the arm-side program buys back voice but not gaze, so we
would do the larger piece of work anyway and then delete the patch. The cost of option 2 is that it
depends on segmentation ownership being settled first, which is T2.1, so the two land together. If
M1 runs late and a quick demonstration is needed in November, option 1 is the fallback: it is small,
local and reversible. Evidence for both is `CODE_AUDIT` L1 and `NEXT_STEPS` 2.2.

### 6.5 M3. The base navigates (12 Oct – 27 Dec 2026)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T3.1 | ~~Compile the navigation workspace~~ **Done 2026-09-14**, 10 of 10 packages in 2 min 34 s, and it needed neither `xpkg_demo` nor `robot_navigation` because both are run-time dependencies. What remains for Zongzhe is to repeat it on his own machine as part of T0.5 | bring-up | Zongzhe | 1 of 4 left | box | T0.4 |
| T3.2 | ~~Run the ten navigation node tests~~ **Done 2026-09-14**, passed first run: 6 controls, 4 expected failures reproduced, 0 skipped. E1, F1 and F2 are now `[observed]`, F4 is new. Read the result before starting T3.3 | measure | Zongzhe | 0 of 5 left | box | T3.1 |
| T3.3 | Fix the missing arm-to-base transform during a mapping run, which today leaves the arm unconnected to the position tree. **Owner changed to Sherman 2026-09-20**, Zongzhe reviews the change | fix | Sherman | 2 | off | T3.2 |
| T3.4 | Drive the base under keyboard control. Confirm the LiDAR publishes. **Owner changed to Sherman 2026-09-20** | bring-up | Sherman | 4 | lab | T0.2, T3.1 |
| T3.5 | Build a map of the lab and localise in it. **Owner changed 2026-09-20:** Sherman leads, Dion joins, since he is at the robot for the camera and LiDAR calibration anyway (T5.5). **Read first (2026-09-21):** `NEXT_STEPS` §2.15 "For Sherman". Two launch files localise differently and read different map files, `navigation.launch.py` fails without `map:=`, and which one the team drives with is still open | bring-up | Sherman, Dion | 6 | lab | T3.4 |
| T3.6 | Drive to a commanded point ten times. Record the position error each time. **Owner changed to Sherman 2026-09-20** | measure | Sherman | 5 | lab | T3.5 |
| T3.7 | The navigation to arm handover on hardware: object position in, drive, arrived signal out. The channels are `CHANNEL_CONTRACT` H2, H3 and H9 | rewire | Dion, Sherman | 6 | lab | T1.12, T3.6, T3.8 |
| T3.8 | **Added 2026-09-21.** Fix the bridge-node defects the bench found: `goal_reached_publisher` has three silent-failure paths, so a second object after any navigation failure gets no goal (`CODE_AUDIT` F1), and all five nav nodes crash with a traceback on Ctrl+C (F4). Both `[observed]` by `bench/nav_nodes.sh`. The return-leg defects E1 and F2 stay with stretch goal S5 | fix | Zongzhe | 6 | off | T3.2 |

### 6.6 M4. The current system, closed loop (28 Dec 2026 – 17 Jan 2027)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T4.1 | One complete run, recorded on video: speak, look, drive, grasp | measure | All | 8 | lab | T2.5, T3.7 |
| T4.2 | Measure how long each stage takes. Report the 99th percentile, not the average. **Owner changed to Sherman 2026-09-20** | measure | Sherman | 6 | lab | T4.1 |
| T4.3 | Keep the defect log from the first powered session onward. One line per bug: symptom, guess, actual cause | measure | All | ongoing | off | T1.6 |

### 6.7 M5. The base has a calibrated forward camera (5 Oct 2026 – 17 Jan 2027)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T5.1 | ~~Camera secured. Found in the lab, or ordered with a date~~ **Done 2026-09-16.** An Intel RealSense D455 is provided to the project. USB 3 connection and live RGB-D stream verification remain T0.1 | decide | Sherman | 2 | lab | T0.1 |
| T5.2 | ~~Design the mount. Forward facing, rigid, clear of the arm's swept volume, not looking at the robot's own body. The arm is mounted facing backward, which makes this a real constraint rather than a formality~~ **Done 2026-09-16 `[reported]`.** Sherman completed the forward-facing D455 mount CAD and measurements: `20 x 20 mm` aluminum extrusion, `190 mm` required length. Physical fabrication and fit verification remain T5.3 | build | Sherman | 10 | off | T5.1 |
| T5.3 | Fabricate, fit, and verify the mount's rigidity, arm clearance, cable route, and camera view | build | Sherman | 8 | lab | T5.2 |
| T5.4 | Measure the mount geometry and make it one source of truth. Today the same 0.18 metre offset is written in three independent places and the robot model carries a fourth | fix | Sherman, Zongzhe | 5 | off, lab | T5.3 |
| T5.5 | Calibrate the position of the camera relative to the LiDAR. Dion owns the procedure and the numbers, Sherman owns the rig and the target | measure | Dion, Sherman | 12 | lab | T5.3 |
| T5.6 | Verify the calibration by projecting LiDAR points into the camera image. Keep the picture, it goes in the paper | measure | Dion | 4 | box | T5.5 |
| T5.7 | Choose where camera poses come from and characterise the error: drift over a run, and the duplicate-object rate it causes in the graph. Start with the existing 2D localisation because it is free. This is a measurement study, not a configuration choice | measure | Dion | 12 | box | T3.5, T5.6 |
| T5.8 | Build a trial fixture: marked object positions and marked robot start positions, so a trial can be repeated exactly | build | Sherman | 8 | lab | T5.3 |
| T5.9 | **Added 2026-09-20 (decision D4).** The escalation half of the pose-source study: if T5.7 says 2D localisation is the limiting factor, bring up FAST-LIVO2 and measure it against the same drift and duplicate-object metrics. Staged deliberately: do not start it before T5.7 has a number. The known blocker is a time-synchronised camera, so the first hour is spent on sensor synchronisation, not on the algorithm. Sherman owns the hardware, the recording and the evaluation runs; pair with Zongzhe for the software bring-up | measure | Sherman | 24 | box, lab | T5.7 |

### 6.8 M6. The memory graph, offline (28 Dec 2026 – 7 Feb 2027)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T6.1 | Read the upstream HiCo-Nav code. Settle which solvers it needs and whether their licences are acceptable | decide | Zongzhe | 4 | off | none |
| T6.2 | Record data of the lab with the base camera: images, depth, LiDAR, positions | measure | Sherman | 4 | lab | T5.6 |
| T6.3 | Build object entries from recorded data: mask, depth, camera position, image feature | build | Zongzhe | 14 | off | T6.2 |
| T6.4 | The merge test, so the same physical object seen twice becomes one entry: 3D overlap combined with image feature similarity | build | Zongzhe | 10 | off | T6.3 |
| T6.5 | The two-stage trigger. A cheap detector runs always, the expensive one runs only when a new object class appears or the robot has moved enough. This also closes the "when should segmentation run" question from M2 | build | Zongzhe | 8 | off | T2.4, T6.3 |
| T6.6 | Decide the reasoning model endpoint, cloud or local, and check whether sending lab images off site is permitted. A procurement and policy question of the same kind as T0.1 | decide | Sherman | 4 | off | none |
| T6.7 | The reasoning layer. Called once at the start of a task, off the control loop, expanding the instruction into related objects | build | Zongzhe | 10 | off | T6.4, T6.6 |
| T6.8 | Query the graph with a sentence and get an object position back | build | Zongzhe, Dion | 8 | off | T6.4 |

### 6.9 M7. The graph drives the robot (1–28 Feb 2027)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T7.1 | Publish the approach goal from the graph instead of from live perception. The channel and its meaning do not change, only who writes to it. **Write this node in C++ with rclcpp**, not Python. `object_approach_node.py` is a working reference for the same behaviour, so you can diff against it and know when the C++ one is right | build | Dion | 16 | box | T3.7, T6.8 |
| T7.2 | Build the graph while the robot drives, rather than from a recording | build | Zongzhe | 10 | lab | T5.7, T7.1 |
| T7.3 | Spoken instruction to arrival at the right object, on hardware, with the object not in view when the instruction is given | measure | All | 8 | lab | T7.2 |

### 6.10 M8. Gaze picks the instance (8 Feb – 14 Mar 2027). Protected

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T8.1 | Produce an image feature from the gaze-cropped region of the glasses frame | build | Dion | 8 | off | T2.3 |
| T8.2 | Carry that feature into the graph query so it selects an instance rather than a class | build | Dion | 10 | off | T6.8, T8.1 |
| T8.3 | Run the ablation. N trials with the feature and N without, same objects, same start positions, using the fixture | measure | Dion, Sherman | 18 | lab | T5.8, T7.3, T8.2 |
| T8.4 | Re-measure the cross-camera matching baseline so the comparison number is ours rather than remembered | measure | Dion | 4 | box | T2.1 |

### 6.11 M9. Frontier scoring and visit ordering (2 Nov 2026 – 21 Feb 2027). Optional

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T9.1 | Get the upstream simulator evaluation running as a baseline | bring-up | Zongzhe | 8 | off | T6.1 |
| T9.2 | Implement frontier scoring | build | Zongzhe | 12 | off | T9.1 |
| T9.3 | Implement visit ordering with an openly licensed solver | build | Zongzhe | 10 | off | T9.2 |
| T9.4 | A node that emits drive goals, sitting beside the existing bridge, with Nav2 unchanged | build | Zongzhe, Dion | 8 | box | T9.3 |

### 6.12 M10. Demonstration and paper (1–21 Mar 2027)

| ID | Task | Type | Owner | Hours | Where | After |
|---|---|---|---|---|---|---|
| T10.1 | Full demonstration run, recorded | measure | All | 8 | lab | T8.3 |
| T10.2 | Paper draft. The central table is T8.3's ablation | decide | All | 24 | off | T8.3 |
| T10.3 | Reproducibility artifacts: the bench, the recorded data, this plan, the defect log | decide | Dion | 6 | off | T10.2 |

### 6.13 The critical path

The longest chain of dependent tasks from today to the claim:

```
T0.3 -> T0.4 -> T3.1 -> T3.2 -> T3.5 -> T5.7 -> T7.2 -> T7.3 -> T8.3 -> T10.2
```

and the second chain, which is the one that runs through Dion:

```
T1.1 -> T1.8 -> T1.9 -> T1.11 -> T1.12 -> T2.1 -> T2.4 -> T2.5 -> T3.7 -> T7.1 -> T8.2 -> T8.3
```

Twelve tasks, almost all of them Dion's, now that T0.7 is done. That is the schedule risk in one
line. Anything that can be moved off that chain should be, which is why T6.5 and T6.6 moved earlier
and why T4.2 moved on 2026-09-20. T0.10 and T0.11 stay with Dion by his own call: he wrote the
bench, so they go faster with him even though they sit beside the chain. T7.1 stays on the chain and is written in C++ on
purpose.

**Load after the 2026-09-20 rebalance**, counting open hours against the weekly hours in the
"Effort available" note at the top and roughly 21 working weeks left:

| Person | Open hours | Hours a week | Weeks needed |
|---|---|---|---|
| Dion | about 210 | 12 | 17 to 18 |
| Zongzhe | about 130 | 8 to 10 | 13 to 16 |
| Sherman | about 139 | 8 to 10 | 14 to 17 |

Dion is still the heaviest and still sits on the whole critical chain. What moved was work beside
the chain, not on it, because nobody else can pick up the arm and perception repairs faster than
they can learn them.

---

## 7. Assignment and load

### 7.1 What each person owns

Each entry says what the person is accountable for, what they get out of it, why the work suits
them, and what is open enough to be worth digging into. Task-level ownership is in section 6.

**Dion. Perception, the arm, and the research claim.**

Owns everything between a camera frame and the arm closing on an object, plus the contribution
itself. That means arm bring-up through to a working grasp, one segmentation service instead of two
competing ones, the glasses stream reaching the arm, the calibration of the base camera and what its
accuracy costs, and the gaze-conditioned query that M8 measures.

*Takeaway.* An end-to-end perception system on real hardware, from raw frames to an executed motion,
and a measured result with an ablation table behind it. Production ROS 2 in both Python and C++,
since T7.1 is written with rclcpp against a working Python reference.

*Why it fits.* This is the most vision-heavy and the most systems-heavy stream in the project. Most
of it is repair rather than authorship, and the skill it rewards is reading an unfamiliar system
accurately enough to find the five lines that matter.

*Worth exploring.* Image embeddings. Nothing in this repository computes one today, so the feature
extractor is genuinely new code, and both the memory graph and the gaze crop consume it. Owning it
means the interface between perception and the graph is a deliverable rather than a conversation.

**Zongzhe. The memory graph and the reasoning layer.**

*Revised 2026-09-20.* Navigation bring-up moved to Sherman. What stays here is the software half of
navigation: the bridge nodes (`object_approach_node.py`, `goal_reached_publisher.py`), the node that
emits drive goals, and everything above the goal. CI and the per-subsystem bench, T0.10 and T0.11,
were briefly moved here and then kept with Dion, who wrote the bench.

Owns the one part of this project that does not already exist in some form: object entries built
from images, depth and camera pose; the merge rule that stops one physical object being registered
twice; the sentence query that returns a place to drive to; and, if the schedule allows, the frontier
scoring and visit ordering in M9.

*Takeaway.* A published method taken from the paper to working, evaluated code, with the design
decisions owned rather than inherited. This is the most paper-shaped work on the board and the part a
reader of the write-up will ask about first.

*Why it fits.* Well-posed problems with a right answer, most of them geometric or statistical, and
the core of it runs on a laptop against recorded data. Progress does not depend on the robot being
free, the lab being open, or anyone else finishing first.

*Worth exploring.* The merge rule itself, which is 3D overlap combined with embedding similarity and
a threshold nobody has tuned for this room. It is the decision the graph's correctness turns on and
it is directly measurable. The reasoning layer is the other one, and it is the only place in the
project with real research risk, because no model in this repository has ever been given an image.

**Sherman. The platform, and where its poses come from.**

*Revised 2026-09-20.* This now includes navigation bring-up outright (T3.3 to T3.6), the Nav2 and
SLAM configuration, the static transforms, and the FAST-LIVO2 escalation in T5.9. The rule is that
Sherman owns everything that gets the robot to a commanded point, and Zongzhe owns what decides
which point. Sherman also owns the lab session itself: the agenda, the setup, the recording and
running the trials, whoever else is in the room.

Owns the robot as a working machine: it powers on, it drives, it maps, it localises, it answers on
the network, and a runbook exists that says how. Owns the physical build the rest depends on, meaning
the forward camera mount, the calibration rig and target, and the trial fixture that makes M8's runs
repeatable. Owns the open question of which pose source the memory graph needs, and the measurement
that answers it.

*Takeaway.* SLAM and localisation on real hardware, ending in a comparison with a number attached
rather than a preference. Plus a mechanical design that is genuinely on the critical path rather than
a bracket bolted on at the end.

*Why it fits.* Bring-up rewards resourcefulness with unfamiliar tooling far more than it rewards
knowing the internals first, and most of what stands between this repository and a running robot is
retrieval and assembly rather than development. The mount is a real design problem, because the arm
is mounted facing backward and its swept volume constrains where a forward camera can sit.

*Worth exploring.* The pose-source question is open and nobody has the answer. Start with the 2D
localisation already running, because it is free, and escalate only if the measurement says to. Two
findings make this more interesting than it looks. The LiDAR's own inertial sensor is already
publishing on `livox/imu` and nothing subscribes to it `[code]`, and the vendored OpenVINS copy is
calibrated for the glasses rather than for a base camera `[code]`, so neither of the two obvious
shortcuts is quite the shortcut it appears to be. The failure mode is visible as duplicated objects
in the graph, which makes this a study with a result rather than a configuration choice.

### 7.2 What each person is expected to put in

| Person | Hours a week |
|---|---|
| Dion | about 12 |
| Zongzhe | 8 to 10 |
| Sherman | 8 to 10 |

That is about 30 person-hours a week, and about 620 over the 31 calendar weeks once the recess, the
exam period, the winter break and travel are taken out (5.3 has the working-week count). The named
work in section 6 comes to roughly 406 hours, so the plan runs at about 65 percent of capacity.
Sherman's share carries more slack than the task list suggests, because the travel and the lab
session overhead land on him and none of the estimates capture them.

### 7.3 Working agreements

1. **Hardware sessions are booked and have a written agenda.** Travel is 20 minutes each way, so a
   session with no agenda costs an hour before anything starts. Write the agenda in your own
   `docs/<name>_docs/` folder the day before.
2. **Run the bench before and after any change that moves code.** It takes a second and it catches
   renamed channels, which is the failure mode this project has already suffered twice.
3. **Two people can use the lab workstation at once** as long as each uses a different private
   message channel. The bench scripts refuse to start if the channel is not empty, which is the
   check that keeps you from reaching real hardware by accident.
4. **The defect log is one shared file**, one line per bug, from the first powered session onward.
   It is the raw material for the paper's discussion section and it costs nothing to keep.
5. **Nobody edits anybody else's `docs/<name>_docs/` folder.** Corrections go in your own folder with
   a citation, and you tell the owner.
6. **Robot code changes go on a branch for review.** Bench and documentation changes go straight to
   the main branch.

---

## 8. Risks and what we drop first

### 8.1 The cut list, in order

If the schedule slips, cut from the top of this list. Decided in advance so it is not an argument in
March, with the final report due.

| Order | What we cut | What we lose | What survives |
|---|---|---|---|
| 1 | **M9 entirely**, frontier scoring and visit ordering | The paper's largest reported benefit, which is not ours anyway | Everything. M9 is not on the path to the claim |
| 2 | The reasoning layer, T6.7 | Instruction expansion into related objects | Direct sentence query of the graph, which is what M8 needs |
| 3 | Graph pruning and the solver work | The graph grows without bound over a long run | Correctness over a lab-sized run |
| 4 | The two-stage trigger, T6.5 | Speed | Correctness, provided the age limit from T2.4 stays |
| 5 | Live graph building, T7.2 | The robot builds its map of objects as it goes | A graph built from a recorded drive of the same room, which still supports the ablation |
| 6 | Reduce N in the ablation, T8.3 | Statistical strength | A number, which is better than no number |

**M8 is never cut.** If M8 cannot run, the project has no result, and at that point the right move is
to tell the supervisor early rather than late.

### 8.2 Named risks

| Risk | Likelihood | Effect | What we do about it |
|---|---|---|---|
| The first powered arm sessions take far longer than estimated. The arm has never moved | High | M1 slips past 1 Nov and collides with the November exam period, which is no-work time regardless of how the team is running | Three short sessions rather than one long one. M3 runs in parallel and is not blocked by it |
| The camera is not in the lab and procurement takes weeks | Medium | M5 slips, M6 loses its input | Confirm in week 1. The wrist-camera fallback below is no longer safe to assume |
| **The wrist D435i is faulty and may not survive a replug** `[observed]` 2026-09-14 | **Certain that it is faulty. Unknown whether it recovers** | T1.12 has no live mask, T6.2 has no recorded frames, and the M5 fallback of parking the arm is gone, so a single camera fault removes both camera paths at once | Replug it and re-run `python3 bench/preflight.py -g net` before booking any session that needs it. Settle D8 in week 1 and buy alongside the D455 if it is dead, since one order beats two |
| Camera position accuracy from 2D localisation is too poor and the graph registers duplicates | Medium | M6 quality drops | The duplication rate is directly measurable. Measure it in T5.7 before building on it |
| The reasoning model does not fit in graphics memory alongside the segmentation model | Medium | T6.7 blocked | Cut item 2 on the list above, or use a cloud endpoint if the imagery policy permits |
| Dion is the contention point on thirteen consecutive tasks | High | Everything | T0.7 in week 1. Navigation handed to Zongzhe outright. Sherman runs the trials |
| The lab workstation is shared, throttled and nearly full | Certain | Builds take four times as long, disk runs out | Check free space before large builds. Raise the cooling and power profile with whoever maintains the machine |

### 8.3 Two things the record says to expect

From this project's own history, worth stating rather than rediscovering.

**Bring-up work has doubled every time so far.** The navigation workspace needed two packages nobody
had, a manifest that is generated rather than committed, and a build flag combination not written in
any document. Treat any hardware estimate here as a lower bound.

**Renames fail silently.** ROS matches channel and frame names as plain text at run time, so a rename
applied to four of five places compiles, launches and quietly does nothing. This has already produced
two defects in this repository. Run the bench.

---

## 9. Tracking the work in Linear

**Recommendation: yes, use it, with this plan as the source of truth and Linear as the working
surface.** The plan holds the reasoning and the dependencies. Linear holds state, assignment and what
moved this week. The two stay in step because the task identifiers are the same in both.

Suggested structure.

| Linear concept | What we put in it |
|---|---|
| Team | One team, "Gappler" |
| Project | One project per milestone, M0 to M10, with the milestone's "done means" as the project description and the end-of-week date as the target |
| Issue | One issue per task node, titled with its identifier, for example `T1.8 Fix the three interlocking grasp path defects` |
| Sub-issue | The steps inside a task, added by the owner when they start it, not planned in advance |
| Blocking relation | Copy the "after" column exactly. This is what makes the dependency view match the tree in section 6 |
| Labels | `owner:dion`, `owner:zongzhe`, `owner:sherman`, and `where:off`, `where:box`, `where:lab`, and `stream:arm`, `stream:nav`, `stream:hardware` |
| Estimate | The hours column, so the load in section 7.2 stays visible as things change |
| Cycle | Two weeks, matching the milestone boundaries |

**To create this, the Linear connector has to be authenticated in this session first.** It is
available but not connected. Once it is, the whole structure above can be created from this file in
one pass, and kept in step afterwards.

---

## 10. Future work

Beyond this plan, in the order they would become worth doing.

1. The return-to-user leg, which needs the pose fusion node rewritten to match its own documentation,
   the marker path restored, and the frame disagreement settled.
2. Naming everything descriptively across the repository, in one deliberate pass, with the frame
   renames last and done with somebody at the robot.
3. One configuration tree, with channel names declared as parameters rather than as constants so they
   stay overridable at launch.
4. Replaying recorded data as a regression test.
5. The paper's motion layer, only if Nav2's controller proves inadequate around moving obstacles.
6. Better localisation, only if the duplication rate measured in T5.7 says the current one is the
   limiting factor.

**CI moved out of this list on 2026-09-16** — see §4.3: it is now `T0.10`, gated on `T0.5` rather
than on the rest of the plan.

---

## 11. What we already know does not work

Recorded so nobody spends time on it twice. All of this is from the existing documents.

- **Building from inside one workspace.** Produces a partial overlay that fails at run time in
  confusing ways. Build from the repository root.
- **Setting `PYTHONNOUSERSITE=1`, or tidying up `~/.local`.** It breaks the graphics-capable PyTorch.
- **The robot configuration's own simulated-arm launch.** It has been unable to start since March
  because the block that adds fake hardware is commented out. The bench carries its own simulated arm
  instead.
- **Copying the existing built overlays between accounts.** They contain absolute paths to a home
  directory that the current account cannot read. Rebuild instead.
- **Treating the two-dimensional centroid message as a normal 3D point.** Its first two numbers are
  pixel coordinates and the third is depth in metres.
- **Assuming the branch `realman_manip` holds newer arm code.** It does not. Take its documents, its
  environment script and its calibration file, and none of its code.
- **Expecting the paper's timing numbers to transfer.** They were measured on an RTX 5090. Our
  workstation has a 4060 Ti and it is currently thermally throttled.

---

## 12. Stretch goals

Section 8 says what we cut if we run late. This says what we pick up if we run early, so that the
answer is decided in advance either way. These are ordered by how much they add to the result, not by
how hard they are.

Nothing here is promised to anyone. None of it is a dependency of M8. If you find yourself ahead,
take from the top of this list, and say so in the weekly note so the others know where you went.

| # | Stretch goal | Owner | Why it is worth doing | What it needs first |
|---|---|---|---|---|
| S1 | **Candidate-based grasping instead of the simple path** | Dion | `grasp_state_machine.cpp:41` sets `USE_SIMPLE_EXECUTE = true`, which routes every grasp through one Cartesian step and a gripper close. The real path, with the candidate queue, the stability window and orientation interpolation, is about 150 lines of written but never-executed code in the same file `[code]`. Turning it on is the difference between a demonstration and a grasp policy | M1 complete, and the concurrency fixes in T1.9 landed first, because this path is what makes them reachable |
| S2 | **The reasoning layer, if it was cut** | Zongzhe | Cut item 2 in section 8. It is what turns "find the mug" into "look near the sink as well", and it is the piece a reviewer will expect from a paper that claims a memory graph | M6 through T6.4, plus the endpoint decision in T6.6 |
| S3 | **Graph pruning with a real solver** | Zongzhe | Cut item 3. Bounded graph growth over a long run. A weighted set multicover problem with mature open solvers, so it is a known quantity rather than a research question | T6.4, and a licence check on the solver |
| S4 | **A second pose source, measured against the first** | Sherman | If T5.7 says 2D localisation is the limiting factor, this stops being a stretch goal and becomes required work. Either way the comparison is a paper section. The LiDAR's inertial sensor already publishes on `livox/imu` with no subscriber `[code]`, so the input exists | T5.7, and the duplicate-object rate measured on the existing source first |
| S5 | **The return-to-user leg** | Dion | Out of scope in section 4.2, but `goto_glasses.py` has to be corrected regardless, because its outbound half fires on the same spoken command as the forward leg and competes for the same Nav2 action server `[code]`. Once that is fixed the return leg is closer than the scope decision assumes | The frame defect fixed, and the pose fusion node reconciled with its own documentation |
| S6 | **Frontier scoring and visit ordering, if M9 was cut** | Zongzhe | Cut item 1. The largest reported benefit in the paper. It is not ours and it is not on the path to our claim, which is why it was cut, but it is the most complete second result available | M6 done, and the upstream evaluation running as a baseline |
| S7 | **Replay a recording as a regression test** | Dion | The bench catches renamed channels but nothing catches a perception regression. A recorded drive replayed through the graph would. It is also the cheapest way to make the results reproducible by someone else | A recorded run from T6.2 |
| S9 | **Pick the gazed object by geometry** | Dion | Two identical objects defeat appearance matching. Casting the gaze ray in the robot's frame does not care what the objects look like. Three methods, cheapest first: map the gaze point by the whole-scene matches, then solve the glasses pose from the shared scene against robot depth, then full pose fusion. Could become part of M8's claim, per D9 | An identical pair included in T2.5, so the failure of today's method is measured first. `NEXT_STEPS` §2.13 |
| S8 | **One configuration tree** | anyone with a spare week | Channel names declared as parameters rather than constants, so they stay overridable at launch. Today 38 of 54 owned channel names are declared outside `shared/global_config.yaml` `[code]` `CODE_AUDIT` K1 | The naming pass, and `TESTBENCH_PLAN` C1 fixed so the bench can still read them |

**How to use this list.** If a milestone lands early, the default is not to start the next one early.
It is to take the top item here that your own stream unblocks. That keeps the slack where the
schedule can still absorb it, and it means an early finish produces something rather than evaporating.

---

## 13. Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-13 | Claude (Opus 5) + Dion | Created. Milestone spine M0 to M10, task tree with 67 nodes and their dependencies, three-way split validated against the constraints, scope written down with reasons for what is out, cut list decided in advance, Linear structure proposed. |
| 2026-09-13 | Claude (Opus 5) + Dion | Dion's revisions: T7.1 written in C++ with rclcpp, T5.5 to T5.7 reframed as Dion's calibration and localisation-error workstream rather than mount support, and T6.5 and T6.6 handed to Zongzhe and Sherman. Per-person hour totals replaced by a weekly expectation. Removed the skill labels on individual people, since nobody here has deep ROS 2 experience yet and T0.6 now covers all three. |
| 2026-09-13 | Claude (Opus 5) + Dion | Checked this file against the published map. Corrected two stale counts: the audit now holds 49 findings, not 45 (`CODE_AUDIT` changelog, after L1), and the task tree has 67 nodes, not 60. The map at the artifact link was already current and needed no republish. |
| 2026-09-13 | Claude (Opus 5) + Dion | Republished the task tree map under Dion's own account, so its link is `.../65c7784d-...` and the old `.../72753a73-...` one is dead. The page content did not change. |
| 2026-09-14 | Claude (Opus 5) + Dion | Rewrote 7.1 as what each person owns, takes away, why it fits and what is worth exploring, replacing the reasoning about how the split was arrived at. Added section 12, stretch goals, as the counterpart to the cut list. Changelog renumbered to 13. |
| 2026-09-14 | Claude (Opus 5) + Dion | Added a work type to all 67 tasks (`build`, `fix`, `rewire`, `bring-up`, `measure`, `decide`) as a new column in section 6 and a new 6.1b explaining it. The map carries the same types as a chip, the right-hand edge colour of each node, a filter axis and a proportion bar. Counts: 16 build, 6 fix, 3 rewire, 12 bring-up, 18 measure, 12 decide. |
| 2026-09-14 | Claude (Opus 5) + Dion | **Added T0.0, the `realman_manip` cherry-pick, as the first task in M0 and the first thing to do.** Checked the branch rather than trusting the earlier audit: exactly 15 files exist there and not on `main`, the four already scoped in `NEXT_STEPS` §3.3 plus `anygrasp_node.sh`, which is new to this list and records that the verified session ran `checkpoint_tracking.tar` while `main` launches `checkpoint_detection.tar`. Ten of the fifteen are pre-reorg duplicates. Task count 67 to 68, `bring-up` 12 to 13. |
| 2026-09-14 | Claude (Opus 5) + Dion | **Folded the 2026-09-14 bench results in as §2.6, and corrected the current-state tables against them.** The navigation workspace compiles (10/10, no Livox blocker, the SDK was already installed), the five nav nodes pass the bench first run, E1/F1/F2 are now `[observed]` and F4 is new, so the audit holds 51 findings. T0.8, T3.1 and T3.2 marked done, M3's risk lowered. The wrist D435i is faulty and off the USB bus: recorded as a new risk, a new open decision D8, and a row in §2.2, because it removes both the live-mask path in T1.12 and the parked-arm fallback for M5 and T6.2 at the same time. |
| 2026-09-14 | Claude (Opus 5) + Dion | Added §2.5 recording four read-only code checks: navigation is retrieval not development, the arm and perception work is repair at 100 to 150 lines, the glasses gaze and image producers are complete and only the consumer is missing, segmentation already shares its model, the memory graph is genuinely from scratch, the Livox IMU already publishes, and the vendored OpenVINS is calibrated for the glasses. New defect recorded as `CODE_AUDIT` E5. |
| 2026-09-16 | Claude (Sonnet 5) + Dion | Replaced the 20-week internal schedule with the real academic calendar: the four fixed capstone deadlines (plan/Gantt due 2026-10-05, interim presentation 2026-11-10 to 2026-11-13, final report due 2027-03-28, oral presentation 2027-04-05 to 2027-04-16), the end-of-September recess, the November exam period plus early December, and the winter break split into two off weeks and two half-speed buffer weeks. The same 20 weeks of work now spans 31 calendar weeks to 2027-04-18, which raised available capacity from about 515 to about 620 hours and dropped named work from 79 to about 65 percent of it. Milestone dates in §5.1 and the §6 section headers, the checkpoints in §5.2, and the Gantt in §5.3 were all recomputed; task hours, ownership and dependencies are unchanged. |
| 2026-09-16 | Claude (Sonnet 5) + Dion | This file moved from `docs/dion_docs/PROJECT_PLAN.md` to `docs/PROJECT_PLAN.md` as part of moving all global docs out of the per-person folder (see `docs/START_HERE.md` and `CLAUDE.md`). Content unchanged by the move; all in-repo links updated. |
| 2026-09-16 | Claude (Sonnet 5) + Dion | Added `T0.10`, a CI task, to the M0 table in §6.2: wire up `./bench/run.sh` on every push, gated on `T0.5` rather than left as an after-the-plan idea. Moved "a continuous integration job" out of §4.3 (deferred) and §10 (future work) accordingly. Task count 68 to 69, `build` 16 to 17; counts and the "sixteen of sixty-eight" sentence in §6.1b updated to match, and the new task added to `next-steps-map.html`'s data with the same DONE-prefix convention. Full reasoning and scope in `NEXT_STEPS.md` §2.12. |
| 2026-09-16 | OpenCode (GPT-5.6 Terra) + Sherman | Updated task evidence from the lab session. T0.2 is done: switch wiring and a persistent `.100`/`.10`/`.5` profile let RM65 and MID-360 reply from their required host addresses after a connection cycle. T0.9 is done for the manufacturer ECHO-PLUS chassis: its manual gives a `265 mm` stated rotation radius, so the `200 mm` Nav2 radius is not conservative; the fitted-robot footprint remains a T5.3/T5.4 check. An Intel RealSense D455 is provided but untested, so T5.1 is done while T0.1 retains USB 3 and live-stream verification. T5.2 mount CAD and measurements are reported complete; fabrication and fit remain T5.3. |
| 2026-09-19 | Claude (Opus 5) + Dion | T0.0 progress. `calibration.json` taken, as `src/services/aria_device/calibration/aria_factory_calibration.json`: it is the only calibration source when testing without the glasses. `env.sh` and `anygrasp_node.sh` held until a box check, listed at the top of `TESTBENCH_PLAN` "Start here". Found that the two AnyGrasp nodes differ in method (tracker vs detector), not only in checkpoint. Per-file decisions in `NEXT_STEPS` §3.3. |
| 2026-09-19 | Claude (Opus 5) + Dion | T0.0: startup guide archived to `docs/archive/` with citations repointed, `SETUP.md` skipped. Only the two held files remain. |
| 2026-09-19 | Claude (Opus 5) + Dion | Added open decision D9 and stretch goal S9: pick the gazed object by geometry, so two identical objects can be told apart. Exploration only. No task, hour or dependency changed. Detail in `NEXT_STEPS` §2.13. |
| 2026-09-19 | Claude (Opus 5) + Dion | T0.10 progress: `.github/workflows/bench.yml` added, running Tiers 0-1 strictly on PRs into and pushes to `main`, started before T0.5 on purpose. Added `T0.11`, one test suite per subsystem so CI runs only what a PR touched. Task count 69 to 70, `build` 17 to 18, §6.1b counts updated. |
| 2026-09-19 | Claude (Opus 5) + Dion | T0.4 now also covers the `mtc_sim_test` executable decision, and its done condition turns on branch protection so the bench blocks merges into `main`. T0.11 gained the Monday and Wednesday night full-suite run and the open lab-box-runner-or-Docker question, deferred to that task. |
| 2026-09-19 | Claude (Opus 5) + Dion | Bench levels renamed L0-L5 (`bench/README.md`). T0.11: runner decided (self-hosted on the lab box, L0-L4 only), plus the `dev`/`main` skip rules. |
| 2026-09-19 | Claude (Opus 5) + Dion | T0.3 marked DONE, and in `next-steps-map.html`'s task data. |
| 2026-09-20 | Claude (Opus 5) + Dion | **T0.7 done: [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md) is the single source for channel ownership**, and §3.5 points to it. Streams renamed to kinds of work: arm and perception, algorithms and graph, platform and experiments. Navigation split at the goal: Sherman owns motion and sensing (T3.3 to T3.6, Nav2 and SLAM config, the static transforms, the pose source), Zongzhe owns goals and algorithms. New T5.9, the FAST-LIVO2 escalation, from decision D4. T4.2 to Sherman, off Dion's chain. T0.10 and T0.11 stay with Dion, who wrote the bench. T3.5 gains Dion, since he is at the robot for T5.5 anyway. D1, D2, D4, D5, D8 and D9 answered. |
| 2026-09-21 | Claude (Opus 5) + Dion | **T0.0 done.** Box checks passed for the calibration file and `env.sh`, so `env.sh` and `anygrasp_node.sh` are taken. The glasses serial check is still owed. `next-steps-map.html` task data updated with the DONE prefix. |
| 2026-09-21 | Claude (Opus 5) + Dion | **T0.4 done**, by Dion at his request, ahead of Zongzhe. Both nav packages in the repo, the Livox manifest in its package, the orphan `mtc_sim_test` launch file deleted (building its source would add a second program that moves the arm). The saved map stays out of git, per T0.3. L0-L2 green locally. Branch protection is Dion's last step once CI is green on the PR. |
| 2026-09-21 | Claude (Opus 5) + Dion | T0.11: L5 is now the robot check, L6 the hardware. Neither runs on the CI runner or gates a merge. Map text updated to match. |
| 2026-09-21 | Claude (Opus 5) + Dion | Every open bench finding is now a task, so TESTBENCH_PLAN holds no work items. New **T0.12** (was W6, AnyGrasp replay) and **T3.8** (nav bridge fixes F1, F4, before T3.7). B4 folded into T1.3, C7 into T1.9, `conda run` into T1.10. **T1.2 progress:** `estop.py` fixed (B2, B2a, B2c). Task tree updated to match and republished. |
| 2026-09-21 | Claude (Opus 5) + Dion | **T0.10 done.** `bench` on `main` and `dev`, both protected, `dev` the default branch. T0.11 progress: branch step done, runner and no-skips job left. `next-steps-map.html` task data updated. |
| 2026-09-21 | Claude (Opus 5) + Dion | §4.2: the full reorg moved into scope. Spec in `NEXT_STEPS` §2.15. No new task ID: it rides with T0.11, whose suites follow the folder layout. |
| 2026-09-21 | Claude (Opus 5) + Dion | T3.5 points to the nav map findings in `NEXT_STEPS` §2.15 "For Sherman". `next-steps-map.html` task data updated to match, republish owed (the refactor is still going). |
| 2026-09-21 | Claude (Opus 5) + Dion | `shared/config.yaml` renamed to `shared/global_config.yaml` in the two current mentions (reorg step 2). The gaze topic's line cite corrected to `:13`. |
