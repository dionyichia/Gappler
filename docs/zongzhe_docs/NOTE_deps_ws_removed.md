# `deps_ws/` no longer exists (2026-09-21, left here by Dion)

Your [`BUILD_WORKSPACES.md`](BUILD_WORKSPACES.md) explains why `deps_ws` and
`ros2_robot_ws` are built separately. That changed in reorg step 3 (`NEXT_STEPS.md` §2.15):

- **MoveIt Task Constructor moved** from `deps_ws/src/` to `grasp/vendor/moveit_task_constructor/`.
  `deps_ws/` is deleted.
- **One build, one overlay.** `./bench/build.sh` builds `ros2_robot_ws/src`, `arm/vendor` and
  `grasp/vendor` together into the repo-root `install/`. `env.sh` sources only that.
- **`ros2_robot_ws/install.sh`** still builds `deps_ws` first, so it no longer works. On a fresh
  clone it stops at `cd deps_ws`, before any `rm -rf`. On an old clone a leftover `deps_ws/` (its
  ignored `build/` and `install/` survive a pull) lets it run on and fail later. Use
  `./bench/build.sh` instead. Whether to delete or rewrite `install.sh` is open.

Please update or retire `BUILD_WORKSPACES.md` when you next work in your folder.
