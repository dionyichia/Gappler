# HiCo-Nav — paper review and first-pass integration assessment

**Subject paper:** Xu, Liu, Yang, Liang, Jin, Yuan, Wang, Xie — *HiCo-Nav: A Deployable Embodied
Vision-Language Navigation System with Hierarchical Cognition and Context-Aware Exploration*.
CARTIN / NTU EEE + Spatial AI & Robotics Lab, University at Buffalo. Extended journal version of an
ICRA 2026 conference paper. Local copy: [`HiCo-Nav.pdf`](HiCo-Nav.pdf). Upstream code:
`https://github.com/xukuanHIT/HiCo-Nav`.

**Companion documents:** [`../ORIENTATION.md`](../ORIENTATION.md) §10 (integration surface),
[`../NEXT_STEPS.md`](../NEXT_STEPS.md) §1 (the three open decisions this report is meant to close),
[`hico-nav-map.html`](hico-nav-map.html) (the visual version of this document).

**Scope discipline.** This is a *reconnaissance* report, written to the brief "find the blockers
that have procurement or calibration lead time before any code is written." It deliberately stops
short of an integration plan. Section 7 states what it does *not* answer.

**Status tags**, consistent with the rest of `docs/`: `[paper]` stated explicitly in the PDF ·
`[code]` verified by reading this repository · `[inferred]` my reasoning, not a fact in either
source · `[open]` genuinely undecided.

---

## 1. Summary and results

HiCo-Nav is a **zero-shot vision-and-language navigation (VLN) system**: you speak or type an
instruction in open natural language ("I want to host a dinner party on a summer evening, where
should I set the table?"), and an untrained robot explores an unseen indoor environment until it
finds and reaches the object the instruction implies. It is training-free — no fine-tuning per
environment, no annotated trajectories.

Its central architectural claim is that navigation intelligence is **multi-scale**, so the system
must be split by time constant rather than by function. It runs three layers concurrently on
separate threads: a 10–20 Hz perception–action layer, a 1–2 Hz memory-construction layer, and a
continuously-running vision-language-model (VLM) reasoning layer. A shared **cognitive memory
graph** (CMG) is the only interface between them, so the slow reasoning never blocks the fast
control loop.

### 1.1 Results relevant to us

| Question the repository docs had open | Answer from the paper | Consequence |
|---|---|---|
| Does HiCo-Nav need a forward-facing RGB-D camera? (`NEXT_STEPS` §1.1) | **Yes, and it is load-bearing, not incidental.** `[paper]` The memory graph's nodes *are* camera keyframes; RGB is what gets sent to the VLM. Depth is what gives objects 3D position. | Blocker confirmed. Procurement decision is real. See §6.1. |
| Does it emit goals or velocities? (`NEXT_STEPS` §1.2) | **Velocities — and considerably more.** `[paper]` §III-E: it runs its own A\* global planner, its own trajectory optimiser and its own dynamic-obstacle controller, producing `(v_t, ω_t)` directly. | It is a **whole-stack replacement for Nav2**, not a plugin swap. But a partial port that emits goals is available and is what I would recommend. See §5.1. |
| How much does it subsume? (`NEXT_STEPS` §1.3) | The CMG holds every object it has ever seen, with a 3D point cloud and a CLIP feature per object. It is a natural source of truth for "where is the thing I was asked for" — at navigation precision, not grasping precision. | It can produce the approach goal. It cannot replace live SAM 3 + AnyGrasp at grasp range. See §5.3. |
| How do objects get registered — does SAM run every frame? | **No — a four-stage cascade.** `[paper]` YOLO-World detects on *every* frame (10 fps); MobileSAM segments and registers only on selected keyframes (~one per 1–2 s). A free escalation test sits between them. See §4.4a. | A 10–20× reduction in segmentation calls, and it **answers `NEXT_STEPS` §2.1**. See §5.5. |
| Anything the docs did not anticipate? | **Three new dependencies with real lead time:** FAST-LIVO2 LiDAR-inertial-visual odometry, a LiDAR↔camera extrinsic calibration, and a VLM endpoint (cloud API or a local 8B model competing with SAM 3 for VRAM). | See §6.2–§6.4. |

### 1.2 The good news

The paper's real-world platform is **a Livox MID-360 LiDAR plus a RealSense camera** `[paper]`
§III-B. This repository's mobile base already has a MID-360 `[code]` `ORIENTATION` §9. The LiDAR
half of the sensor suite is a match, which removes the single most expensive unknown. What is
missing is the camera *placement*, not the camera *class*.

### 1.3 The headline number

Reported quadruped deployment: **95 % success on large objects, 65 % on small objects** over 40
voice-commanded real-world trials `[paper]` §IV-E. The small-object gap is attributed to
motion-induced image blur — a fact that matters directly to our mounting decision (§6.1).

---

## 2. Current state

### 2.1 What this repository has

`[code]` Verified against `main` @ `2d36a89`, and consistent with `ORIENTATION.md` §9 and §5.

| Element | State |
|---|---|
| Mobile base | `xnode_vehicle` + `xnode_comm`, differential drive, consumes `/cmd_vel` |
| LiDAR | Livox MID-360, `frame_id livox_frame`, statically mounted at `0.18 0 0.2` on `robot_base_link` |
| Localisation and mapping | `slam_toolbox` (2D, from a `pointcloud_to_laserscan` projection of the MID-360 cloud, height band −0.1 … 0.5 m) |
| Planning | Nav2: `NavfnPlanner` global, `RegulatedPurePursuitController` local, circular footprint `robot_radius: 0.2` |
| Camera | **One** RealSense D435i, eye-in-hand on the arm's `Link6`. `Navigation_Module` has no image topic anywhere in it. |
| IMU | Aria glasses publish `/aria/imu`; the base and the LiDAR do **not** expose a synchronised IMU topic in this workspace |
| Odometry | `xnode_vehicle` wheel odometry → TF `odom → robot_base_link` |
| VIO | OpenVINS is vendored under `Navigation_Module/OpenVINS/` but is launched externally; `/aria/vio_pose` has no publisher inside the repo |
| Semantic perception | SAM 3 (3.4 GB checkpoint) on the RealSense stream, hardcoded text prompt `"box"` |
| Compute | Single Ubuntu 22.04 host, RTX 4060 Ti 16 GB `[reported]` |

### 2.2 What the existing documentation already assumed

`ORIENTATION.md` §10 and `NEXT_STEPS.md` §1 were written before the paper was read, and flagged the
RGB-D requirement as `[inferred, needs confirming against the paper]`. **That inference was
correct.** This report upgrades it to `[paper]` and sharpens it: the requirement is not merely for
depth data, it is for a *stable, forward-facing, continuously-streaming* colour-plus-depth view,
because the images themselves are the memory substrate.

---

## 3. Methodology

The PDF has no embedded text-extraction tooling available on this machine (`pdftotext`, `pypdf` and
`PyMuPDF` are all absent). I decompressed the PDF's FlateDecode content streams directly and
reconstructed the text from the `Tj`/`TJ` show-text operators, including the figure-label streams
(streams 12–13), which carry the architecture diagram's box text — that is where the layer
frequencies (10–20 Hz, 1–2 Hz) and the hardware list are stated.

Every claim below is traceable to either a paper section or a repository file. Claims that are
neither are marked `[inferred]` and should be treated as hypotheses to be tested, which is the
stated purpose of this document.

**Limitation.** The upstream GitHub repository was not fetched or inspected. Everything about the
implementation — solver choice, ROS interface, node layout, actual dependency list — is read off the
paper, and the paper describes a method, not an API. Several §6 estimates would firm up
considerably after one hour spent reading that repository's `package.xml` and launch files. I have
flagged where that is the case.

---

## 4. Findings — what HiCo-Nav is and does

### 4.1 The three-layer asynchronous architecture

`[paper]` §III-A, Fig. 2. The system's organising principle is that reactive control and
deliberative reasoning have fundamentally different time constants, and that coupling them — the
usual "fast module decides when to invoke the slow module, then blocks on it" design — forces a bad
trade-off: trigger often and lose real-time performance, trigger rarely and miss targets.

| Layer | Rate `[paper]` | Contents | Blocking? |
|---|---|---|---|
| **1 · Real-time perception, localisation, planning** | 10–20 Hz | SLAM localisation, open-vocabulary object detection, obstacle avoidance, global and local planning, chassis commands | Never blocks |
| **2 · Memory construction** | 1–2 Hz | Graph primitive construction, graph update, ILP-based graph refinement, graph decomposition | Never blocks |
| **3 · High-level reasoning** | Continuous, asynchronous | Instruction decomposition, subgraph reasoning against a VLM, target verification | Runs on its own thread; result is *deposited*, never awaited |

The three layers communicate **only** through the shared cognitive memory graph. Layer 3 is
*proactive*: it walks the memory space on its own schedule rather than reacting to a trigger from
Layer 1. This is the paper's main departure from prior fast–slow VLN work.

### 4.2 Inputs

`[paper]` §III-B and Fig. 2.

| Input | Purpose | Notes |
|---|---|---|
| **RGB image stream** | Open-vocabulary detection (YOLO-World); *becomes* the visual anchor content sent to the VLM | RealSense D455 in the real-world deployment |
| **Depth image stream** | Reconstructs each detected object's 3D point cloud, given the camera pose | Must be pixel-registered to colour |
| **LiDAR point cloud** | Localisation via FAST-LIVO2; occupancy map for frontier extraction and obstacle avoidance | Livox MID-360 |
| **IMU** | Required by FAST-LIVO2 (LiDAR-**inertial**-visual odometry) | Implicit in the FAST-LIVO2 dependency |
| **LiDAR↔camera extrinsics** | Camera poses are computed by FAST-LIVO2 and transformed into the camera frame using calibrated extrinsics | Explicitly named as a prerequisite in §III-B(a) |
| **Language instruction** | The task. Free-form natural language, delivered by voice in the real-world experiments | |
| **Robot kinematic limits** `v_max`, `ω̇_max` | Used inside the goal-ordering cost model, Eq. 20 | |

### 4.3 Outputs

| Output | Type | Where it goes |
|---|---|---|
| **Chassis velocity commands `(v_t, ω_t)`** | Smooth, collision-free, from trajectory optimisation with dynamic-obstacle-aware control `[paper]` §III-E | Robot platform |
| **Mid-term navigation goal** | The first node of the WTRP-ordered frontier sequence | Its own local planner |
| **Target localisation** | The selected visual anchor plus a 2D bounding box on it, produced by the VLM `[paper]` §III-C(b) | Task completion / downstream consumer |
| **Reasoning evidence** | A concise natural-language justification for the decision | Logging, explainability |
| **The CMG itself** | Persistent bipartite graph of visual anchors and object nodes | Shared state |

### 4.4 The cognitive memory graph

`[paper]` §III-B. This is the paper's most portable idea and the one with the most direct bearing on
this project.

**Structure.** A bipartite graph `G = (V_a, V_o, E)`:

- `V_a` — **visual anchors**: selected RGB keyframes, each a compact visual memory unit.
- `V_o` — **object nodes**: each `o_j = {P_j, f_j}`, a 3D point cloud plus a semantic feature.
- `E` — an edge `(a_i, o_j)` means "anchor `a_i` observed object `o_j`".

The design argument is explicitly *against* multi-layer symbolic scene graphs: raw visual
observations are a more compact and information-rich substrate, and they are natively compatible
with a VLM, which consumes images rather than symbol tables.

### 4.4a How objects actually get registered — the four-stage cascade

`[paper]` §III-B(a) and §IV-E. Worth stating precisely, because the obvious guess is wrong and the
answer has direct consequences for `NEXT_STEPS` §2.1.

**Segmentation does not run every frame.** It does not run every *other* frame either. The pipeline
is a **cascade**: a cheap detector runs on everything, and an expensive segmenter runs only on the
frames the detector's output says are worth keeping.

| Stage | What runs | On what | Real-world rate `[paper]` §IV-E |
|---|---|---|---|
| 1 · Pose | FAST-LIVO2, transformed to the camera frame via the calibrated extrinsics | every frame | sensor rate |
| 2 · Detect | **YOLO-World**, open-vocabulary bounding boxes | **every incoming frame** | **10 fps** |
| 3 · Decide | The anchor test (Eq. 2) — cheap, no inference at all | every frame | 10 fps |
| 4 · Segment + register | **MobileSAM** mask → depth + pose → 3D point cloud → CLIP feature → merge test | **only on selected anchors** | **one every 1–2 s** |

**The anchor test is the whole trick** (Eq. 2). A frame becomes a visual anchor if *either*:

```
(i)   ∃ a new object in this frame                    ← semantic novelty
(ii)  ‖t‖ > τ_d   or   θ > τ_θ                        ← geometric novelty
```

where `t` and `θ` are translation and rotation **relative to the last selected anchor** — not to the
previous frame, so slow drift accumulates and eventually trips the threshold. Stage 4 runs only when
this fires.

So the arithmetic: detection at 10 fps, anchors at roughly 0.5–1 Hz, giving **a 10–20× reduction in
segmentation calls** versus running the segmenter on every frame. The paper states the observed rate
directly — "one visual anchor being selected every 1–2 seconds to update the CMG" — and explicitly
frames it as what keeps the layers from blocking one another.

**Then registration proper.** For each object detected *in that anchor*: MobileSAM cuts the mask,
depth plus camera pose lift it to a 3D point cloud `P_j`, a CLIP feature becomes `f_j`, and the new
node is edge-linked to the anchor. Only then does the merge test in §4.4's Eq. 4 decide whether it
is a new object or another sighting of a known one.

`[inferred]` Three properties of this design worth noting, because they are the transferable part:

- **The escalation criterion is free.** Stage 3 is a threshold on numbers stage 1 and 2 already
  produced. It costs no inference, which is what makes the cascade worth having.
- **Novelty is checked in two independent currencies.** Semantic ("something I have not seen") and
  geometric ("somewhere I have not been"). Either alone is insufficient: a robot standing still in a
  changing scene needs (i); a robot driving through a corridor of identical doors needs (ii).
- **The two models are asymmetric on purpose.** YOLO-World is the always-on gate; MobileSAM — a
  deliberately lightweight SAM variant — is the escalation. The expensive model never sees most
  frames.

**Update** `[paper]` §III-B(b), Eq. 4. A new object node is merged into the most similar existing
node if a joint score exceeds a threshold:

```
s(o, o′) = λ₁ · s_g(o, o′) + λ₂ · s_s(o, o′)
           └─ 3D IoU ──┘     └─ CLIP cosine ─┘
```

**Pruning** `[paper]` §III-B(c), Eqs. 5–7. As the graph grows, anchors proliferate. Anchor selection
is posed as a **weighted set multicover** problem and solved by integer linear programming:

```
minimise   Σ_i  c_i · x_i                        over x_i ∈ {0,1}
subject to Σ_{i : (a_i,o_j) ∈ E} x_i  ≥  r_j     for every object o_j
where      r_j = min(κ, |{a_i : (a_i,o_j) ∈ E}|)
```

Each object must remain covered by up to `κ` anchors where possible. With uniform cost `c_i = 1`
this minimises anchor count; in general `c_i` can encode anchor quality or viewpoint diversity. The
paper contrasts this with heuristic filtering: the ILP guarantees semantic completeness while
compacting memory.

### 4.5 Asynchronous VLM reasoning

`[paper]` §III-C, Fig. 3.

The whole CMG will not fit in a VLM context window, so it is decomposed into subgraphs and streamed.

**Instruction decomposition.** Once per task, the VLM parses the instruction into two object sets:
`O_t` (**target** objects — seeing one completes the task) and `O_r` (**related** objects —
semantically associated context, e.g. chairs for a table). This single up-front call is reused for
the rest of the run, including by the exploration scorer (§4.6).

**Subgraph construction** (Eq. 10). For each target object `o_t`, the subgraph is `o_t`, every
anchor that observed it, and every *other* object those anchors observed. The same is done for
related objects. Leftover anchors each form a singleton subgraph with their own objects.

**Prioritisation** (Eq. 11). Target and related subgraphs go first. The remainder are ordered by
`P(G_k) = Σ_{o_i ∈ V_k^o} s(o_i, T)`, a CLIP similarity between each object and the task text.

**Reasoning.** A dedicated thread queries the VLM subgraph by subgraph and asks for three things:
(1) is the target visible in any of these anchors, (2) if so, pick the best anchor and give a
bounding box, (3) give a short justification. Real deployment used the **Qwen3-Omni cloud API**;
the efficiency table also reports an offline **Qwen3-VL-8B** variant.

### 4.6 Context-aware frontier exploration

`[paper]` §III-D. When the target has not yet been seen, the robot must explore. Each frontier `f_i`
gets a utility score combining two complementary evidence sources — most prior work uses only one:

```
U(f_i) = λ₁ · S_struct(f_i) + λ₂ · S_vis(f_i)
```

**Structural-semantic propagation** (Eqs. 13, 15). Objects co-occur in a distance-dependent way — a
chair is likely near a table. Each object node projects a Gaussian field onto a 2D score map:

```
φ_j(p) = s_j · exp( −‖p − p_j‖² / (2 σ_j²) )
```

with peak `s_j` = CLIP similarity between that object and the task, and width `σ_j` = the average
extent of the object's 3D bounding box. Fields superpose; a frontier's structural score is the
superposed value at its location.

**Task-aware semantic modulation** (Eq. 14). Rather than call the VLM during exploration, objects
that appear in the up-front `O_r` set get a multiplicative boost `γ > 1`. **VLM reasoning influences
exploration predictively, at zero marginal inference cost.** This is a clean design and worth
copying regardless of what else we take.

**Out-of-boundary evidence** (Eq. 16). Depth is truncated at the sensor's range, but the *image*
that observed a frontier boundary still contains scene content extending past it. Each frontier is
associated with that anchor image, and `S_vis(f_i) = s(a_i, T)`, a CLIP similarity between the image
and the task. This is the mechanism that lets the robot "see down the corridor" beyond its mapped
region — and it is another reason a camera is required, not optional.

### 4.7 Goal selection as a Weighted Traveling Repairman Problem

`[paper]` §III-E. The paper's most distinctive planning contribution.

Greedy frontier selection — always go to the highest-utility frontier — is myopic and produces
oscillation. But a full TSP tour is also wrong, because the robot **stops as soon as it finds the
target**, so visiting every frontier is never required. The right objective is *expected
time-to-discovery*:

```
minimise over π    Σ_{i=1..n}  W_{π_i} · L_i(π)        where L_i(π) = Σ_{j=1..i} c_{π_{j−1}, π_j}
```

This is the **Weighted Traveling Repairman Problem**: minimise weighted cumulative latency, not
total tour length. High-weight frontiers are pulled earlier in the sequence, traded off against
travel cost.

**Weights** (Eq. 19) come from min-max-normalised utility passed through an exponential:
`W_i = exp(β · Û(f_i)) / exp(β)`. Larger `β` → peakier, more goal-directed; smaller `β` → smoother,
more balanced exploration.

**Transition cost** (Eqs. 20–24). The nominal cost is a *time* estimate under the robot's actual
limits:

```
c(k_a, k_b) = max( d(p_a, p_b) / v_max ,  |θ_a − θ_b| / ω̇_max )
```

For transitions from the robot's current state, two extra terms apply:

- **motion consistency** (Eq. 21) — an angular penalty against candidates that reverse the current
  heading, suppressing abrupt reorientation at replan time;
- **local structure** (Eq. 22) — prefers small enclosed unexplored pockets, resolving them before
  they cause repeated back-and-forth. Computed by raycasting from the candidate viewpoint toward its
  frontier cluster centre.

Solved with a heuristic TSP solver (**LKH** is named). The first node in the returned sequence
becomes the mid-term goal; the rest is retained as global guidance.

**Then, and only then, does execution happen** `[paper]` §III-E, final paragraph: distance-aware
path generation — A\* for distant goals, direct local planning for near ones — followed by
trajectory optimisation and dynamic-obstacle-aware control producing `(v_t, ω_t)`.

**This last sentence is the answer to `NEXT_STEPS` §1.2, and it is "velocities".**

### 4.8 Reported performance

Simulation, Habitat, against zero-shot and training-based baselines:

| Benchmark | HiCo-Nav SR / SPL | Best baseline | Margin |
|---|---|---|---|
| ObjectNav, MP3D | **48.5 / 21.5** | 45.4 / 17.2 | +3.1 SR |
| ObjectNav, HM3D | **61.0 / 31.8** | 59.6 / 33.0 (ApexNav) | +1.4 SR, −1.2 SPL |
| Open-vocabulary, HM3D-OVON val-unseen | **52.4 / 20.7** | 40.8 / 12.1 | +11.6 SR |
| Text-instance, TextNav | **27.8 / 12.9** | 20.2 / 11.4 (UniGoal) | +7.6 SR |

The margin widens as instructions get harder — small on category-only ObjectNav, large on
open-vocabulary and free-text tasks. That is the expected signature of a system whose advantage
comes from reasoning rather than from search efficiency.

**Efficiency**, first 100 HM3D episodes, on an RTX 5090 + Ryzen 9 9950X3D:

| Method | Task time ↓ | Step speed ↑ | Frame time ↓ | Reasoning |
|---|---|---|---|---|
| VLFM | 33.9 s | 1.00 m/s | 0.25 s | Low |
| ApexNav | 44.4 s | 1.67 m/s | 0.15 s | Medium |
| SG-Nav | 569.3 s | 0.11 m/s | 2.36 s | High |
| UniGoal | 298.3 s | 0.23 m/s | 1.07 s | High |
| **HiCo-Nav (offline Qwen3-VL-8B)** | 27.8 s | 1.47 m/s | 0.23 s | High |
| **HiCo-Nav (online Qwen3-Omni API)** | **21.5 s** | 1.54 m/s | 0.22 s | High |

The comparison that matters: SG-Nav and UniGoal also achieve "High" reasoning, but call an LLM/VLM
every step and pay 10–25× in task time. HiCo-Nav's asynchrony is what buys High reasoning at
VLFM-class frame times. **Note the evaluation hardware is an RTX 5090** — this table does not
characterise Jetson-class or 4060 Ti-class performance.

**Ablation**, TextNav:

| Variant | SR | SPL | Δ SR |
|---|---|---|---|
| Full system | 27.8 | 12.9 | — |
| w/o WTRP (greedy instead) | 25.4 | 11.8 | **−2.4** |
| w/o out-of-boundary score | 26.5 | 12.0 | −1.3 |
| w/o structural-semantic score | 26.7 | 12.1 | −1.1 |

WTRP is the single largest contributor. Both camera-derived exploration signals contribute, and they
are complementary rather than redundant.

### 4.9 Failure modes

`[paper]` §IV-C, Fig. 4. Directly relevant to our expectations.

| Failure | MP3D | HM3D | Relevance here |
|---|---|---|---|
| Different floor | 13.9 % | 18.5 % | **The system uses a 2D exploration map and cannot do cross-floor navigation.** Acknowledged limitation. Irrelevant to a single-floor lab. |
| False positive (stopped at wrong object) | 19.7 % | 8.8 % | Partly dataset annotation error, partly perception error under extreme viewpoints (a sofa read as a bed). |
| Step-out (exceeded 200 steps) | 15.0 % | 10.1 % | An artefact of the benchmark's step budget in large scenes. |
| No frontier remaining | 2.9 % | 1.8 % | Target never observed, or observed and not detected. |

Real-world: 95 % on large objects, **65 % on small objects**, with the gap attributed explicitly to
**motion-induced vibration of the robot causing image blur and reducing detection reliability**
`[paper]` §IV-E. On a quadruped with a rigidly mounted D455. Our target objects are graspable
tabletop items — the small-object regime.

---

## 5. Opportunities — what is worth porting

Ranked by value-per-unit-risk. `[inferred]` throughout; this is the hypothesis section.

### 5.1 The integration is separable into four tiers, and we should not take all four

The paper's system is a full navigation stack. This repository already has a working one. The useful
observation is that HiCo-Nav's contributions sit at *different heights* and can be adopted
independently:

| Tier | HiCo-Nav component | Displaces | Verdict |
|---|---|---|---|
| **A** | WTRP goal ordering + frontier utility scoring | Nothing — this is a layer *above* Nav2 that currently does not exist | **Port first.** Emits `/goal_pose`; Nav2 executes. Largest ablation contribution, smallest blast radius. |
| **B** | Cognitive memory graph + VLM reasoning | Nothing — no semantic memory exists in this repo today | **Port second.** Self-contained, additive, and it is what makes the voice command actually mean something. Requires the camera (§6.1). |
| **C** | A\* + trajectory optimiser + dynamic-obstacle controller | Nav2's `NavfnPlanner` and `RegulatedPurePursuitController` | **Do not port initially.** Nav2 already does this and is tuned for this chassis. Adopting it means re-tuning the whole motion layer for no benchmark benefit. |
| **D** | FAST-LIVO2 localisation | `slam_toolbox` | **Deferred, but see §6.2** — it may not be optional for Tier B. |

Adopting A + B and declining C is the shape I would expect the integration to take. It answers
`NEXT_STEPS` §1.2 as *"velocities in the paper, but we should take the goal-level interface
anyway"*, and it keeps the whole motion layer — the part that can drive a robot into a wall — as it
is today.

**The one thing this trade gives up:** the paper's dynamic-obstacle-aware controller, which Nav2's
`RegulatedPurePursuitController` with a `voxel_layer` local costmap approximates adequately for an
indoor lab.

### 5.2 The predictive VLM-modulation pattern is worth copying by itself

§4.6's Eq. 14 — call the VLM *once* at task start to expand the instruction into a related-object
set, then use that set to bias a cheap CLIP-based score map for the entire run — is a general
technique. It is the reason HiCo-Nav gets "High" reasoning at 0.22 s/frame. It transfers to this
repository even independently of the graph, and it is directly relevant to `NEXT_STEPS` §2.1's
question of when SAM 3 should run.

### 5.3 The CMG is a plausible answer to `NEXT_STEPS` §1.3, with a boundary

**Yes:** the CMG is a registry of every object seen, with 3D position and CLIP feature, queried by
natural language. It can produce `/manipulation/goal_pose` from memory, without live segmentation at
request time. It could also become the trigger source for SAM 3 (`NEXT_STEPS` §2.1's "graph-driven"
row), replacing the current every-frame inference.

**But:** `[inferred]` HiCo-Nav's object geometry is a depth-reconstructed point cloud from a
MobileSAM mask, at navigation range and navigation precision. AnyGrasp needs a clean, close-range,
correctly-registered mask to produce a 6-DoF grasp pose. **The CMG can tell the robot which room and
which table; it cannot replace the close-range SAM 3 → AnyGrasp path.** The likely division of
labour:

```
CMG (memory, coarse)  →  /manipulation/goal_pose  →  drive to the object
        ↓
   arrival triggers
        ↓
SAM 3 on live RealSense (close range, fine)  →  /camera/sam/mask  →  AnyGrasp  →  grasp
```

Which, usefully, is close to the architecture `ORIENTATION.md` §5 already describes — the CMG
replaces the *source* of the goal pose, not the grasp pipeline. That is a smaller change than
`NEXT_STEPS` §1.3 feared.

### 5.4 Voice already exists here

`[code]` The Aria glasses already publish `/aria/audio/prompt` (Whisper small.en → Qwen2.5-0.5B),
and `object_approach_node` already subscribes to it directly. HiCo-Nav's real-world experiments were
voice-commanded. **The instruction input is already built and already wired** — an unusual piece of
good luck, and it means Tier B's input side is essentially free.

### 5.5 The registration cascade answers `NEXT_STEPS` §2.1 — and validates its `[inferred]` row

`NEXT_STEPS.md` §2.1 asks when SAM 3 should run, notes that today it runs on **every synchronised
RGB+depth pair**, and lists four candidate policies. Its "two-stage" row was tagged `[inferred]` with
the caveat *"needs a second model and an 'interesting' criterion."*

**The paper implements exactly that design, and supplies the missing criterion.** §4.4a: a cheap
always-on detector, and an escalation test that costs nothing because it reuses numbers the detector
and the localiser already produced. The criterion §2.1 could not name is:

```
run the expensive model when   a new object class appears
                          or   the robot has moved or turned enough since last time
```

Three consequences for that work item:

- **The "two-stage" row is no longer speculative.** It has a published implementation with a stated
  rate (10 fps detect, ~0.5–1 Hz segment) and a concrete threshold form. The concern in §2.1 that a
  bespoke lightweight stage would be wasted work if the graph subsumed it is resolved the other way:
  the graph *needs* the two-stage cascade — the cascade is how the graph is built.
- **The model split matters, not just the trigger.** `[inferred]` The paper escalates to
  **MobileSAM**, a deliberately lightweight variant. We would be escalating to **SAM 3 at 3.4 GB**.
  Our cascade therefore saves proportionally *more* than the paper's, and the case for it is stronger
  here than there.
- **§2.1's "graph-driven" row and its "event-driven" row turn out to be the same row.** The graph's
  own anchor test *is* the event trigger. There is one policy to build, not two.

`[inferred]` This is also the cheapest thing on this whole list to try. The trigger is a distance
threshold, a rotation threshold, and a set-difference on detected class names — buildable against the
current stack, independent of Tier A, Tier B and the camera purchase, and it directly addresses the
"SAM 3 is the most expensive thing in the system" problem §2.1 opens with.

⚠️ Note that §2.1's other requirement still stands independently: whatever the trigger, add a
**staleness bound**. `ORIENTATION.md` §8.8 records that the consumer-side age guard in
`grasp_state_machine.cpp:637-641` is commented out. A cascade *lowers* the update rate by design,
which makes a missing staleness guard more dangerous, not less.

---

## 6. Results — the blocker register

The purpose of this document. Ordered by lead time, longest first.

### 6.1 🔴 A forward-facing RGB-D camera — CONFIRMED, weeks of lead time

**Status:** the `[inferred]` blocker in `ORIENTATION.md` §10 is now `[paper]`-confirmed, and it is
stronger than the doc supposed.

**Why it cannot be worked around.** The visual anchors in the memory graph *are* RGB keyframes —
they are the images sent to the VLM. Remove the camera and there is no `V_a`, therefore no graph,
therefore no reasoning layer, therefore no VLN. Three separate mechanisms need it:

1. Anchor content — the images the VLM reasons over (§4.5).
2. Object geometry — depth reconstructs `P_j` for each object node (§4.4).
3. Out-of-boundary frontier evidence — CLIP over the boundary image (§4.6), worth −1.3 SR when
   ablated.

**Re-evaluating the three options in `ORIENTATION.md` §10:**

| Option | Verdict after reading the paper |
|---|---|
| **1 · Buy a base-mounted RealSense** | **Recommended.** Buy a **D455**, not another D435i — it is what the paper deployed, and its wider FOV and longer depth range suit frontier observation, where the D435i's ~2 m usable range is marginal. Mount rigidly, forward-facing, on `robot_base_link`. |
| **2 · Park the arm in a fixed observation pose** | **Now looks worse than the doc assumed.** The paper's own small-object success rate drops to 65 % from vibration blur on a *rigidly mounted* camera. A camera on a 6-DoF arm at the end of a compliant kinematic chain will be worse. It also puts the camera pose inside the arm's TF chain, so every anchor pose depends on joint-state timing — and it makes the arm unavailable for grasping during exploration, which is a functional conflict, not just a quality one. Viable as a **bring-up path while a D455 is on order**; not viable as the answer. |
| **3 · Substitute the 2D LiDAR scan** | **Effectively rules out Tier B.** There is no image, so no anchor, no VLM input, no out-of-boundary score. What survives is a geometry-only frontier explorer — which is roughly VLFM-minus-the-V, and gives up the entire reason to adopt this paper. |

**Action, and it is the urgent one:** raise the D455 purchase now. `[open]` Cost was previously
estimated at ~$400 plus NTU procurement lead time. Nothing else in this report has a lead time
measured in weeks.

**Secondary consideration `[inferred]`:** mounting height and pitch. The paper does not specify
them. The MID-360 sits at 0.48 m on this base and the arm's `base_link` at 0.48 m yawed 180°. A
forward-facing camera needs a mount that clears the arm's swept volume and does not look at the
robot's own shell — a small mechanical design task that should start when the camera is ordered, not
when it arrives.

### 6.2 🔴 FAST-LIVO2 localisation — new, not in the existing docs

`[paper]` §III-B(a) states camera poses come from **FAST-LIVO2** (fast, direct LiDAR-inertial-visual
odometry, Zheng et al., T-RO 2024).

**Why this is a blocker and not a detail.** The CMG's correctness is entirely a function of camera
pose accuracy. Every anchor pose, every object point cloud, every 3D IoU merge in Eq. 4 depends on
it. Feeding a graph from a drifting or low-rate pose source will produce duplicated object nodes and
a graph that degrades over the run.

**What this repository has instead:** `slam_toolbox` in 2D on a laserscan projection of the MID-360,
plus wheel odometry from `xnode_vehicle`, plus OpenVINS vendored under `Navigation_Module/OpenVINS/`
but launched externally.

`[open]` Three paths, unresolved:

1. **Adopt FAST-LIVO2.** Closest to the paper. It needs a time-synchronised LiDAR + camera + IMU
   triple. `[inferred]` The base does not currently expose a synchronised IMU topic in this
   workspace — the MID-360 has a built-in IMU, and whether `livox_ros_driver2` is configured to
   publish it here needs checking. This is a bring-up project of its own.
2. **Use `slam_toolbox`'s `map → odom` plus TF to derive camera poses.** Cheapest. `[inferred]`
   2D SLAM gives no reliable pitch/roll, so anchor poses inherit that error — probably tolerable on
   a wheeled indoor base on flat floors, and definitely not on the paper's quadruped.
3. **Use OpenVINS**, already vendored. Middle ground, but it is visual-inertial without the LiDAR
   term, so it does not solve the LiDAR–camera registration problem for free.

**Recommendation:** start with path 2 and treat pose quality as the first thing to measure once the
camera is mounted. It is cheap to try and the failure mode (duplicated object nodes) is directly
observable in the graph.

### 6.3 🟠 LiDAR ↔ camera extrinsic calibration — days, and the graph is incorrect without it

`[paper]` §III-B(a) names calibrated LiDAR–camera extrinsics as a prerequisite. There is no such
calibration in this repository — there has never been a base-mounted camera to calibrate against.

This is a well-understood but fiddly workshop task (target-based or targetless; the Livox ecosystem
has tooling). Budget days, not hours, and note it can only start **after** the camera is physically
mounted. It sits on the critical path immediately behind §6.1, which is another reason the
procurement decision is the urgent one.

### 6.4 🟠 The VLM endpoint — a decision with cost, latency and privacy dimensions

`[paper]` §IV-E: real-world deployment used the **Qwen3-Omni cloud API**; the efficiency table also
reports an **offline Qwen3-VL-8B**. Online was faster (21.5 s vs 27.8 s) *because the evaluation
machine's GPU was not also hosting the model*.

`[open]` For this platform:

| Path | Consideration |
|---|---|
| **Cloud API** | Needs reliable network from a mobile robot, an API key and a per-call budget. Sends lab imagery off-site — worth checking against NTU/CARTIN policy before it becomes a default. |
| **Local Qwen3-VL-8B** | `[inferred]` ~8–16 GB VRAM depending on quantisation, on a 16 GB 4060 Ti that already hosts SAM 3 (3.4 GB), YOLO-World, MobileSAM and CLIP. **This is a genuine VRAM contention problem, not a rounding error.** Quantisation or a smaller VLM is likely required. |

`[inferred]` Note also that the paper's *efficiency* numbers come from an RTX 5090. Nothing in the
paper characterises this workload on a 4060 Ti, and the local-VLM path in particular should be
expected to be slower here. The asynchronous architecture is what makes that survivable — a slower
reasoning layer degrades decision quality gracefully rather than stalling control — but it is worth
stating rather than discovering.

### 6.5 🟡 Solver dependencies

Two optimisation solvers are load-bearing:

- **An ILP solver** for graph pruning (Eq. 5–7, weighted set multicover). Open options exist
  (CBC via PuLP, HiGHS, OR-Tools). `[inferred]` Low risk, but licensing should be checked before it
  is embedded — this project already carries one machine-locked commercial licence in AnyGrasp, and
  a second would be unwelcome.
- **LKH** for the WTRP (§4.7). LKH's own licence is free for academic use but **not open source**
  and not redistributable. `[inferred]` OR-Tools' routing solver is a plausible substitute for
  frontier-count-sized problems. Worth resolving before Tier A is written, since Tier A *is* the
  WTRP.

### 6.6 🟡 Confirmed non-blockers

Recording these so they are not re-litigated:

- **LiDAR** — MID-360 is exactly what the paper used. No action.
- **Cross-floor navigation** — the paper cannot do it (2D map). Single-floor lab, so irrelevant.
- **Voice input** — already built (§5.4).
- **Chassis interface** — HiCo-Nav's `(v_t, ω_t)` maps onto `/cmd_vel`, which this base already
  consumes. If Tier C is ever adopted, the interface itself is not the problem; `ORIENTATION.md`
  §8.7's three-claimants-on-`/cmd_vel` issue is.
- **Training data** — none. The system is zero-shot and training-free. No dataset collection, no
  fine-tuning, no annotation budget.

### 6.7 The register, summarised

| # | Blocker | Priority | Lead time | Decision owner |
|---|---|---|---|---|
| 6.1 | Base-mounted D455 RGB-D camera | 🔴 | **Weeks** (procurement) | Dr. Yuan / Dion — raise now |
| 6.2 | Camera-pose source (FAST-LIVO2 vs slam_toolbox vs OpenVINS) | 🔴 | Days–weeks | Engineering, after §6.1 |
| 6.3 | LiDAR↔camera extrinsic calibration | 🟠 | Days, after camera arrives | Engineering |
| 6.4 | VLM endpoint: cloud vs local | 🟠 | Days + policy check | Dion + supervisor |
| 6.5 | ILP and TSP solver choice / licensing | 🟡 | Hours–days | Engineering |
| — | Camera mount design | 🟠 | Weeks, **in parallel with 6.1** | Engineering |

---

## 7. Future work

### 7.1 What this report deliberately does not answer

Per the brief, no integration plan has been written. Specifically left open:

- Node decomposition, topic names, launch-file structure.
- Which of the seven contract topics in `ORIENTATION.md` §5 the CMG takes over (`NEXT_STEPS` §1.3
  is *narrowed* by §5.3 above, not closed).
- Whether the upstream implementation is ROS 2, ROS 1 or standalone — **unknown, and it materially
  affects effort.** This is the highest-value hour of follow-up available.
- Frame conventions: the paper's 2D exploration map versus Nav2's costmap; whether the CMG lives in
  `map` or in its own frame.
- How the CMG is persisted across runs, if at all.

### 7.2 Recommended sequence

1. **Now, before anything else:** raise the D455 purchase (§6.1). Start the mount design in
   parallel.
2. **This week, one hour:** read `github.com/xukuanHIT/HiCo-Nav` — `package.xml`, launch files,
   `requirements.txt`, node graph. Resolves §6.5 entirely and most of §7.1.
3. **While the camera is on order:** prototype **Tier A** (frontier utility + WTRP → `/goal_pose`).
   It is LiDAR-only, needs no camera, drops in beside `goal_reached_publisher.py`, and is the
   largest single ablation contributor. Best available use of the procurement wait.
4. **On camera arrival:** extrinsic calibration (§6.3), then measure camera-pose quality to settle
   §6.2, then build **Tier B**.
5. **Revisit Tier C only if** Nav2's controller proves inadequate for dynamic obstacles. Not before.

### 7.3 Open questions to carry into the next review

1. Is `livox_ros_driver2` in this workspace configured to publish the MID-360's built-in IMU? Decides
   whether FAST-LIVO2 is even reachable (§6.2).
2. Does CARTIN policy permit sending lab imagery to a commercial VLM API (§6.4)?
3. What is the actual concurrent VRAM budget on the 4060 Ti with SAM 3 resident (§6.4)?
4. Does the arm's swept volume permit a forward-facing base camera mount, given the arm is yawed
   180° (§6.1)?

---

## 8. What didn't work

Recorded so the same ground is not covered twice.

**PDF text extraction.** `pdftotext`, `pypdf` and `PyMuPDF` are all absent from this machine, and
`pdftoppm` is not installed so the Read tool cannot rasterise PDF pages either. Resolved by
decompressing the FlateDecode content streams and parsing the `Tj`/`TJ` operators directly. Worth
knowing: **the figure text lives in separate content streams** (12 and 13 in this file) from the
body text, and streams 12–13 are where the layer frequencies, the sensor list and the Jetson Orin NX
platform note are stated. A naive body-text-only extraction would have missed the single most
useful table in the paper.

**Reading the paper's efficiency numbers as transferable.** The initial temptation was to treat
21.5 s task time and 0.22 s frame time as what we would get. They are RTX 5090 numbers. The only
embedded-platform claim in the paper is qualitative — "real-time performance on a Jetson Orin NX",
with 10 fps YOLO-World detection and one anchor per 1–2 s as the only concrete figures. No
quantitative Jetson or 4060 Ti benchmark exists in the paper, so no throughput estimate for our
hardware can be honestly derived from it.

**Trying to resolve `NEXT_STEPS` §1.2 as a binary.** The question as posed — goals or velocities —
has no clean answer. The paper emits velocities, but that is a description of *its* stack, not a
constraint on *our* integration. Recasting it as the four-tier separation in §5.1 was more
productive than forcing the binary.

---

## 9. Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-10 | Claude (Opus 5) + Dion | Added §4.4a (the object-registration cascade — SAM runs on keyframes, not frames) and §5.5 (it answers `NEXT_STEPS` §2.1 and promotes that item's `[inferred]` two-stage row). |
| 2026-09-10 | Claude (Opus 5) + Dion | Created. Full read of the paper; confirmed the RGB-D blocker, answered the goals-vs-velocities question, narrowed the scoping question, and surfaced three previously unrecorded dependencies (FAST-LIVO2, extrinsic calibration, VLM endpoint). No integration plan by design. |
