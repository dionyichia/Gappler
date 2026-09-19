# Why `deps_ws` and `ros2_robot_ws` are built separately

**Status:** written 2026-09-15 from a question answered by Puneet on 2026-08-25, then checked
against the code. Nothing here was run. The build timing quoted below comes from a bench run
someone else recorded on the lab box.

## The short answer

The two workspaces are built separately on purpose, and the split is worth the extra step.

- **`deps_ws/` is the underlay.** It holds MoveIt Task Constructor, which is open source code from
  outside the project that we do not edit. It takes 10 to 15 minutes to build, and is built once
  per machine.
- **`ros2_robot_ws/` is the overlay.** It holds the arm code we actually write. It should build in
  under a minute and gets rebuilt constantly.

Keeping them apart means the slow half is built once and then left alone. You can delete and rebuild
your own workspace as often as you like without paying for MoveIt Task Constructor again.

## The question and the answer

`[reported]` Puneet, chat, 2026-08-25. Quoted as written.

> **Q:** I saw that there are 2 separate colcon builds on deps_ws and ros2_robot_ws, and I was
> wondering if there are any design concerns behind splitting both builds vs building them together
> at the root folder.
>
> **A:** Deps is absolutely massive and takes 10-15min, its mostly open source code from outside
> libraries. It acts as an underlay, and is only built the first time you run it the code on the
> system
>
> Ros2 robot ws is the code that you actively write and change and should compile within a minute at
> most and can be repeatedly run. This acts as an overlay

## What underlay and overlay mean, if you have not used colcon

A colcon workspace is a folder with a `src/` of packages. Building it produces an `install/` folder
containing a script called `setup.bash`. Running `source install/setup.bash` tells your shell that
those packages exist, so anything you build or launch afterwards can find them.

Workspaces stack. If you source workspace A and then build workspace B, B can use A's packages.
A is then the **underlay** and B is the **overlay**. The stacking is done entirely by sourcing, in
that order, in that shell. There is nothing else to configure.

That is why the order matters, and it is the part that trips people up. Build the overlay without
sourcing the underlay first and the build fails to find things it needs, in ways that are confusing
to read.

## How this shows up in this repo

`[code]` `ros2_robot_ws/install.sh` already implements exactly what Puneet described. Reading it is
the fastest way to see the design.

| Line | What it does | Why it matters |
|---|---|---|
| `install.sh:12-18` | Builds `deps_ws` **only if** `deps_ws/install/setup.bash` is missing | This is the "built the first time and never again" behaviour. On a machine that already has it, this block is skipped entirely. |
| `install.sh:21` | `source "$DEPS_WS/install/setup.bash"` | Makes the underlay available before the overlay is built. This one line is what makes the split work. |
| `install.sh:26` | `rm -rf ./log ./build ./install`, inside the robot workspace only | Wipes the overlay for a clean rebuild. `deps_ws` is deliberately untouched, which is the whole point. |
| `install.sh:28-36` | Builds `rm_ros_interfaces` first, sources the result, then builds everything | The custom grasp messages (`GraspCandidate.msg`) have to exist before the packages that use them compile. |

`[code]` The split is also what actually ran on the lab box.
[`../TESTBENCH_PLAN.md`](../TESTBENCH_PLAN.md) line 313 records `deps_ws/install`
and `ros2_robot_ws/install` sitting side by side in both clones on that machine.

`[reported]` The slow half is genuinely slow. The bench's own build, which compiles both source trees
together, finished 22 packages in **27 minutes 40 seconds** from cold
([`../bench-runs/2026-09-11-labbox-build-sim.txt`](../bench-runs/2026-09-11-labbox-build-sim.txt)
line 4). Puneet's 10 to 15 minutes is the dependency half of that on its own.

One honest qualification. colcon is incremental, so a second build of an unchanged workspace is fast
whether or not the two are split. The split does not speed up ordinary rebuilds much. What it buys
you is insulation: when the overlay gets into a bad state and you want to delete `build/` and
`install/` and start again, the split means that costs you a minute instead of half an hour.

## How this squares with ORIENTATION section 3

[`../ORIENTATION.md`](../ORIENTATION.md) lines 296 to 302 gives different advice.
It says to run `colcon build` from the repo root so colcon finds both source trees and produces one
overlay, and warns that "building from inside either workspace gives you a partial one that fails at
runtime in confusing ways".

`[inferred]` **These are not in conflict, and the missing piece is the sourcing step.** The failure
ORIENTATION warns about is what happens when you build inside one workspace *without sourcing the
other one first*. `install.sh:21` sources the underlay before it builds anything. That single line is
the difference between a working split and the broken partial overlay ORIENTATION describes. The
current wording does not mention it, so a reader takes away "per-workspace builds are a mistake",
when the accurate version is "per-workspace builds need the underlay sourced first".

This reading is tagged `[inferred]` because it is my explanation of why two pieces of advice differ.
Nobody has confirmed it, and both were written by people with more context than I have.

Which one to use, in practice:

- **Building from the root** is the simpler one-shot check of whether the whole thing compiles. That
  is what the bench does.
- **The split**, via `install.sh`, is the one to use while actively working on arm code, because it
  keeps your rebuild loop short and protects the dependency build.

## For Dion

Two things for you to decide. Recording them here rather than changing anything, per the no-fixes
rule and rule 3 on not editing another person's folder.

1. **`ORIENTATION.md:296-302` could gain one sentence.** Something to the effect that a
   per-workspace build is fine as long as the underlay is sourced first, pointing at
   `ros2_robot_ws/install.sh:21` as the worked example. As written, the section reads as though the
   root build is the only correct approach, which leaves the repo's own build script looking like a
   mistake rather than the intended design. `install.sh` is currently named in the docs exactly once,
   at `NEXT_STEPS.md:243`, only as a file with a broken hardcoded path.

2. **`bench/build.sh:23` merges both source trees into one `build/` and `install/`.** For a Tier 2
   "does it compile" check that is a reasonable choice and probably the right one. The question is
   whether clearing a bad overlay should cost a full rebuild of MoveIt Task Constructor, or whether
   Tier 2 should mirror `install.sh` and keep the underlay in its own install base. Your call, since
   it is your bench and the tradeoff depends on how often Tier 2 gets re-run from scratch.

~~Either way there is a blocker in front of both.~~ **Fixed 2026-09-15**, see
[`T0.3_SESSION.md`](T0.3_SESSION.md). `install.sh:4-5` used to hardcode
`$HOME/GitHub/Renaissance-Capstone-Project/`, the old repo name, so the script could not run on any
current clone (`ORIENTATION.md` section 8.4, `NEXT_STEPS.md` section 2.5). `install.sh:7` now derives
the repo root from the script's own location, so the build layout decision above is no longer blocked
on it.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-15 | Claude (Opus 5) + Zongzhe | First version. Puneet's answer recorded, checked against `install.sh`, `TESTBENCH_PLAN` line 313 and the 2026-09-11 bench build. Added the reconciliation with ORIENTATION section 3 and two questions for Dion. |
| 2026-09-15 | Claude (Opus 5) + Zongzhe | Renumbered every `install.sh` citation (+4 lines) after T0.3 fixed its repo root, and retagged the `install.sh:4-5` blocker as fixed. No claim changed, only line numbers and that one status. |
