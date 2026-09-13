# PROJECT PLAN: milestones, task tree and who does what

**What this is.** The layer above [`NEXT_STEPS.md`](NEXT_STEPS.md). `NEXT_STEPS` is a register of
everything we could do. This file decides what we *will* do, in what order, by when, and who owns
each piece. It also answers one question Dion raised directly: can three people work on this at the
same time without blocking each other.

**Who this is for.** Dion, Zongzhe and Sherman. Written so a reader who has never used ROS 2 can
follow it. Where a term is needed, it is explained on first use.

**Horizon.** 20 weeks, week 1 starting Monday 2026-09-14, week 20 ending Sunday 2027-01-31.
A working demonstration is expected at the end, and a checkpoint demonstration at the end of week 12
(2026-12-06). The goal of the whole effort is a published result, so the plan protects the one
milestone that carries a research claim and treats several other milestones as droppable.

**Effort available.** Dion about 12 hours a week, Sherman 8 to 10, Zongzhe 8 to 10. Call it 30
person-hours a week, about 570 after two reduced weeks over the December holidays, about 515 after
travel and meetings. Named work in this plan comes to roughly 406 hours excluding the optional
milestone. That is 79 percent of capacity, which for a project with this much unknown bring-up is
full. Section 8 says what we drop first.

**The visual version** of this plan is [`next-steps-map.html`](next-steps-map.html), published at
<https://claude.ai/code/artifact/72753a73-2ffc-4bb7-acfb-75ab297bed17>. It carries the milestone
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
| The regression bench catches renamed channels, frames and parameters | `bench/` tiers 0 to 3 |

### 2.2 What does not work today

| Thing | Consequence | Source |
|---|---|---|
| Nothing runs from a fresh clone | No second machine, no second person | `NEXT_STEPS` 2.5 |
| The grasp path cannot produce a grasp as written, for three interlocking reasons | The arm cannot pick anything up under its own perception | `CODE_AUDIT` A |
| The navigation workspace has never been compiled | Navigation is at zero | `ORIENTATION` 3 |
| Four things the robot needs are in nobody's repository | The navigation launch fails at run time | `NEXT_STEPS` 2.9 |
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
the configuration tree, the vendor and owned-code separation, most of the 45 audit findings, the
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

After M0, these three run in parallel and touch each other only at named handover points.

| Stream | Owner | What it covers | Where the work happens | Hands over at |
|---|---|---|---|---|
| **Arm and perception** | Dion | Arm bring-up, the grasp path defects, one segmentation service, gaze, the calibration and localisation-error study, the contribution | Lab plus the box | The approach-goal channel, and the arrived signal |
| **Navigation and algorithms** | Zongzhe | Navigation build and bring-up, mapping, the memory graph, the segmentation trigger, goal ordering | Laptop and the box, lab for mapping only | The approach-goal channel, and the drive-here channel |
| **Hardware and experiments** | Sherman | Network, camera mount, the calibration rig and target, physical measurements, the bring-up runbook, trial fixtures, running trials, the procurement and policy decisions | Lab | Measured geometry, recorded data, trial results |

The handover points are three channel names and one measurement. That is a small enough interface
for three people to agree on in an hour and then not talk about for a month.

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
| The full repository reorganisation into one folder per node | Referenced in four documents and specified in none. Do the vendor separation only, as part of M0, and leave the rest | `NEXT_STEPS` 2.11 |
| The Habitat simulator baseline | Only needed to evaluate goal ordering, which is the optional milestone | Paper review 5.6 |

### 4.3 Deferred, meaning wanted but after week 20

Naming things descriptively across the whole repository, the full configuration tree, replaying
recorded data as a regression test, and a continuous integration job.

---

## 5. Milestones

### 5.1 The spine

Eleven milestones. M0 is a tax. M1 to M4 make the system we already have work. M5 to M7 are the
integration. M8 is the claim. M9 is optional. M10 is the write-up.

| # | Milestone | Done means | Weeks | Lead | Priority |
|---|---|---|---|---|---|
| **M0** | Everyone can build and run | Two people who are not Dion have cloned the repository on their own machine, built it, run the bench and got the same result. The arm and the LiDAR answer on the network at the same time | 1 to 2 | Zongzhe | P0 |
| **M1** | The arm picks something up | With the emergency stop verified and a validated home pose, the arm grasps a box from a table using a mask from its own camera. Five attempts, success rate recorded | 3 to 6 | Dion | P0 |
| **M2** | Voice and gaze reach the arm | You say "grab the box", you look at one of two boxes, and the arm picks the one you looked at | 6 to 9 | Dion | P1 |
| **M3** | The base navigates | A map of the lab exists, the robot localises in it, and it drives to a commanded point and reports arrival. Ten runs, repeatability recorded | 4 to 8 | Zongzhe | P1 |
| **M4** | The current system, closed loop | One run: speak, look, the base drives, the arm grasps. Per-stage timing recorded | 9 to 11 | Dion | P1 |
| **M5** | The base has a calibrated forward camera | A RealSense D455 is mounted on the base, its position relative to the LiDAR is calibrated, LiDAR points project onto the right pixels in its image, and the camera-pose error is written down as a number | 3 to 11 | Sherman mount, Dion calibration | P0 |
| **M6** | The memory graph is built offline | From recorded data, the system produces a set of object entries with a 3D position and an image feature each, merged so the same physical object appears once. Querying it with a sentence returns sensible objects | 9 to 14 | Zongzhe | P1 |
| **M7** | The graph drives the robot | A spoken instruction produces an approach goal read out of the graph rather than from live perception, the base drives there, and close-range perception takes over | 14 to 17 | Dion | P1 |
| **M8** | Gaze picks the instance | The gaze-cropped image feature is carried into the graph query. Ablation with and without, N trials each, success rate reported | 15 to 19 | Dion | **P1, protected** |
| **M9** | Frontier scoring and visit ordering | The robot chooses where to explore next using the paper's scoring, measured against a baseline | 7 to 16 | Zongzhe | P2, optional |
| **M10** | Demonstration and paper | A recorded end-to-end run and a paper draft whose claim is M8's number | 18 to 20 | All | P1 |

### 5.2 Two checkpoints

| Date | Week | What should exist |
|---|---|---|
| **2026-12-06** | end of 12 | M0 to M5 done. A recorded run of the current system: speak, look, drive, grasp. A camera on the base with a calibration you can show a picture of. An offline memory graph you can query. This is the thing to talk about in December |
| **2027-01-31** | end of 20 | M6 to M8 and M10. A recorded run driven by the memory graph, and an ablation table |

### 5.3 Calendar

Week 1 is 2026-09-14. Weeks 15 and 16 (2026-12-21 to 2027-01-03) are planned at half velocity for the
holidays.

```
week   1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20
M0    ###
M1          ############
M2                   ##########
M3             ###########
M4                            ######
M5          ###########################
M6                            ################
M7                                          ##########
M8                                             ############
M9                   ...........................
M10                                                    #######
             ^ split opens                 ^ Dec 6 checkpoint     ^ Jan 31
```

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
recorded. Risk: the navigation workspace has never been compiled and depends on packages that were
never in any repository. Mitigation: M0 brings those in, and the build preparation is already
written and waiting to run.

**M4. The current system, closed loop.** Accept on one complete recorded run. Risk: this is the
first time the arm and the base are powered together, which is exactly what obstacle 2 prevents
today. Mitigation: obstacle 2 is removed in week 1.

**M5. The base has a calibrated forward camera.** Accept when LiDAR points projected into the
camera image land on the right objects, shown as a picture, and when the camera-pose error over a run
is written down as a number. The mount half is Sherman's. The calibration and error half, T5.5 to
T5.7, is Dion's and is the part that produces a result rather than a setup step. Risk: procurement. The supervisor
believes a D455 already exists in the lab, unconfirmed `[reported]`. Mitigation: confirm in week 1.
If it is not there, order immediately and use the wrist camera in a parked pose as a stand-in for
M6's offline work, which is explicitly allowed as a bring-up path by the paper review.

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

### 6.2 M0. Everyone can build and run (weeks 1 to 2)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T0.1 | Find the D455 in the lab. Confirm the model, that it works, and that we may use it. If it is not there, raise the purchase the same day | Sherman | 2 | lab | none |
| T0.2 | Get a network switch. Add the second host address to the wired port. Prove the arm and the LiDAR both answer in one session | Sherman, Dion | 5 | lab | none |
| T0.3 | Make the repository run from a fresh clone. Paths inside the repository are computed from the repository root. Paths outside it move to one configuration file with sensible defaults | Zongzhe | 12 | off | none |
| T0.4 | Bring into git the four things the robot needs that live in nobody's repository: the base bring-up package, the navigation launch package, the LiDAR package manifest, and the saved map | Zongzhe | 6 | box | T0.3 |
| T0.5 | Zongzhe and Sherman each clone the repository on their own machine, build it and run the bench. This is the acceptance test for M0 | Zongzhe, Sherman | 8 | off | T0.3 |
| T0.6 | ROS 2 ramp, all three of us. Reading guide round 1, then run the simulated arm test and read what it printed | All | 24 | box | T0.5 |
| T0.7 | Write the channel contract: which stream owns which message channels, and the exact three handover points between streams. One page | Dion | 4 | off | none |
| T0.8 | Clear the bench backlog that has been waiting since the box went off: environment check, navigation build, ten navigation node tests | Dion | 5 | box | none |
| T0.9 | Measure the real base footprint and compare it with the 0.2 metre radius the navigation configuration assumes | Sherman | 3 | lab | none |

### 6.3 M1. The arm picks something up (weeks 3 to 6)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T1.1 | Answer the six open questions in the code audit and record the decisions. Several are choices, not fixes | Dion | 3 | off | T0.7 |
| T1.2 | Safety fixes before any power: the emergency stop key that the launcher promises but does not exist, the stop program ignoring Ctrl+C, and the arm driver being launched twice | Dion | 8 | off | T1.1 |
| T1.3 | Decide which home pose is correct and validate it on the simulated arm before using it on the real one | Dion | 4 | box | T1.1 |
| T1.4 | Physical safety setup at the robot: clear working volume, stop button within reach, mount and cable check | Sherman | 3 | lab | none |
| T1.5 | Write the bring-up runbook. Power on to ready, in order, with the check at each step and what a failure looks like | Sherman | 8 | lab | T1.6 |
| T1.6 | First powered arm session. Driver handshake, joint feedback arriving, no motion commanded | Dion, Sherman | 3 | lab | T0.2, T1.2, T1.4 |
| T1.7 | First commanded motion, to the validated home pose, with a hand on the stop | Dion, Sherman | 3 | lab | T1.3, T1.6 |
| T1.8 | Fix the three interlocking defects that stop the grasp path working: the inverted state condition in the grasp predictor, the consumer that only accepts candidates in one state, and the flag that makes the whole path unreachable | Dion | 10 | off, box | T1.1 |
| T1.9 | Fix the concurrency defects in the state machine. One condition variable with two locks, and an unlocked read, are undefined behaviour rather than untidiness | Dion | 8 | off, box | T1.8 |
| T1.10 | Decide which grasp prediction program is authoritative and make its Python environment reproducible from a script in the repository | Dion | 6 | box | T1.1 |
| T1.11 | Grasp using the stand-in mask publisher, on hardware. Fix its wrong channel name first | Dion, Sherman | 4 | lab | T1.7, T1.8, T1.9, T1.10 |
| T1.12 | Grasp using a live mask from the wrist camera with a fixed prompt word. Five attempts, success rate recorded | Dion, Sherman | 4 | lab | T1.11 |

### 6.4 M2. Voice and gaze reach the arm (weeks 6 to 9)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T2.0 | Settle the open decision in `NEXT_STEPS` 2.2: patch the spoken word into the existing arm-side segmentation program, or retire it and restore the pipeline call site. Recommendation below | Dion | 2 | off | T1.1 |
| T2.1 | Build one segmentation service that owns the model and is the only publisher of the three mask channels. Both current call sites become clients of it | Dion | 12 | off, box | T1.12, T2.0 |
| T2.2 | Switch the glasses image stream back on, one stage at a time so failures are attributable | Dion | 6 | lab | T0.3 |
| T2.3 | Verify the gaze path and measure the error introduced by the fixed 1.5 metre depth assumption. Record the usable distance range | Dion | 6 | lab | T2.2 |
| T2.4 | Decide when segmentation runs, instead of on every frame, and add an age limit so the arm never moves toward a stale position | Dion | 8 | off | T2.1 |
| T2.5 | Voice and gaze to grasp, on hardware. Two boxes, pick the one you looked at | Dion, Sherman | 5 | lab | T1.12, T2.3, T2.4 |

**Recommendation on T2.0: option 2, retire the arm-side program.** The reasoning is that M2's
acceptance test needs gaze, and gaze disambiguation exists only in the pipeline, not in the arm-side
program. Patching the spoken word into the arm-side program buys back voice but not gaze, so we
would do the larger piece of work anyway and then delete the patch. The cost of option 2 is that it
depends on segmentation ownership being settled first, which is T2.1, so the two land together. If
M1 runs late and a quick demonstration is needed in November, option 1 is the fallback: it is small,
local and reversible. Evidence for both is `CODE_AUDIT` L1 and `NEXT_STEPS` 2.2.

### 6.5 M3. The base navigates (weeks 4 to 8)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T3.1 | Compile the navigation workspace. Eight packages, never built | Zongzhe | 4 | box | T0.4 |
| T3.2 | Run the ten navigation node tests. Four are expected to fail against known defects. Explain any others | Zongzhe | 5 | box | T3.1 |
| T3.3 | Fix the missing arm-to-base transform during a mapping run, which today leaves the arm unconnected to the position tree | Zongzhe | 2 | off | T3.2 |
| T3.4 | Drive the base under keyboard control. Confirm the LiDAR publishes | Zongzhe, Sherman | 4 | lab | T0.2, T3.1 |
| T3.5 | Build a map of the lab and localise in it | Zongzhe, Sherman | 6 | lab | T3.4 |
| T3.6 | Drive to a commanded point ten times. Record the position error each time | Zongzhe, Sherman | 5 | lab | T3.5 |
| T3.7 | The navigation to arm handover on hardware: object position in, drive, arrived signal out | Zongzhe, Dion | 6 | lab | T1.12, T3.6 |

### 6.6 M4. The current system, closed loop (weeks 9 to 11)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T4.1 | One complete run, recorded on video: speak, look, drive, grasp | All | 8 | lab | T2.5, T3.7 |
| T4.2 | Measure how long each stage takes. Report the 99th percentile, not the average | Dion | 6 | lab | T4.1 |
| T4.3 | Keep the defect log from the first powered session onward. One line per bug: symptom, guess, actual cause | All | ongoing | off | T1.6 |

### 6.7 M5. The base has a calibrated forward camera (weeks 3 to 11)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T5.1 | Camera secured. Found in the lab, or ordered with a date | Sherman | 2 | lab | T0.1 |
| T5.2 | Design the mount. Forward facing, rigid, clear of the arm's swept volume, not looking at the robot's own body. The arm is mounted facing backward, which makes this a real constraint rather than a formality | Sherman | 10 | off | T5.1 |
| T5.3 | Fabricate and fit the mount | Sherman | 8 | lab | T5.2 |
| T5.4 | Measure the mount geometry and make it one source of truth. Today the same 0.18 metre offset is written in three independent places and the robot model carries a fourth | Sherman, Zongzhe | 5 | off, lab | T5.3 |
| T5.5 | Calibrate the position of the camera relative to the LiDAR. Dion owns the procedure and the numbers, Sherman owns the rig and the target | Dion, Sherman | 12 | lab | T5.3 |
| T5.6 | Verify the calibration by projecting LiDAR points into the camera image. Keep the picture, it goes in the paper | Dion | 4 | box | T5.5 |
| T5.7 | Choose where camera poses come from and characterise the error: drift over a run, and the duplicate-object rate it causes in the graph. Start with the existing 2D localisation because it is free. This is a measurement study, not a configuration choice | Dion | 12 | box | T3.5, T5.6 |
| T5.8 | Build a trial fixture: marked object positions and marked robot start positions, so a trial can be repeated exactly | Sherman | 8 | lab | T5.3 |

### 6.8 M6. The memory graph, offline (weeks 9 to 14)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T6.1 | Read the upstream HiCo-Nav code. Settle which solvers it needs and whether their licences are acceptable | Zongzhe | 4 | off | none |
| T6.2 | Record data of the lab with the base camera: images, depth, LiDAR, positions | Sherman | 4 | lab | T5.6 |
| T6.3 | Build object entries from recorded data: mask, depth, camera position, image feature | Zongzhe | 14 | off | T6.2 |
| T6.4 | The merge test, so the same physical object seen twice becomes one entry: 3D overlap combined with image feature similarity | Zongzhe | 10 | off | T6.3 |
| T6.5 | The two-stage trigger. A cheap detector runs always, the expensive one runs only when a new object class appears or the robot has moved enough. This also closes the "when should segmentation run" question from M2 | Zongzhe | 8 | off | T2.4, T6.3 |
| T6.6 | Decide the reasoning model endpoint, cloud or local, and check whether sending lab images off site is permitted. A procurement and policy question of the same kind as T0.1 | Sherman | 4 | off | none |
| T6.7 | The reasoning layer. Called once at the start of a task, off the control loop, expanding the instruction into related objects | Zongzhe | 10 | off | T6.4, T6.6 |
| T6.8 | Query the graph with a sentence and get an object position back | Zongzhe, Dion | 8 | off | T6.4 |

### 6.9 M7. The graph drives the robot (weeks 14 to 17)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T7.1 | Publish the approach goal from the graph instead of from live perception. The channel and its meaning do not change, only who writes to it. **Write this node in C++ with rclcpp**, not Python. `object_approach_node.py` is a working reference for the same behaviour, so you can diff against it and know when the C++ one is right | Dion | 16 | box | T3.7, T6.8 |
| T7.2 | Build the graph while the robot drives, rather than from a recording | Zongzhe | 10 | lab | T5.7, T7.1 |
| T7.3 | Spoken instruction to arrival at the right object, on hardware, with the object not in view when the instruction is given | All | 8 | lab | T7.2 |

### 6.10 M8. Gaze picks the instance (weeks 15 to 19). Protected

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T8.1 | Produce an image feature from the gaze-cropped region of the glasses frame | Dion | 8 | off | T2.3 |
| T8.2 | Carry that feature into the graph query so it selects an instance rather than a class | Dion | 10 | off | T6.8, T8.1 |
| T8.3 | Run the ablation. N trials with the feature and N without, same objects, same start positions, using the fixture | Dion, Sherman | 18 | lab | T5.8, T7.3, T8.2 |
| T8.4 | Re-measure the cross-camera matching baseline so the comparison number is ours rather than remembered | Dion | 4 | box | T2.1 |

### 6.11 M9. Frontier scoring and visit ordering (weeks 7 to 16). Optional

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T9.1 | Get the upstream simulator evaluation running as a baseline | Zongzhe | 8 | off | T6.1 |
| T9.2 | Implement frontier scoring | Zongzhe | 12 | off | T9.1 |
| T9.3 | Implement visit ordering with an openly licensed solver | Zongzhe | 10 | off | T9.2 |
| T9.4 | A node that emits drive goals, sitting beside the existing bridge, with Nav2 unchanged | Zongzhe, Dion | 8 | box | T9.3 |

### 6.12 M10. Demonstration and paper (weeks 18 to 20)

| ID | Task | Owner | Hours | Where | After |
|---|---|---|---|---|---|
| T10.1 | Full demonstration run, recorded | All | 8 | lab | T8.3 |
| T10.2 | Paper draft. The central table is T8.3's ablation | All | 24 | off | T8.3 |
| T10.3 | Reproducibility artifacts: the bench, the recorded data, this plan, the defect log | Dion | 6 | off | T10.2 |

### 6.13 The critical path

The longest chain of dependent tasks from today to the claim:

```
T0.3 -> T0.4 -> T3.1 -> T3.2 -> T3.5 -> T5.7 -> T7.2 -> T7.3 -> T8.3 -> T10.2
```

and the second chain, which is the one that runs through Dion:

```
T0.7 -> T1.1 -> T1.8 -> T1.9 -> T1.11 -> T1.12 -> T2.1 -> T2.4 -> T2.5 -> T3.7 -> T7.1 -> T8.2 -> T8.3
```

Thirteen tasks, almost all of them Dion's. That is the schedule risk in one line. Anything that can
be moved off that chain should be, which is why T6.5 and T6.6 were moved and why navigation is
Zongzhe's outright. T7.1 stays on the chain and is written in C++ on purpose.

---

## 7. Assignment and load

### 7.1 Why each person has what they have

**Zongzhe, computer science.** Starts with two pure software tasks that need no
robot and no ROS knowledge: path portability and bringing the missing packages in. Both force him to
read the repository layout, which is the fastest way to learn it. Then navigation, which is the most
self-contained subsystem and gives him ROS experience on a stack that cannot damage anything while it
is being built. Then the memory graph, which is algorithm work of the kind a computer science student
is best placed to do, and which sits on the critical path so his time is not spent off to one side.

**Sherman, mechanical engineering.** Owns the physical layer, which is genuinely
separate work rather than made-up work. The network switch is the single change that unblocks arm and
navigation running together. The camera mount is on the critical path. The mount geometry task fixes a
real defect, which is that one physical measurement is written down in four places that can disagree.
He is also the person most often in the lab, so he owns the bring-up runbook and the trial fixture,
and he runs the ablation trials in M8. Running trials to a fixed procedure is a large part of the
experimental work and needs no code at all.

**Dion, computer engineering and perception.** The arm, the perception chain and the contribution.
This is the critical path and it is also the part that matches his background. The mitigation for him
being the contention point is T0.7, writing the channel contract in week 1, so the other two can build
against an agreed interface instead of against Dion's availability.

Three deliberate choices inside Dion's share, all of which keep the total the same:

- **T7.1 is written in C++ with rclcpp, not Python.** It costs about a week more than the Python
  version and it costs nobody else anything, because nothing downstream cares which language publishes
  the channel. `object_approach_node.py` already implements the same behaviour, so there is a working
  reference to diff against. It is the highest single-item return in the plan.
- **T5.5 to T5.7 are a calibration and localisation-error workstream, not mount support.** Dion owns
  the procedure, the numbers and the error characterisation. Sherman owns the rig, the target and the
  mount. Framed that way it produces a measured result rather than a setup step, which is a section of
  the paper.
- **T6.5 and T6.6 move off Dion.** The two-stage trigger is graph-adjacent and sits naturally with
  Zongzhe, who owns the graph. The endpoint decision is procurement and policy, which is the kind of
  item Sherman already carries. That is twelve hours back, which pays for the C++ premium on T7.1 and
  the expanded T5.7 without adding to anyone's load.

### 7.2 What each person is expected to put in

| Person | Hours a week |
|---|---|
| Dion | about 12 |
| Zongzhe | 8 to 10 |
| Sherman | 8 to 10 |

That is about 30 person-hours a week, and about 515 over the twenty weeks once the December holidays
and travel are taken out. The named work in section 6 comes to roughly 406 hours, so the plan runs at
about 79 percent of capacity. Sherman's share carries more slack than the task list suggests, because
the travel and the lab session overhead land on him and none of the estimates capture them.

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

If the schedule slips, cut from the top of this list. Decided in advance so it is not an argument
in week 16.

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
| The first powered arm sessions take far longer than estimated. The arm has never moved | High | M1 slips into week 7 or 8, pushing everything | Three short sessions rather than one long one. M3 runs in parallel and is not blocked by it |
| The camera is not in the lab and procurement takes weeks | Medium | M5 slips, M6 loses its input | Confirm in week 1. Fall back to the wrist camera in a parked pose for M6's offline work |
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

Beyond week 20, in the order they would become worth doing.

1. The return-to-user leg, which needs the pose fusion node rewritten to match its own documentation,
   the marker path restored, and the frame disagreement settled.
2. Naming everything descriptively across the repository, in one deliberate pass, with the frame
   renames last and done with somebody at the robot.
3. One configuration tree, with channel names declared as parameters rather than as constants so they
   stay overridable at launch.
4. Replaying recorded data as a regression test, and a continuous integration job running the offline
   bench tiers on every change.
5. The paper's motion layer, only if Nav2's controller proves inadequate around moving obstacles.
6. Better localisation, only if the duplication rate measured in T5.7 says the current one is the
   limiting factor.

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

## 12. Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-13 | Claude (Opus 5) + Dion | Created. Milestone spine M0 to M10, task tree with 60 nodes and their dependencies, three-way split validated against the constraints, scope written down with reasons for what is out, cut list decided in advance, Linear structure proposed. |
| 2026-09-13 | Claude (Opus 5) + Dion | Dion's revisions: T7.1 written in C++ with rclcpp, T5.5 to T5.7 reframed as Dion's calibration and localisation-error workstream rather than mount support, and T6.5 and T6.6 handed to Zongzhe and Sherman. Per-person hour totals replaced by a weekly expectation. Removed the skill labels on individual people, since nobody here has deep ROS 2 experience yet and T0.6 now covers all three. |
