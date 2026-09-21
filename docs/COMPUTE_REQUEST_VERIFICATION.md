# Compute Request (RCP2026/19) — verification against the codebase

**What this is.** A check of the draft "Compute Resource Request" doc against what this repo
actually runs, done before the request goes to the supervisor. Three corrections matter enough to
fix before submitting. The three tables in section 3 are the requested end state: one row per
requirement, with the memory or resource it needs.

**Status tags**, as in the rest of `docs/`: `[code]` read from source in this repo ·
`[reported]` the 2026-08-25 hardware session, or a bench run on the box · `[inferred]` reasoning ·
`[unverified]` not confirmed at the machine this session.

**Scope note.** The tailscale address (`100.87.133.60`) was unreachable this session, but the
campus address (`rcp2026@10.91.242.76`) worked, so the numbers below were pulled live from the box
on 2026-09-15 (`nvidia-smi`, `free -h`, `df -h`), not just carried over from the 2026-09-11 bench
log. The REP Makers server and any Jetson hardware are still outside this repo and this box, so
those two items stay `[unverified]`. No SLURM client (`sinfo`/`squeue`/`sacct`) is installed on
this machine, so the REP Makers claim could not be checked from here either way.

---

## 1. The three corrections that matter

### 1.1 The lab GPU is 16 GB, not 8 GB

The draft's §5.1 "4060 shortfall" argument rests on an 8 GB card. The box is actually an
**RTX 4060 Ti, 16 GB**, confirmed live over SSH on 2026-09-15 and twice in the docs:

- Live `nvidia-smi`, 2026-09-15: `NVIDIA GeForce RTX 4060 Ti, 16380 MiB total, 673 MiB used, 15273
  MiB free, 3% util` — only two processes hold GPU memory at idle: the remote-desktop daemon
  (120 MiB) and an Isaac Sim Python process under `/home/iot22/robot-learning/` (362 MiB), neither
  belonging to this project.
- `docs/ORIENTATION.md:1039` — "Machine | `iot22-Computer` ... RTX 4060 Ti 16 GB"
- `docs/TESTBENCH_PLAN.md:309` — same box, driver 575.57, confirmed again 2026-09-14
- `bench-runs/2026-09-11-labbox-w1-venv.txt` — preflight measured 15.5 GB free of 16.0 GB at idle,
  plus `sam3-weights 3.21 GB`, `anygrasp-detection 283 MB`, `anygrasp-tracking 23 MB` on disk

With 16 GB and the draft's own 10-12 GB estimate for the resident FAM-HRI stack, there is headroom,
not a shortfall, on the number that's actually measured. This doesn't mean the workstation
upgrade case disappears (see 1.3), but the "8 GB, 2-4 GB short" framing should not go to the
supervisor as written. `[reported, live-verified 2026-09-15]`

Also resolved while checking this: the draft's §7 flags **system RAM as unconfirmed**. Live
`free -h`: **31 GiB total, 25 GiB available.** `df -h ~`: `/home` is 325 GB total, 27 GB free,
92% used — tighter than the 8.3 GB `.venv` alone would suggest, consistent with `CLAUDE.md`'s
"check `df -h ~` before large builds" note. `[reported, live-verified 2026-09-15]`

### 1.2 HiCo-Nav's compute section describes code that does not exist yet, and is blocked on a camera that hasn't been bought

None of §4.2's components are in this repo: no YOLO-World, no MobileSAM, no CLIP descriptors, no
cognitive memory graph, no FAST-LIVO2. Checked directly: `pyproject.toml` lists only
`faster-whisper`, `lightglue`, `projectaria-client-sdk`, `projectaria-eyetracking`, `sam3`,
`transformers` — nothing HiCo-Nav-specific. `docs/hico-nav/PAPER_REPORT.md` is explicit
that this is still reconnaissance: "No integration plan has been written" (§7.1), and the upstream
release itself has no ROS layer, only a Habitat benchmark harness (§5.6).

More importantly, the thing HiCo-Nav's whole perception stack needs — a forward-facing RGB-D
camera — **does not exist on this robot**. `ORIENTATION.md:1063`: "⚠️ There is no base-mounted
RGB-D camera on this robot. The D435i is the only camera and it is on the moving wrist." The paper
report calls this blocker `🔴 CONFIRMED, weeks of lead time` (§6.1) and says it hasn't been raised
for purchase yet.

So §4.2's "6-10 GB, resident continuously" is a projection for a system that is weeks of
procurement away from having the sensor it needs, not a current requirement. It belongs in the
request as a forward-looking ask with that caveat attached, not folded into the merged total in
§4.3 as if it were concurrent with what's running today. `[code]` + `[paper]` (via PAPER_REPORT.md)

### 1.3 Two of the FAM-HRI line items are measurably different from what's coded

- **"Planning agents | LLM | API | 2 sequential calls | 1.3-2.2 s each"** — the actual component
  (`src/services/prompt_extractor.py:135`, `src/config/audio_streaming_pipeline_config.py:3`) is a
  **local Qwen2.5-0.5B-Instruct**, one call, loaded in fp16 on `Settings.DEVICE`
  (`prompt_extractor.py:30-33`). A 0.5B fp16 model is roughly 1-1.5 GB resident, not an API call on
  the critical path. The "API, 2 calls, 1.3-2.2s" figures look like they were carried over from the
  FAM-HRI paper's own planning-agent description rather than measured from this repo's code. Worth
  checking which one the request means to describe.
- **"Speech + word timestamps | faster-whisper | CPU"** — the code passes `device=Settings.DEVICE`
  (`audio_streaming_pipeline.py:59-62`), and `Settings.DEVICE` resolves to `"cuda"` whenever a GPU
  is present (`src/config/base.py:13`). On the lab box this runs on the GPU, int8, not on the CPU.
  Small footprint either way, but it is one more model sharing the same 16 GB, and the "CPU"
  column undercounts what's on the card.

---

## 2. Claims in the draft this repo cannot verify

These aren't wrong, just outside what this codebase, or this box, can confirm:

- **REP Makers RTX 4090 / `ninfer-serve` holding 23 GB at 0% util.** Nothing in this repo
  references the REP Makers server, and no SLURM client (`sinfo`/`squeue`/`sacct`) is installed on
  the lab box, so it isn't reachable through that machine either. This needs checking on the REP
  Makers server directly, or asking whoever showed you the `nvidia-smi` output for a fresh
  capture. `[unverified]`
- **"Onboard IPC: Jetson Orin NX 16 GB (ONX18F1E1)."** No file in this repo — not `ASSETS.md`,
  not `NEXT_STEPS.md`, not `TESTBENCH_PLAN.md` — records this project owning a Jetson. Every
  "Jetson Orin NX" mention in the docs traces to the HiCo-Nav paper's own quadruped platform
  (`PAPER_REPORT.md:751-759`, and `hico-nav-map.html:1322`: "Not from the Jetson the real robot
  carried, and not from our card"). If there genuinely is a Jetson on hand, it isn't recorded
  anywhere Claude sessions have written to, and the request should say where it came from. If
  there isn't one, §5 and §8 of the draft need rewriting, since "no onboard GPU upgrade is needed"
  currently rests on hardware that may not exist. `[unverified, likely incorrect as written]`
- **Aria SDK x86_64-only, no aarch64 wheel.** Plausible and consistent with `requires-python
  ==3.10.*` in `pyproject.toml`, but this repo doesn't state the aarch64 gap directly. `[inferred]`

Two items the draft's own §7 flagged as unconfirmed are now resolved (see §1.1 above): system RAM
is 31 GiB, and `/home` currently has 27 GB free at 92% used.

---

## 3. The three tables

### Table 1 — What's actually running today, verified against code

Every row here is a model this repo imports and instantiates, all sharing one GPU
(`Settings.DEVICE`) on the lab box.

| Component | Source | What it takes | Note |
|---|---|---|---|
| SAM 3, human view | `src/services/object_recognition/sam3_model.py` | 3.21 GB checkpoint (measured, `sam3-weights` preflight), bf16 autocast enabled | One instance per view; this is the Aria-side one |
| SAM 3, robot view | `ros2_robot_ws/src/rm_mtc/src/perception/sam3_ros_node.py` | 3.21 GB checkpoint, same weights file | Separate process from the human-view instance today |
| LightGlue + SuperPoint | `src/services/feature_matching.py:35-36` | SuperPoint, 2048 keypoints, + LightGlue matcher, both on GPU | Cross-view alignment, real-time on frame arrival |
| AnyGrasp + MinkowskiEngine | `grasp/vendor/` (was `grasp_module/`), checkpoints under `ros2_robot_ws/src/rm_mtc/src/perception/log/` | Detection net 283 MB, tracking net 23 MB on disk (checkpoint size, not runtime VRAM) | Licence machine-locked; re-registering to new hardware costs ~2 working days |
| Prompt extractor (LLM) | `src/services/prompt_extractor.py:135` | Qwen2.5-0.5B-Instruct, fp16, local, ~1-1.5 GB resident | Not an API call — corrects draft §4.1's "LLM, API, 2 calls" row |
| Speech transcription | `src/services/aria_device/stream/audio_streaming_pipeline.py:59-62` | faster-whisper `small.en`, int8, on `Settings.DEVICE` (GPU when present) | Corrects draft §4.1's "CPU" row |
| Aria gaze (Gen 1) | `src/config/models.py`, `projectaria-eyetracking` (pinned fork) | ~0.5 GB `[inferred, not measured]` | Offline inference only, per draft's own note |
| Aria client SDK | `projectaria-client-sdk==1.1.0` in `pyproject.toml` | 0 GPU, x86_64 host only | Streaming/control, no model weights |

### Table 2 — HiCo-Nav additions: planned, not built, blocked on procurement

Nothing in this table exists in the repo yet. Every row is a future requirement, gated by the
camera purchase in row 1.

| Component | Status | What it would take | Blocker |
|---|---|---|---|
| Base-mounted RGB-D camera (D455) | Not purchased | N/A (sensor, not compute) | 🔴 Hard blocker for every row below. Weeks of procurement lead time (`PAPER_REPORT.md` §6.1). No code below can run without it |
| FAST-LIVO2 localisation | Not implemented | CPU-bound, real-time | Needs the camera, plus a synchronised LiDAR-IMU-camera triple not yet confirmed to exist on this base (`PAPER_REPORT.md` §6.2) |
| YOLO-World (open-vocab detection) | Not implemented | ~2 GB `[paper-reported estimate, not measured here]` | Needs the camera stream |
| MobileSAM (keyframe segmentation) | Not implemented | Lightweight, ~1 anchor per 1-2 s, not every frame | Needs the camera stream; note this is MobileSAM, not SAM 3 — a materially smaller model than what the draft's §4.2 implies |
| CLIP descriptors | Not implemented | ~2 GB `[paper-reported estimate]` | Needs registered objects from MobileSAM first |
| Cognitive memory graph (ILP prune, 3D IoU merge) | Not implemented | CPU only | No GPU cost, but needs a working camera-pose source (§6.2) to be correct |
| Qwen3-Omni (reasoning layer) | Not implemented | API (paper's real-world deployment), or 20-24 GB local `[paper]` | Cloud-vs-local is an open policy decision (`PAPER_REPORT.md` §6.4), not yet made |
| LiDAR↔camera extrinsic calibration | Not done | Days of workshop time, no compute cost | Can only start after the camera is physically mounted |

### Table 3 — Hardware reality check: draft claim vs. what's verified

| Item | Draft claims | Verified here | Status |
|---|---|---|---|
| Lab box GPU | RTX 4060, 8 GB | RTX 4060 Ti, 16 GB, 15.3 GB free live (2026-09-15) | `[reported, live-verified]` — fix before submitting |
| System RAM | Unconfirmed (draft §7) | 31 GiB total, 25 GiB available, live | `[reported, live-verified]` — fills the gap the draft flagged |
| Disk free | 14 GB free, 2026-09-11 (`CLAUDE.md`) | 27 GB free of 325 GB, 92% used, live (2026-09-15) | `[reported, live-verified]` — still tight, check before large downloads |
| "In-room workstation" identity | Implied separate from the lab box | Same machine as `iot22-Computer` / the box everything else runs on, per `ORIENTATION.md` §9 | `[reported]` — worth confirming whether the draft means a second physical machine |
| Onboard IPC (Jetson Orin NX 16 GB) | Owned, adequate, no action needed | No record of this hardware anywhere in the repo; every Jetson mention is the HiCo-Nav paper's own robot | `[unverified, likely incorrect]` — confirm ownership or remove the row |
| REP Makers RTX 4090 / `ninfer-serve` | 23/24 GB held by an unscheduled process | Outside this repo; no SLURM client on the lab box to check it from there either | `[unverified]` — re-capture `nvidia-smi` fresh on that server before citing it in the request |
| Base-mounted RGB-D camera | Not listed as a request item (assumed present for HiCo-Nav compute estimates) | Confirmed absent (`ORIENTATION.md:1063`); procurement not yet raised | `[reported]` — this is arguably the request's most urgent line item and isn't in the summary table at all |
| Aria SDK network requirement | NTU campus network incompatible, needs dedicated router | Consistent with the Aria SDK's documented behaviour; not something this repo's code confirms directly | `[inferred]` — reasonable as stated |

---

## 4. Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-15 | Claude (Sonnet 5) + Dion | Created. Verified the draft compute request against `pyproject.toml`, the FAM-HRI-side service code, `ORIENTATION.md`, `TESTBENCH_PLAN.md`, and the HiCo-Nav paper report. Tailscale address timed out; campus address (`rcp2026@10.91.242.76`) reached the box, so GPU/RAM/disk numbers came from a live `nvidia-smi`/`free -h`/`df -h`, not just the 2026-09-11 bench log. No SLURM client on the box, so the REP Makers claim stays unchecked. |
| 2026-09-21 | Claude (Opus 5) + Dion | AnyGrasp source path updated to `grasp/vendor/` after reorg step 3. |
